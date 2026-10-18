"""E2E-specific test fixtures."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import AsyncGenerator
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, GlobalUserRole
from app.models.workspace import Workspace, WorkspaceStatus
from app.models.workspacemember import WorkspaceMember, WorkspaceMemberRole, WorkspaceMemberStatus
from app.models.template import Template, ExportFormatEnum
from app.models.document import Document, DocumentStatusEnum, DocumentSourceEnum
from app.models.project import Project
from app.models.apikey import ApiKey, ApiKeyStatusEnum
from app.models.webhookconfig import WebhookConfig
from app.models.subscription import Subscription, SubscriptionPlanEnum, SubscriptionStatusEnum
from app.auth.dependencies import get_password_hash
from app.auth.utils import hash_api_key
from app.auth.dependencies import create_access_token, TokenType
from app.config import get_settings


# Alias for compatibility with existing tests
@pytest.fixture
async def async_client(client: AsyncClient) -> AsyncGenerator[AsyncClient, None]:
    """Alias for client fixture for compatibility."""
    yield client


@pytest.fixture
async def test_user(
    db_session: AsyncSession,
) -> AsyncGenerator[User, None]:
    """Create a test user."""
    user = User(
        email=f"test_{uuid4().hex[:8]}@example.com",
        password_hash=get_password_hash("TestPassword123!"),
        full_name="Test User",
        is_email_verified=True,
        global_role=GlobalUserRole.USER,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    yield user


@pytest.fixture
def user_password() -> str:
    """Return the test user password."""
    return "TestPassword123!"


@pytest.fixture
async def test_workspace(
    db_session: AsyncSession,
    test_user: User,
) -> AsyncGenerator[Workspace, None]:
    """Create a test workspace."""
    workspace = Workspace(
        name="Test Workspace",
        owner_user_id=test_user.id,
        status=WorkspaceStatus.ACTIVE,
    )
    db_session.add(workspace)
    await db_session.flush()
    await db_session.refresh(workspace)
    yield workspace


@pytest.fixture
async def test_workspace_member(
    db_session: AsyncSession,
    test_user: User,
    test_workspace: Workspace,
) -> AsyncGenerator[WorkspaceMember, None]:
    """Create a test workspace member."""
    member = WorkspaceMember(
        workspace_id=test_workspace.id,
        user_id=test_user.id,
        role=WorkspaceMemberRole.OWNER,
        status=WorkspaceMemberStatus.ACTIVE,
    )
    db_session.add(member)
    await db_session.commit()
    await db_session.refresh(member)
    yield member


@pytest.fixture
async def authenticated_client(
    app,
    test_user: User,
    test_workspace: Workspace,
    test_workspace_member: WorkspaceMember,
) -> AsyncGenerator[AsyncClient, None]:
    """Create an authenticated HTTP client."""
    settings = get_settings()
    
    # Create access token
    token = create_access_token(
        data={"sub": str(test_user.id), "workspace_id": str(test_workspace.id)},
        token_type=TokenType.SESSION,
    )
    
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        # Set authentication cookie
        client.cookies.set("access_token", token)
        # Set workspace cookie
        client.cookies.set("current_workspace_id", str(test_workspace.id))
        yield client


@pytest.fixture
async def admin_user(
    db_session: AsyncSession,
) -> AsyncGenerator[User, None]:
    """Create an admin user."""
    user = User(
        email=f"admin_{uuid4().hex[:8]}@example.com",
        password_hash=get_password_hash("AdminPassword123!"),
        full_name="Admin User",
        is_email_verified=True,
        global_role=GlobalUserRole.ADMIN,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    yield user


@pytest.fixture
async def admin_workspace(
    db_session: AsyncSession,
    admin_user: User,
) -> AsyncGenerator[Workspace, None]:
    """Create a workspace for admin user."""
    workspace = Workspace(
        name="Admin Workspace",
        owner_user_id=admin_user.id,
        status=WorkspaceStatus.ACTIVE,
    )
    db_session.add(workspace)
    await db_session.flush()
    
    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=admin_user.id,
        role=WorkspaceMemberRole.OWNER,
        status=WorkspaceMemberStatus.ACTIVE,
    )
    db_session.add(member)
    await db_session.commit()
    await db_session.refresh(workspace)
    yield workspace


@pytest.fixture
async def authenticated_admin_client(
    app,
    admin_user: User,
    admin_workspace: Workspace,
) -> AsyncGenerator[AsyncClient, None]:
    """Create an authenticated admin HTTP client."""
    settings = get_settings()
    
    token = create_access_token(
        data={"sub": str(admin_user.id), "workspace_id": str(admin_workspace.id)},
        token_type=TokenType.SESSION,
    )
    
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        client.cookies.set("access_token", token)
        client.cookies.set("current_workspace_id", str(admin_workspace.id))
        yield client


@pytest.fixture
async def test_project(
    db_session: AsyncSession,
    test_workspace: Workspace,
) -> AsyncGenerator[Project, None]:
    """Create a test project."""
    project = Project(
        name="Test Project",
        workspace_id=test_workspace.id,
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    yield project


@pytest.fixture
async def test_template(
    db_session: AsyncSession,
    test_workspace: Workspace,
    test_user: User,
) -> AsyncGenerator[Template, None]:
    """Create a test extraction template."""
    template = Template(
        workspace_id=test_workspace.id,
        name="Test Template",
        description="A test extraction template",
        document_type="invoice",
        field_schema={
            "vendor_name": {"type": "string", "required": True},
            "invoice_number": {"type": "string", "required": True},
            "total_amount": {"type": "number", "required": True},
            "date": {"type": "string", "required": False},
        },
        default_export_format=ExportFormatEnum.JSON,
        created_by_user_id=test_user.id,
    )
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)
    yield template


@pytest.fixture
async def test_document(
    db_session: AsyncSession,
    test_workspace: Workspace,
    test_user: User,
    test_template: Template,
) -> AsyncGenerator[Document, None]:
    """Create a test document."""
    # Create a temporary test file
    test_file_path = Path(tempfile.gettempdir()) / f"test_doc_{uuid4().hex[:8]}.pdf"
    test_file_path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\nxref\n0 0\ntrailer\n<<\n/Root 1 0 R\n>>\n%%EOF")
    
    document = Document(
        workspace_id=test_workspace.id,
        template_id=test_template.id,
        file_name="test_document.pdf",
        file_type="application/pdf",
        storage_path=str(test_file_path),
        pages=1,
        status=DocumentStatusEnum.PENDING,
        uploaded_by_user_id=test_user.id,
        source=DocumentSourceEnum.UI,
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    yield document
    
    # Cleanup
    if test_file_path.exists():
        test_file_path.unlink()


@pytest.fixture
async def test_api_key(
    db_session: AsyncSession,
    test_workspace: Workspace,
    test_user: User,
) -> AsyncGenerator[tuple[ApiKey, str], None]:
    """Create a test API key and return both the model and the plaintext key."""
    import secrets
    from app.auth.utils import hash_api_key
    
    # Generate API key similar to the router
    prefix = "dk_test"
    secret_part = secrets.token_urlsafe(32)
    full_key = f"{prefix}_{secret_part}"
    
    api_key = ApiKey(
        workspace_id=test_workspace.id,
        name="Test API Key",
        prefix=prefix,
        key_hash=hash_api_key(full_key),
        scopes=["documents:read", "documents:write"],
        status=ApiKeyStatusEnum.ACTIVE,
        created_by_user_id=test_user.id,
    )
    db_session.add(api_key)
    await db_session.commit()
    await db_session.refresh(api_key)
    yield api_key, full_key


@pytest.fixture
async def test_webhook_config(
    db_session: AsyncSession,
    test_workspace: Workspace,
    test_user: User,
) -> AsyncGenerator[WebhookConfig, None]:
    """Create a test webhook configuration."""
    webhook = WebhookConfig(
        workspace_id=test_workspace.id,
        url="https://example.com/webhook",
        secret="test_webhook_secret",
        events=["document.completed"],
        is_active=True,
        created_by_user_id=test_user.id,
    )
    db_session.add(webhook)
    await db_session.commit()
    await db_session.refresh(webhook)
    yield webhook


@pytest.fixture
async def test_subscription(
    db_session: AsyncSession,
    test_user: User,
    test_workspace: Workspace,
) -> AsyncGenerator[Subscription, None]:
    """Create a test subscription."""
    subscription = Subscription(
        user_id=test_user.id,
        workspace_id=test_workspace.id,
        plan=SubscriptionPlanEnum.STARTER,
        status=SubscriptionStatusEnum.ACTIVE,
        stripe_subscription_id=f"sub_test_{uuid4().hex[:8]}",
        stripe_customer_id=f"cus_test_{uuid4().hex[:8]}",
    )
    db_session.add(subscription)
    await db_session.commit()
    await db_session.refresh(subscription)
    yield subscription


@pytest.fixture
def mock_storage_dir(tmp_path: Path) -> Path:
    """Create a temporary storage directory for test files."""
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir


@pytest.fixture
def sample_pdf_file(tmp_path: Path) -> Path:
    """Create a sample PDF file for testing."""
    pdf_path = tmp_path / "sample.pdf"
    # Minimal valid PDF content
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\nxref\n0 0\ntrailer\n<<\n/Root 1 0 R\n>>\n%%EOF"
    pdf_path.write_bytes(pdf_content)
    return pdf_path


@pytest.fixture
def sample_image_file(tmp_path: Path) -> Path:
    """Create a sample image file for testing."""
    from PIL import Image as PILImage
    
    img_path = tmp_path / "sample.png"
    # Create a simple 1x1 pixel image
    img = PILImage.new("RGB", (1, 1), color="white")
    img.save(img_path, "PNG")
    return img_path

