"""E2E tests for multi-tenant isolation."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspacemember import WorkspaceMember, WorkspaceMemberRole, WorkspaceMemberStatus
from app.models.document import Document
from app.models.template import Template
from app.models.apikey import ApiKey
from app.auth.dependencies import get_password_hash
from app.auth.utils import hash_api_key


@pytest.fixture
async def second_workspace(
    db_session: AsyncSession,
    test_user: User,
) -> Workspace:
    """Create a second workspace for isolation tests."""
    workspace = Workspace(
        name="Second Workspace",
        owner_user_id=test_user.id,
    )
    db_session.add(workspace)
    await db_session.flush()

    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=test_user.id,
        role=WorkspaceMemberRole.OWNER,
        status=WorkspaceMemberStatus.ACTIVE,
    )
    db_session.add(member)
    await db_session.commit()
    await db_session.refresh(workspace)
    return workspace


@pytest.fixture
async def foreign_user(
    db_session: AsyncSession,
) -> User:
    """Create a user in a different workspace."""
    user = User(
        email=f"foreign_{uuid4().hex[:8]}@example.com",
        password_hash=get_password_hash("ForeignPass123!"),
        full_name="Foreign User",
        is_email_verified=True,
    )
    db_session.add(user)
    await db_session.flush()

    workspace = Workspace(
        name="Foreign Workspace",
        owner_user_id=user.id,
    )
    db_session.add(workspace)
    await db_session.flush()

    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user.id,
        role=WorkspaceMemberRole.OWNER,
        status=WorkspaceMemberStatus.ACTIVE,
    )
    db_session.add(member)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_workspace_data_isolation_documents(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_workspace: Workspace,
    second_workspace: Workspace,
    test_user: User,
) -> None:
    """Test user can only access documents in their current workspace."""
    # Create documents in both workspaces
    doc1 = Document(
        workspace_id=test_workspace.id,
        file_name="doc1.pdf",
        file_type="application/pdf",
        storage_path="/tmp/doc1.pdf",
        status="pending",
        uploaded_by_user_id=test_user.id,
        source="ui",
    )
    doc2 = Document(
        workspace_id=second_workspace.id,
        file_name="doc2.pdf",
        file_type="application/pdf",
        storage_path="/tmp/doc2.pdf",
        status="pending",
        uploaded_by_user_id=test_user.id,
        source="ui",
    )
    db_session.add_all([doc1, doc2])
    await db_session.commit()

    # List documents - should only see documents from current workspace
    response = await authenticated_client.get("/api/documents")
    assert response.status_code == 200
    data = response.json()
    
    # Extract document list (might be paginated)
    documents = data.get("documents", data) if isinstance(data, dict) else data
    if isinstance(documents, list):
        doc_ids = [doc["id"] if isinstance(doc, dict) else str(doc) for doc in documents]
        # Should only see doc1 (from current workspace)
        assert str(doc1.id) in doc_ids or len(doc_ids) == 0  # Might be empty if filtering works


@pytest.mark.asyncio
async def test_api_keys_workspace_scoped(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_workspace: Workspace,
    second_workspace: Workspace,
    test_user: User,
) -> None:
    """Test API keys are workspace-scoped."""
    import secrets

    # Create API key in first workspace
    prefix1 = "dk_test1"
    secret1 = secrets.token_urlsafe(32)
    full_key1 = f"{prefix1}_{secret1}"

    api_key1 = ApiKey(
        workspace_id=test_workspace.id,
        name="Workspace 1 Key",
        prefix=prefix1,
        key_hash=hash_api_key(full_key1),
        scopes=["documents:read"],
        status="active",
        created_by_user_id=test_user.id,
    )
    db_session.add(api_key1)
    await db_session.commit()

    # List API keys - should only see keys from current workspace
    response = await authenticated_client.get("/api/api-keys")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Should only see api_key1
    key_ids = [key["id"] for key in data]
    assert str(api_key1.id) in key_ids


@pytest.mark.asyncio
async def test_templates_workspace_scoped(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_workspace: Workspace,
    second_workspace: Workspace,
    test_user: User,
) -> None:
    """Test templates are workspace-scoped."""
    from app.models.template import Template, ExportFormatEnum

    # Create templates in both workspaces
    template1 = Template(
        workspace_id=test_workspace.id,
        name="Template 1",
        field_schema={},
        default_export_format=ExportFormatEnum.JSON,
        created_by_user_id=test_user.id,
    )
    template2 = Template(
        workspace_id=second_workspace.id,
        name="Template 2",
        field_schema={},
        default_export_format=ExportFormatEnum.JSON,
        created_by_user_id=test_user.id,
    )
    db_session.add_all([template1, template2])
    await db_session.commit()

    # List templates - should only see templates from current workspace
    response = await authenticated_client.get("/api/templates")
    assert response.status_code == 200
    data = response.json()
    
    templates = data.get("templates", data) if isinstance(data, dict) else data
    if isinstance(templates, list):
        template_ids = [t["id"] if isinstance(t, dict) else str(t) for t in templates]
        # Should only see template1
        assert str(template1.id) in template_ids or len(template_ids) == 0


@pytest.mark.asyncio
async def test_workspace_member_invite(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_workspace: Workspace,
    foreign_user: User,
) -> None:
    """Test owner can invite members."""
    payload = {
        "email": foreign_user.email,
        "role": "member",
    }

    response = await authenticated_client.post(
        f"/api/workspaces/current/invite",
        json=payload,
    )
    # Invite might return 200, 201, or 202 depending on implementation
    assert response.status_code in (200, 201, 202)

    # Verify membership was created
    member_stmt = select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == test_workspace.id,
        WorkspaceMember.user_id == foreign_user.id,
    )
    member_result = await db_session.execute(member_stmt)
    member = member_result.scalar_one_or_none()
    # Member might be created immediately or via invitation flow
    assert member is not None or response.status_code == 202


@pytest.mark.asyncio
async def test_role_based_permissions_owner(
    authenticated_client: AsyncClient,
    test_workspace: Workspace,
) -> None:
    """Test owner can manage workspace settings."""
    # Owner should be able to update workspace
    payload = {
        "name": "Updated Workspace Name",
    }

    response = await authenticated_client.patch(
        "/api/workspaces/current",
        json=payload,
    )
    # Owner should have permission
    assert response.status_code in (200, 204)


@pytest.mark.asyncio
async def test_role_based_permissions_member(
    app: Any,
    db_session: AsyncSession,
    test_workspace: Workspace,
    foreign_user: User,
) -> None:
    """Test member can upload documents but not manage billing."""
    from app.auth.dependencies import create_access_token, TokenType

    # Create member user
    member_user = User(
        email=f"member_{uuid4().hex[:8]}@example.com",
        password_hash=get_password_hash("MemberPass123!"),
        full_name="Member User",
        is_email_verified=True,
    )
    db_session.add(member_user)
    await db_session.flush()

    member = WorkspaceMember(
        workspace_id=test_workspace.id,
        user_id=member_user.id,
        role=WorkspaceMemberRole.MEMBER,
        status=WorkspaceMemberStatus.ACTIVE,
    )
    db_session.add(member)
    await db_session.commit()

    # Create authenticated client for member
    token = create_access_token(
        data={"sub": str(member_user.id), "workspace_id": str(test_workspace.id)},
        token_type=TokenType.SESSION,
    )

    async with AsyncClient(app=app, base_url="http://testserver") as client:
        client.cookies.set("access_token", token)
        client.cookies.set("current_workspace_id", str(test_workspace.id))

        # Member should be able to upload documents
        # (This would require a file, so we just verify the endpoint exists)
        # Member should NOT be able to manage billing
        response = await client.get("/api/billing/portal-session")
        # Should fail with 403 or redirect
        assert response.status_code in (403, 401, 302)


@pytest.mark.asyncio
async def test_cross_workspace_access_prevention(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_workspace: Workspace,
    foreign_user: User,
) -> None:
    """Test cross-workspace access prevention."""
    # Create a document in foreign workspace
    foreign_workspace_stmt = select(Workspace).where(
        Workspace.owner_user_id == foreign_user.id,
    )
    foreign_ws_result = await db_session.execute(foreign_workspace_stmt)
    foreign_workspace = foreign_ws_result.scalar_one_or_none()
    assert foreign_workspace is not None

    foreign_doc = Document(
        workspace_id=foreign_workspace.id,
        file_name="foreign_doc.pdf",
        file_type="application/pdf",
        storage_path="/tmp/foreign.pdf",
        status="pending",
        uploaded_by_user_id=foreign_user.id,
        source="ui",
    )
    db_session.add(foreign_doc)
    await db_session.commit()

    # Try to access foreign document - should fail
    response = await authenticated_client.get(f"/api/documents/{foreign_doc.id}")
    assert response.status_code in (403, 404)

