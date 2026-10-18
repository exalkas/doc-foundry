import asyncio
import logging
import os
from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings, Settings
from app.database import Base, get_db
from app.main import create_app

logger = logging.getLogger(__name__)


def _build_test_database_url() -> str:
    """
    Build a PostgreSQL async database URL for tests, using environment variables
    prefixed with TEST_ if present, otherwise falling back to DB_ vars or sensible defaults.
    """
    db_host = os.getenv("TEST_DB_HOST", os.getenv("DB_HOST", "localhost"))
    db_port = os.getenv("TEST_DB_PORT", os.getenv("DB_PORT", "5432"))
    db_name = os.getenv("TEST_DB_NAME", os.getenv("DB_NAME", "docfoundry_test"))
    db_user = os.getenv("TEST_DB_USER", os.getenv("DB_USER", "postgres"))
    db_password = os.getenv("TEST_DB_PASSWORD", os.getenv("DB_PASSWORD", "postgres"))

    return (
        f"postgresql+asyncpg://{db_user}:{db_password}"
        f"@{db_host}:{db_port}/{db_name}"
    )


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """
    Create an event loop for the whole test session.

    This overrides pytest-asyncio's default function-scoped loop to allow
    session-scoped async fixtures.
    """
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


@pytest.fixture(scope="session", autouse=True)
def settings() -> Settings:
    """
    Provide application settings for tests.

    Adjusts a few settings to be more test-friendly (e.g. test secret key).
    """
    # Set test secret key via environment variable before creating settings
    import os
    if "SECRET_KEY" not in os.environ:
        os.environ["SECRET_KEY"] = "test-secret-key"
    test_settings = get_settings()
    return test_settings


async def _ensure_enums_exist(conn):
    """Ensure all enum types exist before creating tables."""
    from sqlalchemy import text
    
    enum_definitions = {
        "global_user_role": ["admin", "user"],
        "auth_provider": ["local", "google"],
        "workspace_status": ["active", "suspended", "trial", "canceled"],
        "workspace_member_role_enum": ["owner", "member", "readonly"],
        "workspace_member_status_enum": ["pending", "active", "revoked"],
        "subscription_plan_enum": ["basic", "pro"],
        "subscription_status_enum": ["active", "past_due", "canceled", "trialing"],
        "export_format_enum": ["json", "csv", "excel"],
        "document_status_enum": ["pending", "processing", "completed", "failed"],
        "document_source_enum": ["ui", "api"],
        "job_type_enum": ["document_extraction", "webhook_delivery"],
        "job_status_enum": ["queued", "processing", "succeeded", "failed"],
        "api_key_status_enum": ["active", "revoked"],
        "webhook_delivery_status_enum": ["pending", "succeeded", "failed"],
        "audit_actor_type_enum": ["user", "system"],
        "notification_channel": ["email", "in_app"],
        "extraction_log_level": ["info", "warning", "error"],
    }
    
    for enum_name, enum_values in enum_definitions.items():
        result = await conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_type 
                    WHERE typname = :enum_name
                )
            """),
            {"enum_name": enum_name}
        )
        exists = result.scalar()
        
        if not exists:
            values_sql = ", ".join([f"'{v}'" for v in enum_values])
            await conn.execute(
                text(f'CREATE TYPE "{enum_name}" AS ENUM ({values_sql})')
            )


@pytest.fixture(scope="session")
async def async_engine(settings: Settings) -> AsyncGenerator[Any, None]:
    """
    Create a dedicated async SQLAlchemy engine for tests and ensure that
    database schema is created and dropped around the test session.
    """
    database_url = _build_test_database_url()
    engine = create_async_engine(
        database_url,
        echo=False,
    )

    # Create enum types first, then tables
    async with engine.begin() as conn:
        await _ensure_enums_exist(conn)
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield engine
    finally:
        # Drop all tables after tests complete
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest.fixture(scope="session")
async def async_session_maker(
    async_engine: Any,
) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """
    Provide a sessionmaker bound to the test engine for creating AsyncSession instances.
    """
    session_maker: async_sessionmaker[AsyncSession] = async_sessionmaker(
        bind=async_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    yield session_maker


@pytest.fixture
async def db_session(
    async_session_maker: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a database session for a single test.

    The session is rolled back at the end of the test to ensure isolation.
    """
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            # Rollback any uncommitted changes to keep tests isolated
            await session.rollback()


@pytest.fixture
async def app(
    settings: Settings, async_session_maker: async_sessionmaker[AsyncSession]
) -> AsyncGenerator[FastAPI, None]:
    """
    Create a FastAPI app instance configured to use the test database session.

    Overrides the application's `get_db` dependency so all routes use the
    test session instead of any production database.
    """
    application = create_app()

    async def _get_test_db() -> AsyncGenerator[AsyncSession, None]:
        async with async_session_maker() as session:
            try:
                yield session
            finally:
                await session.rollback()

    # Override the DB dependency globally for tests
    application.dependency_overrides[get_db] = _get_test_db

    yield application

    # Clear overrides after each usage to avoid leakage between tests
    application.dependency_overrides.clear()


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """
    Provide an HTTPX AsyncClient configured to talk to the FastAPI app.

    Usage:
        async def test_something(client: AsyncClient):
            response = await client.get("/api/health")
    """
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac