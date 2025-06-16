# alembic/env.py
import os
from dotenv import load_dotenv
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Make sure your Base and all models are imported
# so that Base.metadata correctly reflects all tables.
from src.database import Base

# Import all model modules to ensure they're registered with Base
from src.auth import models as auth_models  # noqa
from src.athlete import models as profile_models # noqa
from src.course import models as course_models # noqa

# Load .env file for general use (e.g., if Alembic CLI needs DATABASE_URL)
load_dotenv()

# This is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the metadata for 'autogenerate' support
target_metadata = Base.metadata


def get_database_url() -> str:
    """Get database URL and convert async URL to sync for Alembic"""
    # Get the URL that might have been set by conftest.py or alembic.ini
    current_sqlalchemy_url = config.get_main_option("sqlalchemy.url")

    if current_sqlalchemy_url:
        return current_sqlalchemy_url

    # If not set by tests or alembic.ini, get from environment for CLI use
    env_db_url = os.getenv("DATABASE_URL")
    if not env_db_url:
        raise ValueError(
            "DATABASE_URL not found in environment variables and "
            "sqlalchemy.url not set in alembic.ini or test config."
        )

    # Convert async URL to sync for Alembic
    if "+asyncpg" in env_db_url:
        sync_db_url = env_db_url.replace("+asyncpg", "")
    elif "postgresql://" in env_db_url:  # Already a sync URL
        sync_db_url = env_db_url
    else:
        raise ValueError(
            f"DATABASE_URL format not recognized for sync conversion: {env_db_url}"
        )

    return sync_db_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,  # Enable type comparison
        compare_server_default=True,  # Enable server default comparison
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Set the database URL in config
    database_url = get_database_url()
    config.set_main_option("sqlalchemy.url", database_url)

    # Create engine from config
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # Enable type comparison
            compare_server_default=True,  # Enable server default comparison
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
