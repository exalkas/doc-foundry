import logging
import os
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base

# Load environment variables from .env if present
load_dotenv()

logger = logging.getLogger(__name__)

# SQLAlchemy declarative base for ORM models
# Create base with legacy annotation support
# __allow_unmapped__ enables compatibility with legacy annotations (List[...] instead of Mapped[List[...]])
# This allows models using old-style annotations to work with SQLAlchemy 2.0
_DeclarativeBase = declarative_base()


class Base(_DeclarativeBase):
    """Base class for all ORM models with legacy annotation support."""
    __allow_unmapped__ = True
    __abstract__ = True


def _build_database_url() -> str:
    """
    Build the async PostgreSQL database URL from environment variables.

    Environment variables:
        DB_HOST (default: "localhost")
        DB_PORT (default: 5432)
        DB_NAME (required)
        DB_USER (required)
        DB_PASSWORD (required)

    Returns:
        A database URL string suitable for async SQLAlchemy engine.

    Raises:
        RuntimeError: If required variables are missing.
    """
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")

    missing = [name for name, value in [
        ("DB_NAME", db_name),
        ("DB_USER", db_user),
        ("DB_PASSWORD", db_password),
    ] if not value]

    if missing:
        msg = f"Missing required database environment variables: {', '.join(missing)}"
        logger.error(msg)
        raise RuntimeError(msg)

    # Use asyncpg driver for async SQLAlchemy
    return f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


def get_database_url() -> str:
    """
    Get the database URL for synchronous operations.
    
    This returns a sync-compatible PostgreSQL URL (without asyncpg driver)
    suitable for use with synchronous database tools.
    
    Returns:
        A database URL string suitable for synchronous SQLAlchemy engine.
    
    Raises:
        RuntimeError: If required environment variables are missing.
    """
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    
    missing = [name for name, value in [
        ("DB_NAME", db_name),
        ("DB_USER", db_user),
        ("DB_PASSWORD", db_password),
    ] if not value]
    
    if missing:
        msg = f"Missing required database environment variables: {', '.join(missing)}"
        logger.error(msg)
        raise RuntimeError(msg)
    
    # Use psycopg2 driver for sync SQLAlchemy
    return f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


DATABASE_URL = _build_database_url()

# Create async engine with sensible defaults
# Configure connection pool settings for better reliability
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True in development if detailed SQL logs are needed
    pool_pre_ping=True,  # Helps avoid stale connections
    pool_size=10,  # Number of connections to maintain
    max_overflow=20,  # Maximum number of connections beyond pool_size
    pool_recycle=3600,  # Recycle connections after 1 hour
    pool_reset_on_return="commit",  # Reset connection state on return
    connect_args={
        "server_settings": {
            "application_name": "docfoundry_backend",
        }
    },
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides an async database session.

    Yields:
        AsyncSession: An active SQLAlchemy async session.

    Ensures:
        Session is closed after request lifecycle.
        Transactions are rolled back on errors.
    """
    session: AsyncSession = AsyncSessionLocal()
    try:
        yield session
        # If no exception occurred, commit the transaction
        try:
            await session.commit()
        except SQLAlchemyError as commit_exc:
            logger.exception("Error committing transaction: %s", commit_exc)
            await session.rollback()
            raise
    except SQLAlchemyError as exc:
        logger.exception("Database error during request: %s", exc)
        # Let FastAPI's exception handlers deal with the error,
        # but ensure the transaction is rolled back.
        try:
            await session.rollback()
        except Exception as rollback_exc:
            logger.exception("Error during rollback: %s", rollback_exc)
        raise
    except HTTPException:
        # HTTPException is an expected application-level error, don't log as unexpected
        # FastAPI will handle it properly, but we still need to rollback
        try:
            await session.rollback()
        except Exception as rollback_exc:
            logger.exception("Error during rollback: %s", rollback_exc)
        raise
    except Exception as exc:
        # Catch any other exceptions and ensure rollback
        logger.exception("Unexpected error in database session: %s", exc)
        try:
            await session.rollback()
        except Exception as rollback_exc:
            logger.exception("Error during rollback: %s", rollback_exc)
        raise
    finally:
        try:
            await session.close()
        except Exception as close_exc:
            logger.warning("Error closing database session: %s", close_exc)


async def init_db() -> None:
    """
    Initialize database-related resources.

    This function can be called on application startup to:
      - Validate connectivity to the database.

    Raises:
        SQLAlchemyError: If connection test fails.
    """
    try:
        from sqlalchemy import text
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection established successfully.")
    except OperationalError as e:
        logger.error(
            "Failed to establish database connection. "
            "Please check that PostgreSQL is running and accessible. "
            "Error: %s", e
        )
        raise
    except SQLAlchemyError as e:
        logger.exception("Database error during initialization: %s", e)
        raise
    except Exception as e:
        logger.exception("Unexpected error during database initialization: %s", e)
        raise