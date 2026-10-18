"""Tests for API keys endpoints."""

from __future__ import annotations

from typing import Any, Dict
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.apikey import ApiKey, ApiKeyStatusEnum
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspacemember import WorkspaceMember
from app.auth.utils import get_password_hash


@pytest.fixture
async def test_user_with_workspace(
    db_session: AsyncSession,
) -> tuple[User, Workspace, WorkspaceMember]:
    """Create a test user with workspace and membership."""
    user = User(
        email="apikey_test@example.com",
        password_hash=get_password_hash("TestPass123!"),
        full_name="API Key Test User",
        is_email_verified=True,
    )
    db_session.add(user)
    await db_session.flush()

    workspace = Workspace(
        name="API Key Test Workspace",
        owner_user_id=user.id,
    )
    db_session.add(workspace)
    await db_session.flush()

    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user.id,
        role="owner",
        status="active",
    )
    db_session.add(member)
    await db_session.commit()

    return user, workspace, member


@pytest.fixture
async def authenticated_api_client(
    app: Any,
    test_user_with_workspace: tuple[User, Workspace, WorkspaceMember],
) -> AsyncClient:
    """Create an authenticated client for API key tests."""
    user, workspace, _ = test_user_with_workspace
    
    # Login to get token
    async with AsyncClient(app=app, base_url="http://test") as client:
        login_response = await client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "TestPass123!"},
        )
        assert login_response.status_code == 200
        token = login_response.json()["token"]
        
        # Set workspace cookie
        await client.post(
            "/api/auth/switch-workspace",
            json={"workspace_id": str(workspace.id)},
            cookies={"access_token": token},
        )
        
        # Set auth cookie for subsequent requests
        client.cookies.set("access_token", token)
        yield client


@pytest.mark.asyncio
async def test_create_api_key_success(
    authenticated_api_client: AsyncClient,
    db_session: AsyncSession,
    test_user_with_workspace: tuple[User, Workspace, WorkspaceMember],
) -> None:
    """Test creating an API key successfully."""
    _, workspace, _ = test_user_with_workspace
    
    payload: Dict[str, Any] = {
        "name": "Test API Key",
        "scopes": ["documents:read", "documents:write"],
    }
    
    response = await authenticated_api_client.post("/api/api-keys", json=payload)
    assert response.status_code == 201
    
    data = response.json()
    assert "api_key" in data
    assert "plaintext_key" in data
    
    api_key_data = data["api_key"]
    assert api_key_data["name"] == payload["name"]
    assert api_key_data["workspace_id"] == str(workspace.id)
    assert api_key_data["status"] == "active"
    assert set(api_key_data["scopes"]) == set(payload["scopes"])
    assert api_key_data["prefix"] is not None
    
    # Verify plaintext key is returned only once
    assert data["plaintext_key"] is not None
    assert len(data["plaintext_key"]) > 0
    
    # Verify in database
    result = await db_session.execute(
        select(ApiKey).where(ApiKey.id == api_key_data["id"])
    )
    db_api_key = result.scalar_one_or_none()
    assert db_api_key is not None
    assert db_api_key.name == payload["name"]
    assert db_api_key.status == "active"  # Verify lowercase value
    assert set(db_api_key.scopes) == set(payload["scopes"])


@pytest.mark.asyncio
async def test_create_api_key_with_expiration(
    authenticated_api_client: AsyncClient,
    test_user_with_workspace: tuple[User, Workspace, WorkspaceMember],
) -> None:
    """Test creating an API key with expiration date."""
    from datetime import datetime, timezone, timedelta
    
    payload: Dict[str, Any] = {
        "name": "Expiring API Key",
        "scopes": ["documents:read"],
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
    }
    
    response = await authenticated_api_client.post("/api/api-keys", json=payload)
    assert response.status_code == 201
    
    data = response.json()
    api_key_data = data["api_key"]
    assert api_key_data["expires_at"] is not None


@pytest.mark.asyncio
async def test_list_api_keys(
    authenticated_api_client: AsyncClient,
    db_session: AsyncSession,
    test_user_with_workspace: tuple[User, Workspace, WorkspaceMember],
) -> None:
    """Test listing API keys."""
    _, workspace, _ = test_user_with_workspace
    
    # Create a test API key directly in DB
    api_key = ApiKey(
        workspace_id=workspace.id,
        name="Test Key",
        key_hash="test_hash",
        prefix="test",
        scopes=["documents:read"],
        status="active",
    )
    db_session.add(api_key)
    await db_session.commit()
    
    response = await authenticated_api_client.get("/api/api-keys")
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(key["name"] == "Test Key" for key in data)


@pytest.mark.asyncio
async def test_revoke_api_key(
    authenticated_api_client: AsyncClient,
    db_session: AsyncSession,
    test_user_with_workspace: tuple[User, Workspace, WorkspaceMember],
) -> None:
    """Test revoking an API key."""
    _, workspace, _ = test_user_with_workspace
    
    # Create a test API key
    api_key = ApiKey(
        workspace_id=workspace.id,
        name="To Revoke",
        key_hash="test_hash",
        prefix="test",
        scopes=["documents:read"],
        status="active",
    )
    db_session.add(api_key)
    await db_session.commit()
    
    response = await authenticated_api_client.post(
        f"/api/api-keys/{api_key.id}/revoke"
    )
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "revoked"
    
    # Verify in database
    await db_session.refresh(api_key)
    assert api_key.status == "revoked"  # Verify lowercase value


@pytest.mark.asyncio
async def test_create_api_key_requires_scopes(
    authenticated_api_client: AsyncClient,
) -> None:
    """Test that creating an API key requires at least one scope."""
    payload = {
        "name": "No Scopes Key",
        "scopes": [],
    }
    
    response = await authenticated_api_client.post("/api/api-keys", json=payload)
    # Should fail validation (400) or succeed but this test verifies scopes are required
    # The actual behavior depends on Pydantic validation
    assert response.status_code in (400, 422)


@pytest.mark.asyncio
async def test_create_api_key_enum_value_is_lowercase(
    authenticated_api_client: AsyncClient,
    db_session: AsyncSession,
    test_user_with_workspace: tuple[User, Workspace, WorkspaceMember],
) -> None:
    """Test that API key status enum values are stored as lowercase in database."""
    _, workspace, _ = test_user_with_workspace
    
    payload = {
        "name": "Lowercase Test",
        "scopes": ["documents:read"],
    }
    
    response = await authenticated_api_client.post("/api/api-keys", json=payload)
    assert response.status_code == 201
    
    data = response.json()
    api_key_id = data["api_key"]["id"]
    
    # Verify the status is lowercase in the database
    result = await db_session.execute(
        select(ApiKey).where(ApiKey.id == api_key_id)
    )
    db_api_key = result.scalar_one_or_none()
    assert db_api_key is not None
    assert db_api_key.status == "active"  # Must be lowercase

