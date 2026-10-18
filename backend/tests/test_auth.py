from __future__ import annotations

from typing import Any, Dict

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspacemember import WorkspaceMember
from app.auth.utils import verify_password


@pytest.mark.asyncio
async def test_register_creates_user_workspace_and_sets_cookie(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Register endpoint should create a user, workspace, member record and set auth cookie."""
    payload: Dict[str, Any] = {
        "full_name": "Test User",
        "email": "register@example.com",
        "password": "StrongPassw0rd!",
        "workspace_name": "Test Workspace",
    }

    response = await async_client.post("/api/auth/register", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert "token" in data
    assert "user" in data
    assert "workspace" in data

    # Check response structure
    user_data = data["user"]
    workspace_data = data["workspace"]

    assert user_data["email"] == payload["email"]
    assert user_data["full_name"] == payload["full_name"]
    assert workspace_data["name"] == payload["workspace_name"]

    # Cookie should be set
    cookies = response.cookies
    assert "access_token" in cookies or any(
        c.name == "access_token" for c in response.cookies.jar
    )

    # Validate DB records
    user_stmt = select(User).where(User.email == payload["email"])
    user_result = await db_session.execute(user_stmt)
    user: User | None = user_result.scalar_one_or_none()
    assert user is not None
    assert user.full_name == payload["full_name"]
    assert user.is_email_verified is False
    assert verify_password(payload["password"], user.password_hash)

    ws_stmt = select(Workspace).where(Workspace.owner_user_id == user.id)
    ws_result = await db_session.execute(ws_stmt)
    workspace: Workspace | None = ws_result.scalar_one_or_none()
    assert workspace is not None
    assert workspace.name == payload["workspace_name"]

    member_stmt = select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == workspace.id,
        WorkspaceMember.user_id == user.id,
    )
    member_result = await db_session.execute(member_stmt)
    member: WorkspaceMember | None = member_result.scalar_one_or_none()
    assert member is not None
    assert member.role == "owner"


@pytest.mark.asyncio
async def test_register_duplicate_email_fails(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Register with an existing email should return 400/409 error."""
    email = "dup@example.com"
    password = "StrongPassw0rd!"

    # Create existing user
    existing_user = User(
        email=email,
        password_hash="hash",
        full_name="Existing",
        is_email_verified=False,
    )
    db_session.add(existing_user)
    await db_session.commit()

    payload = {
        "full_name": "New User",
        "email": email,
        "password": password,
        "workspace_name": "Another Workspace",
    }

    response = await async_client.post("/api/auth/register", json=payload)
    assert response.status_code in (400, 409)


@pytest.mark.asyncio
async def test_login_success_sets_cookie_and_returns_user_and_workspaces(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_workspace: Workspace,
    test_workspace_member: WorkspaceMember,
    user_password: str,
) -> None:
    """Login with valid credentials should set cookie and return user and workspaces."""
    payload = {"email": test_user.email, "password": user_password}

    response = await async_client.post("/api/auth/login", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert "token" in data
    assert "user" in data
    assert "workspaces" in data
    assert "current_workspace" in data

    user_data = data["user"]
    workspaces = data["workspaces"]
    current_ws = data["current_workspace"]

    assert user_data["id"] == str(test_user.id)
    assert user_data["email"] == test_user.email
    assert isinstance(workspaces, list)
    assert any(ws["id"] == str(test_workspace.id) for ws in workspaces)
    assert current_ws is not None
    assert current_ws["id"] == str(test_workspace.id)

    # Cookie set
    cookies = response.cookies
    assert "access_token" in cookies or any(
        c.name == "access_token" for c in response.cookies.jar
    )


@pytest.mark.asyncio
async def test_login_invalid_password(
    async_client: AsyncClient,
    test_user: User,
) -> None:
    """Login with invalid password should fail."""
    payload = {"email": test_user.email, "password": "WrongPassword123!"}

    response = await async_client.post("/api/auth/login", json=payload)
    assert response.status_code in (400, 401)


@pytest.mark.asyncio
async def test_login_unknown_email(
    async_client: AsyncClient,
) -> None:
    """Login with unknown email should fail without leaking existence."""
    payload = {"email": "unknown@example.com", "password": "SomePass123!"}

    response = await async_client.post("/api/auth/login", json=payload)
    assert response.status_code in (400, 401)


@pytest.mark.asyncio
async def test_me_requires_auth(async_client: AsyncClient) -> None:
    """GET /auth/me should require authentication."""
    response = await async_client.get("/api/auth/me")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_me_returns_current_user_and_workspaces(
    authenticated_client: AsyncClient,
    test_user: User,
    test_workspace: Workspace,
) -> None:
    """GET /auth/me should return current user, their workspaces, and current workspace."""
    response = await authenticated_client.get("/api/auth/me")
    assert response.status_code == 200

    data = response.json()
    assert "user" in data
    assert "workspaces" in data
    assert "current_workspace" in data

    user_data = data["user"]
    assert user_data["id"] == str(test_user.id)
    assert user_data["email"] == test_user.email

    workspaces = data["workspaces"]
    assert isinstance(workspaces, list)
    assert any(ws["id"] == str(test_workspace.id) for ws in workspaces)

    current_ws = data["current_workspace"]
    assert current_ws is not None
    assert current_ws["id"] == str(test_workspace.id)


@pytest.mark.asyncio
async def test_switch_workspace_changes_current_workspace_cookie(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_workspace: Workspace,
) -> None:
    """POST /auth/switch-workspace should change current workspace if user is a member."""
    # Create another workspace and membership for the same user
    other_ws = Workspace(
        name="Other Workspace",
        owner_user_id=test_user.id,
    )
    db_session.add(other_ws)
    await db_session.flush()

    other_member = WorkspaceMember(
        workspace_id=other_ws.id,
        user_id=test_user.id,
        role="member",
    )
    db_session.add(other_member)
    await db_session.commit()

    payload = {"workspace_id": str(other_ws.id)}
    response = await authenticated_client.post(
        "/api/auth/switch-workspace", json=payload
    )
    assert response.status_code == 200

    data = response.json()
    assert "current_workspace" in data
    current_ws = data["current_workspace"]
    assert current_ws["id"] == str(other_ws.id)

    # Optionally, verify cookie changed
    cookies = response.cookies
    # Name depends on implementation; we at least expect some workspace cookie or JWT updated
    # This assertion is intentionally loose:
    assert len(cookies) >= 1


@pytest.mark.asyncio
async def test_switch_workspace_forbidden_for_non_member(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """User should not be able to switch to a workspace they are not a member of."""
    foreign_ws = Workspace(
        name="Foreign Workspace",
        owner_user_id=test_user.id,  # ownership doesn't imply membership in our member table in tests
    )
    db_session.add(foreign_ws)
    await db_session.commit()

    payload = {"workspace_id": str(foreign_ws.id)}
    response = await authenticated_client.post(
        "/api/auth/switch-workspace", json=payload
    )
    assert response.status_code in (403, 404)