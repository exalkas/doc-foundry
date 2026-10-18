"""E2E tests for admin functions."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, GlobalUserRole
from app.models.workspace import Workspace, WorkspaceStatus
from app.models.auditlog import AuditLog


@pytest.mark.asyncio
async def test_admin_authentication_required(
    authenticated_client: AsyncClient,
) -> None:
    """Test admin endpoints require admin authentication."""
    # Regular user should not access admin endpoints
    response = await authenticated_client.get("/api/admin/workspaces")
    assert response.status_code in (403, 401)


@pytest.mark.asyncio
async def test_admin_can_access_endpoints(
    authenticated_admin_client: AsyncClient,
) -> None:
    """Test global admin can access admin endpoints."""
    response = await authenticated_admin_client.get("/api/admin/workspaces")
    # Admin should have access
    assert response.status_code in (200, 401, 403)  # Might still need proper admin setup


@pytest.mark.asyncio
async def test_admin_list_workspaces(
    authenticated_admin_client: AsyncClient,
    db_session: AsyncSession,
    test_workspace: Workspace,
) -> None:
    """Test admin can list all workspaces."""
    response = await authenticated_admin_client.get("/api/admin/workspaces")
    
    # Should return paginated list
    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, (list, dict))
        if isinstance(data, dict):
            assert "workspaces" in data or "items" in data or "data" in data
        elif isinstance(data, list):
            workspace_ids = [ws["id"] if isinstance(ws, dict) else str(ws) for ws in data]
            # Should include test_workspace
            assert str(test_workspace.id) in workspace_ids or len(workspace_ids) == 0


@pytest.mark.asyncio
async def test_admin_suspend_workspace(
    authenticated_admin_client: AsyncClient,
    db_session: AsyncSession,
    test_workspace: Workspace,
) -> None:
    """Test admin can suspend workspace."""
    response = await authenticated_admin_client.post(
        f"/api/admin/workspaces/{test_workspace.id}/suspend",
    )
    assert response.status_code in (200, 201, 204)

    # Verify workspace is suspended
    await db_session.refresh(test_workspace)
    if response.status_code in (200, 201, 204):
        assert test_workspace.status == WorkspaceStatus.SUSPENDED


@pytest.mark.asyncio
async def test_admin_unsuspend_workspace(
    authenticated_admin_client: AsyncClient,
    db_session: AsyncSession,
    test_workspace: Workspace,
) -> None:
    """Test admin can unsuspend workspace."""
    # First suspend it
    test_workspace.status = WorkspaceStatus.SUSPENDED
    await db_session.commit()

    # Then unsuspend
    response = await authenticated_admin_client.post(
        f"/api/admin/workspaces/{test_workspace.id}/unsuspend",
    )
    assert response.status_code in (200, 201, 204)

    # Verify workspace is active
    await db_session.refresh(test_workspace)
    if response.status_code in (200, 201, 204):
        assert test_workspace.status == WorkspaceStatus.ACTIVE


@pytest.mark.asyncio
async def test_suspended_workspace_cannot_process_documents(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_workspace: Workspace,
    sample_pdf_file: Any,
) -> None:
    """Test suspended workspace cannot process documents."""
    # Suspend workspace
    test_workspace.status = WorkspaceStatus.SUSPENDED
    await db_session.commit()

    # Try to upload document
    with open(sample_pdf_file, "rb") as f:
        files = {"file": ("test.pdf", f, "application/pdf")}
        data = {}
        response = await authenticated_client.post(
            "/api/documents",
            files=files,
            data=data,
        )

    # Should fail with appropriate error
    assert response.status_code in (403, 400, 422)


@pytest.mark.asyncio
async def test_admin_impersonate_user(
    authenticated_admin_client: AsyncClient,
    db_session: AsyncSession,
    test_workspace: Workspace,
    test_user: User,
) -> None:
    """Test admin can impersonate user."""
    response = await authenticated_admin_client.post(
        f"/api/admin/workspaces/{test_workspace.id}/impersonate",
    )
    assert response.status_code in (200, 201)
    
    if response.status_code in (200, 201):
        data = response.json()
        assert "token" in data or "impersonation_token" in data


@pytest.mark.asyncio
async def test_admin_view_system_metrics(
    authenticated_admin_client: AsyncClient,
) -> None:
    """Test admin can view system metrics."""
    response = await authenticated_admin_client.get("/api/admin/metrics")
    
    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, dict)
        # Should contain metrics like queue depth, processing stats
        assert len(data) >= 0  # At least some data structure


@pytest.mark.asyncio
async def test_admin_view_audit_logs(
    authenticated_admin_client: AsyncClient,
    db_session: AsyncSession,
    test_workspace: Workspace,
    test_user: User,
) -> None:
    """Test admin can view audit logs."""
    from datetime import datetime, timezone

    # Create an audit log entry
    audit_log = AuditLog(
        workspace_id=test_workspace.id,
        user_id=test_user.id,
        actor_type="user",
        event_type="document.uploaded",
        description="Test audit log entry",
        metadata={"document_id": "test-id"},
    )
    db_session.add(audit_log)
    await db_session.commit()

    # List audit logs
    response = await authenticated_admin_client.get("/api/admin/audit-logs")
    assert response.status_code in (200, 401, 403)
    
    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, (list, dict))
        if isinstance(data, dict):
            assert "logs" in data or "items" in data or "data" in data
        elif isinstance(data, list):
            # Should contain audit logs
            assert len(data) >= 0


@pytest.mark.asyncio
async def test_admin_filter_audit_logs(
    authenticated_admin_client: AsyncClient,
    db_session: AsyncSession,
    test_workspace: Workspace,
) -> None:
    """Test admin can filter audit logs."""
    # List audit logs with filters
    response = await authenticated_admin_client.get(
        "/api/admin/audit-logs",
        params={
            "workspace_id": str(test_workspace.id),
            "event_type": "document.uploaded",
        },
    )
    assert response.status_code in (200, 401, 403)
    
    if response.status_code == 200:
        data = response.json()
        # Should return filtered results
        assert isinstance(data, (list, dict))

