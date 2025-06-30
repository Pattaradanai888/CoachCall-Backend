# tests/unit/auth/test_service.py
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from sqlalchemy.pool import StaticPool

from src.auth.models import User, UserProfile
from src.auth.schemas import UserCreate, Token
from src.auth.service import register_user, login_user, refresh_tokens
from src.auth.utils import hash_password, create_refresh_token
from src.database import Base


@pytest.fixture
def in_memory_engine():
    return create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )


@pytest.fixture
async def setup_db(in_memory_engine):
    async with in_memory_engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                bind=sync_conn,
                tables=[User.__table__, UserProfile.__table__],
            )
        )
    yield


@pytest.fixture
async def db_session(in_memory_engine, setup_db) -> AsyncSession:
    session_maker = async_sessionmaker(
        bind=in_memory_engine, expire_on_commit=False, class_=AsyncSession
    )
    async with session_maker() as session:
        yield session


# --- Test ID: UTC-01 ---

@pytest.mark.asyncio
async def test_register_user_success(db_session):
    """
    UTC-01-TC-01: Test successful registration with valid data.
    """
    user_payload = UserCreate(
        fullname="Test User", email="new@test.com", password="Password123!"
    )
    result = await register_user(user_payload, db_session)

    assert result.id is not None
    assert result.email == "new@test.com"
    assert result.password != user_payload.password
    assert result.created_at is not None
    assert isinstance(result.profile, UserProfile)
    assert result.profile.display_name == "Test User"


@pytest.fixture
async def existing_user_data(db_session):
    """Prerequisite for duplicate email test."""
    existing_user = User(email="existing@test.com", password="hashed_password")
    db_session.add(existing_user)
    await db_session.commit()
    return existing_user


@pytest.mark.asyncio
async def test_register_user_duplicate_email(db_session, existing_user_data):
    """
    UTC-01-TC-02: Test registration with an email that already exists.
    """
    user_payload = UserCreate(
        fullname="Another User", email="existing@test.com", password="Password456!"
    )
    with pytest.raises(HTTPException) as exc_info:
        await register_user(user_payload, db_session)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Email already registered"


@pytest.mark.asyncio
async def test_register_user_unexpected_db_error(db_session: AsyncSession):
    """
    UTC-01-TC-03: An unexpected database error occurs during commit.
    """
    user_payload = UserCreate(
        fullname="Error User", email="error@test.com", password="Password789!"
    )

    # Mock the commit and rollback methods on the session
    db_session.commit = AsyncMock(side_effect=Exception("DB connection lost"))
    db_session.rollback = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await register_user(user_payload, db_session)

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "An unexpected error occurred during registration."
    db_session.rollback.assert_awaited_once()


# --- Test ID: UTC-02 ---

@pytest.fixture
async def existing_user_for_login(db_session: AsyncSession):
    """Prerequisite: A user exists for login tests."""
    hashed = hash_password("correct_password")
    user = User(email="user@test.com", password=hashed)
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_login_user_success(db_session: AsyncSession, existing_user_for_login):
    """
    UTC-02-TC-01: Test successful login with the correct email and password.
    """
    token = await login_user(
        email="user@test.com", password="correct_password", db=db_session
    )
    assert isinstance(token, Token)
    assert isinstance(token.access_token, str) and token.access_token != ""
    assert isinstance(token.refresh_token, str) and token.refresh_token != ""
    assert token.token_type == "bearer"


@pytest.mark.asyncio
async def test_login_user_wrong_password(db_session: AsyncSession, existing_user_for_login):
    """
    UTC-02-TC-02: Test login attempt with a wrong password.
    """
    with pytest.raises(HTTPException) as exc_info:
        await login_user(
            email="user@test.com", password="wrong_password", db=db_session
        )
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid email or password"


@pytest.mark.asyncio
async def test_login_user_nonexistent_email(db_session: AsyncSession):
    """
    UTC-02-TC-03: Test login attempt with a non-existent email.
    """
    with pytest.raises(HTTPException) as exc_info:
        await login_user(
            email="nouser@test.com", password="any_password", db=db_session
        )
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid email or password"


# --- Test ID: UTC-03 ---

@pytest.mark.asyncio
async def test_refresh_tokens_success():
    """
    UTC-03-TC-01: Refresh with a valid token → returns new tokens
    """
    valid_refresh = create_refresh_token({"sub": "alice@test.com"})
    token = await refresh_tokens(valid_refresh)

    assert isinstance(token, Token)
    assert isinstance(token.access_token, str) and token.access_token != ""
    assert isinstance(token.refresh_token, str) and token.refresh_token != ""
    assert token.token_type == "bearer"


@pytest.mark.asyncio
async def test_refresh_tokens_no_token():
    """
    UTC-03-TC-02: Refresh with an empty string → reject as missing token
    """
    with pytest.raises(HTTPException) as exc_info:
        await refresh_tokens("")

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "No refresh token provided"


@pytest.mark.asyncio
async def test_refresh_tokens_invalid_token():
    """
    UTC-03-TC-03: Refresh with an invalid/malformed token → reject as invalid
    """
    bad_token = "this.is.not.a.valid.token"
    with pytest.raises(HTTPException) as exc_info:
        await refresh_tokens(bad_token)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Could not validate token" in exc_info.value.detail


@pytest.mark.asyncio
async def test_refresh_tokens_missing_sub_claim():
    """
    UTC-03-TC-04: Failure: Provide a valid token that is missing the "sub" claim.
    """
    token_no_sub = create_refresh_token({"some_other_claim": "value"})
    with pytest.raises(HTTPException) as exc_info:
        await refresh_tokens(token_no_sub)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "Invalid token: Subject claim missing"


# --- Test ID: UTC-04 ---

@pytest.mark.asyncio
async def test_logout_user():
    """
    UTC-04-TC-01: Success: Call the logout function.
    """
    from src.auth.service import logout_user as service_logout
    result = await service_logout()
    assert result is None