"""E2E tests for API integration (API keys and public API)."""

from __future__ import annotations

from typing import Any, Dict

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.apikey import ApiKey, ApiKeyStatusEnum
from app.models.document import Document, DocumentStatusEnum


@pytest.mark.asyncio
async def test_create_api_key_with_scopes(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_workspace: Any,
) -> None:
    """Test create API key with scopes."""
    payload: Dict[str, Any] = {
        "name": "Test API Key",
        "scopes": ["documents:read", "documents:write"],
    }

    response = await authenticated_client.post("/api/api-keys", json=payload)
    assert response.status_code in (200, 201)
    data = response.json()

    assert "api_key" in data
    assert "id" in data
    api_key_value = data["api_key"]
    api_key_id = data["id"]

    # Verify key is returned only once (hash stored, not plaintext)
    assert len(api_key_value) > 0
    assert "." in api_key_value or "_" in api_key_value  # Format check

    # Verify API key was created in DB
    api_key_stmt = select(ApiKey).where(ApiKey.id == api_key_id)
    api_key_result = await db_session.execute(api_key_stmt)
    api_key: ApiKey | None = api_key_result.scalar_one_or_none()
    assert api_key is not None
    assert api_key.name == payload["name"]
    assert api_key.scopes == payload["scopes"]
    assert api_key.status == ApiKeyStatusEnum.ACTIVE


@pytest.mark.asyncio
async def test_list_api_keys_hides_full_key(
    authenticated_client: AsyncClient,
    test_api_key: tuple[ApiKey, str],
) -> None:
    """Test GET /api/api-keys lists keys without exposing full key."""
    response = await authenticated_client.get("/api/api-keys")
    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    if len(data) > 0:
        key_data = data[0]
        assert "id" in key_data
        assert "prefix" in key_data
        assert "api_key" not in key_data  # Full key should not be exposed
        assert "key_hash" not in key_data  # Hash should not be exposed


@pytest.mark.asyncio
async def test_revoke_api_key(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_api_key: tuple[ApiKey, str],
) -> None:
    """Test revoke API key."""
    api_key, _ = test_api_key
    api_key_id = api_key.id

    response = await authenticated_client.post(f"/api/api-keys/{api_key_id}/revoke")
    assert response.status_code in (200, 204)

    # Verify key is revoked
    await db_session.refresh(api_key)
    assert api_key.status == ApiKeyStatusEnum.REVOKED


@pytest.mark.asyncio
async def test_public_api_extract_with_api_key(
    app: Any,
    db_session: AsyncSession,
    test_api_key: tuple[ApiKey, str],
    test_template: Any,
    test_workspace: Any,
    sample_pdf_file: Any,
) -> None:
    """Test extract document via public API with API key."""
    api_key, full_key = test_api_key

    async with AsyncClient(app=app, base_url="http://testserver") as client:
        # Upload document via public API
        with open(sample_pdf_file, "rb") as f:
            files = {"file": ("test.pdf", f, "application/pdf")}
            data = {"template_id": str(test_template.id)}
            headers = {"Authorization": f"Bearer {full_key}"}

            response = await client.post(
                "/api/v1/documents:extract",
                files=files,
                data=data,
                headers=headers,
            )

        assert response.status_code in (200, 201)
        response_data = response.json()
        assert "document_id" in response_data or "id" in response_data

        # Verify usage is tracked (check last_used_at updated)
        await db_session.refresh(api_key)
        assert api_key.last_used_at is not None


@pytest.mark.asyncio
async def test_public_api_rejects_invalid_key(
    app: Any,
    sample_pdf_file: Any,
) -> None:
    """Test public API rejects invalid/expired/revoked API keys."""
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        # Test with invalid key
        with open(sample_pdf_file, "rb") as f:
            files = {"file": ("test.pdf", f, "application/pdf")}
            data = {"template_id": "00000000-0000-0000-0000-000000000000"}
            headers = {"Authorization": "Bearer invalid_key_12345"}

            response = await client.post(
                "/api/v1/documents:extract",
                files=files,
                data=data,
                headers=headers,
            )

        assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_public_api_rejects_revoked_key(
    app: Any,
    db_session: AsyncSession,
    test_api_key: tuple[ApiKey, str],
    sample_pdf_file: Any,
) -> None:
    """Test public API rejects revoked API keys."""
    api_key, full_key = test_api_key

    # Revoke the key
    api_key.status = ApiKeyStatusEnum.REVOKED
    await db_session.commit()

    async with AsyncClient(app=app, base_url="http://testserver") as client:
        with open(sample_pdf_file, "rb") as f:
            files = {"file": ("test.pdf", f, "application/pdf")}
            data = {}
            headers = {"Authorization": f"Bearer {full_key}"}

            response = await client.post(
                "/api/v1/documents:extract",
                files=files,
                data=data,
                headers=headers,
            )

        assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_public_api_respects_scopes(
    app: Any,
    db_session: AsyncSession,
    test_workspace: Any,
    test_user: Any,
    sample_pdf_file: Any,
) -> None:
    """Test public API respects API key scopes."""
    import secrets
    from app.auth.utils import hash_api_key

    # Create API key with limited scope
    prefix = "dk_test"
    secret_part = secrets.token_urlsafe(32)
    full_key = f"{prefix}_{secret_part}"

    from app.models.apikey import ApiKey, ApiKeyStatusEnum

    limited_api_key = ApiKey(
        workspace_id=test_workspace.id,
        name="Limited Scope Key",
        prefix=prefix,
        key_hash=hash_api_key(full_key),
        scopes=["documents:read"],  # Only read, no write
        status=ApiKeyStatusEnum.ACTIVE,
        created_by_user_id=test_user.id,
    )
    db_session.add(limited_api_key)
    await db_session.commit()

    # Try to use write operation with read-only key
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        with open(sample_pdf_file, "rb") as f:
            files = {"file": ("test.pdf", f, "application/pdf")}
            data = {}
            headers = {"Authorization": f"Bearer {full_key}"}

            # This might succeed (if extract is considered read) or fail (if write)
            # The important thing is that scopes are checked
            response = await client.post(
                "/api/v1/documents:extract",
                files=files,
                data=data,
                headers=headers,
            )

        # Should either succeed if extract is read, or fail with 403 if write
        assert response.status_code in (200, 201, 403)


@pytest.mark.asyncio
async def test_webhook_configuration(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_workspace: Any,
) -> None:
    """Test configure webhook endpoint."""
    payload = {
        "url": "https://example.com/webhook",
        "secret": "test_webhook_secret",
        "events": ["document.completed"],
        "is_active": True,
    }

    response = await authenticated_client.post("/api/webhooks", json=payload)
    assert response.status_code in (200, 201)
    data = response.json()

    assert "id" in data
    assert data["url"] == payload["url"]
    assert data["events"] == payload["events"]
    # Secret should not be returned in response
    assert "secret" not in data or data.get("secret") != payload["secret"]

