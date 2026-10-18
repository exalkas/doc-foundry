"""
Test package initialization for the DocFoundry backend.

This module configures common pytest fixtures that can be reused across
the test suite, such as a test database session and a FastAPI test client.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import create_app


TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/docfoundry_test",
)


@pytest.fixture(scope="session")
def event_loop():
    """
    Create an event loop for the entire test session.

    This overrides pytest-asyncio's default per-test-loop behavior so that
    expensive resources (like DB engines) can be shared safely.
    """
    import asyncio

    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine() -> AsyncGenerator:
    """
    Create an async SQLAlchemy engine bound to the test database.

    The database URL is taken from TEST_DATABASE_URL env var, falling back to a
    sensible local default for development.
    """
    engine = create_async_engine(TEST_DB_URL, echo=False)

    # Ensure schema exists for tests
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
async def async_session_factory(
    test_engine,
) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """
    Provide an async_sessionmaker bound to the test engine.
    """
    session_factory = async_sessionmaker(
        bind=test_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    yield session_factory


@pytest.fixture(scope="function")
async def db_session(
    async_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a database session for a single test function.

    Each test runs in its own transaction that is rolled back at the end,
    ensuring database isolation between tests.
    """
    async with async_session_factory() as session:
        trans = await session.begin()
        try:
            yield session
        finally:
            await trans.rollback()
            await session.close()


@pytest.fixture(scope="function")
async def app(db_session: AsyncSession) -> AsyncGenerator[FastAPI, None]:
    """
    Create a FastAPI application instance wired to use the test DB session.

    We override the `get_db` dependency so that all routes use the per-test
    `db_session` fixture instead of the production session.
    """
    application = create_app()

    async def _get_test_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    application.dependency_overrides[get_db] = _get_test_db

    yield application

    application.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """
    Provide an AsyncClient for making requests against the FastAPI app.

    This uses the in-process ASGI app, so no actual network sockets are opened.
    """
    async with AsyncClient(app=app, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture(scope="session", autouse=True)
def _set_test_env() -> Generator[None, None, None]:
    """
    Automatically set environment variables suitable for tests.

    This ensures the application runs in a non-production mode and
    uses deterministic paths and credentials where possible.
    """
    os.environ.setdefault("ENVIRONMENT", "test")
    os.environ.setdefault("DB_HOST", "localhost")
    os.environ.setdefault("DB_PORT", "5432")
    os.environ.setdefault("DB_NAME", "docfoundry_test")
    os.environ.setdefault("DB_USER", "postgres")
    os.environ.setdefault("DB_PASSWORD", "postgres")

    # Ensure a temporary storage directory for document-related tests
    storage_dir = Path(os.getenv("STORAGE_DIR", "/tmp/docfoundry_test_storage"))
    storage_dir.mkdir(parents=True, exist_ok=True)
    os.environ["STORAGE_DIR"] = str(storage_dir)

    yield