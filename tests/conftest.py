# tests/conftest.py
import asyncio
import os
import sys
from typing import AsyncGenerator

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy_utils import create_database, database_exists, drop_database
from alembic import command
from alembic.config import Config as AlembicConfig

from src.main import app as fastapi_app
from src.config import Settings
from src.database import get_async_session
from src.auth import models  # Ensure models are imported


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Test-specific settings"""
    return Settings()


@pytest.fixture(scope="session")
def alembic_config(test_settings: Settings) -> AlembicConfig:
    """Alembic configuration for test database"""
    config = AlembicConfig("alembic.ini")
    # Convert async URL to sync for Alembic
    sync_url = str(test_settings.TEST_DATABASE_URL).replace("postgresql+asyncpg", "postgresql")
    config.set_main_option("sqlalchemy.url", sync_url)
    return config


@pytest.fixture(scope="session", autouse=True)
def setup_test_database(test_settings: Settings, alembic_config: AlembicConfig):
    """Create and teardown test database for the entire test session"""
    sync_url = str(test_settings.TEST_DATABASE_URL).replace("postgresql+asyncpg", "postgresql")

    # Create database if it doesn't exist
    if database_exists(sync_url):
        drop_database(sync_url)
    create_database(sync_url)

    # Run migrations to set up schema
    original_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = sync_url

    try:
        command.upgrade(alembic_config, "head")
        yield
    finally:
        # Cleanup
        if original_db_url:
            os.environ["DATABASE_URL"] = original_db_url
        elif "DATABASE_URL" in os.environ:
            del os.environ["DATABASE_URL"]

        # Drop test database
        drop_database(sync_url)


@pytest_asyncio.fixture
async def db_engine(test_settings: Settings):
    """Create an async database engine for tests"""
    engine = create_async_engine(str(test_settings.TEST_DATABASE_URL))
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for tests with transaction rollback"""
    session_factory = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with session_factory() as session:
        # Start a transaction
        transaction = await session.begin()
        try:
            yield session
        finally:
            # Always rollback to keep tests isolated
            await transaction.rollback()


@pytest_asyncio.fixture
async def app(db_engine) -> FastAPI:
    """Create FastAPI app with test database dependency override"""

    async def get_test_db() -> AsyncGenerator[AsyncSession, None]:
        session_factory = async_sessionmaker(
            bind=db_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        async with session_factory() as session:
            yield session

    # Override the database dependency
    fastapi_app.dependency_overrides[get_async_session] = get_test_db

    yield fastapi_app

    # Clean up
    fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def async_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for testing"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest_asyncio.fixture
async def authenticated_client(async_client: AsyncClient, db_session: AsyncSession):
    """Create an authenticated client with a logged-in user"""
    from src.auth.service import register_user
    from src.auth.schemas import UserCreate

    # Create a test user
    user_data = UserCreate(
        fullname="Test User",
        email="test@example.com",
        password="testpassword123"
    )

    user = await register_user(user_data, db_session)
    await db_session.commit()

    # Login to get access token
    login_data = {
        "username": user.email,
        "password": "testpassword123"
    }

    login_response = await async_client.post("/auth/token", data=login_data)
    token_data = login_response.json()
    access_token = token_data["access_token"]

    # Set authorization header for future requests
    async_client.headers.update({"Authorization": f"Bearer {access_token}"})

    # Store user info for test access
    async_client.test_user = user

    return async_client


# Helper fixture for creating test users
@pytest_asyncio.fixture
async def create_user(db_session: AsyncSession):
    """Helper fixture to create test users"""
    from src.auth.service import register_user
    from src.auth.schemas import UserCreate

    async def _create_user(email: str = "test@example.com",
                           fullname: str = "Test User",
                           password: str = "testpassword123"):
        user_data = UserCreate(fullname=fullname, email=email, password=password)
        user = await register_user(user_data, db_session)
        await db_session.commit()
        return user

    return _create_user