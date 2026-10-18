"""E2E tests for authentication flows."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspacemember import WorkspaceMember
from app.auth.utils import verify_password


@pytest.mark.asyncio
async def test_complete_registration_flow(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test complete registration with email/password."""
    payload = {
        "full_name": "New User",
        "email": "newuser@example.com",
        "password": "StrongPassw0rd!",
        "workspace_name": "New Workspace",
    }

    response = await async_client.post("/api/auth/register", json=payload)
    assert response.status_code in (200, 201)

    data = response.json()
    assert "token" in data
    assert "user" in data
    assert "workspace" in data

    user_data = data["user"]
    workspace_data = data["workspace"]

    assert user_data["email"] == payload["email"]
    assert user_data["full_name"] == payload["full_name"]
    assert workspace_data["name"] == payload["workspace_name"]

    # Verify JWT cookie is set
    cookies = response.cookies
    assert "access_token" in cookies or any(
        c.name == "access_token" for c in response.cookies.jar
    )

    # Verify DB records
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
async def test_registration_duplicate_email_fails(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Test registration with duplicate email fails."""
    payload = {
        "full_name": "Another User",
        "email": test_user.email,
        "password": "AnotherPass123!",
        "workspace_name": "Another Workspace",
    }

    response = await async_client.post("/api/auth/register", json=payload)
    assert response.status_code in (400, 409)


@pytest.mark.asyncio
async def test_registration_validation(
    async_client: AsyncClient,
) -> None:
    """Test registration validation (password strength, email format)."""
    # Test invalid email
    payload = {
        "full_name": "Test User",
        "email": "invalid-email",
        "password": "StrongPassw0rd!",
        "workspace_name": "Test Workspace",
    }
    response = await async_client.post("/api/auth/register", json=payload)
    assert response.status_code in (400, 422)

    # Test weak password
    payload = {
        "full_name": "Test User",
        "email": "test@example.com",
        "password": "weak",
        "workspace_name": "Test Workspace",
    }
    response = await async_client.post("/api/auth/register", json=payload)
    assert response.status_code in (400, 422)


@pytest.mark.asyncio
async def test_login_success_sets_cookie(
    async_client: AsyncClient,
    test_user: User,
    test_workspace: Workspace,
    test_workspace_member: WorkspaceMember,
    user_password: str,
) -> None:
    """Test successful login sets JWT cookie and returns user/workspace data."""
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

    # Verify cookie is set
    cookies = response.cookies
    assert "access_token" in cookies or any(
        c.name == "access_token" for c in response.cookies.jar
    )


@pytest.mark.asyncio
async def test_login_invalid_credentials_fails(
    async_client: AsyncClient,
    test_user: User,
) -> None:
    """Test login with invalid credentials fails."""
    # Wrong password
    payload = {"email": test_user.email, "password": "WrongPassword123!"}
    response = await async_client.post("/api/auth/login", json=payload)
    assert response.status_code in (400, 401)

    # Unknown email
    payload = {"email": "unknown@example.com", "password": "SomePass123!"}
    response = await async_client.post("/api/auth/login", json=payload)
    assert response.status_code in (400, 401)


@pytest.mark.asyncio
async def test_me_endpoint_requires_auth(
    async_client: AsyncClient,
) -> None:
    """Test GET /api/auth/me requires authentication."""
    response = await async_client.get("/api/auth/me")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_me_endpoint_returns_user_data(
    authenticated_client: AsyncClient,
    test_user: User,
    test_workspace: Workspace,
) -> None:
    """Test GET /api/auth/me returns current user and workspaces."""
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
async def test_logout_clears_session(
    authenticated_client: AsyncClient,
) -> None:
    """Test logout clears session."""
    response = await authenticated_client.post("/api/auth/logout")
    # Logout might return 200 or 204
    assert response.status_code in (200, 204)

    # Verify subsequent requests fail
    me_response = await authenticated_client.get("/api/auth/me")
    assert me_response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_switch_workspace_success(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_workspace: Workspace,
) -> None:
    """Test user can switch between workspaces they're a member of."""
    # Create another workspace and membership
    from app.models.workspace import Workspace
    from app.models.workspacemember import WorkspaceMember, WorkspaceMemberRole, WorkspaceMemberStatus

    other_ws = Workspace(
        name="Other Workspace",
        owner_user_id=test_user.id,
    )
    db_session.add(other_ws)
    await db_session.flush()

    other_member = WorkspaceMember(
        workspace_id=other_ws.id,
        user_id=test_user.id,
        role=WorkspaceMemberRole.MEMBER,
        status=WorkspaceMemberStatus.ACTIVE,
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

    # Verify cookie updated
    cookies = response.cookies
    assert len(cookies) >= 1


@pytest.mark.asyncio
async def test_switch_workspace_forbidden_for_non_member(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Test user cannot switch to workspace they're not a member of."""
    from app.models.workspace import Workspace

    foreign_ws = Workspace(
        name="Foreign Workspace",
        owner_user_id=test_user.id,
    )
    db_session.add(foreign_ws)
    await db_session.commit()

    payload = {"workspace_id": str(foreign_ws.id)}
    response = await authenticated_client.post(
        "/api/auth/switch-workspace", json=payload
    )
    assert response.status_code in (403, 404)

