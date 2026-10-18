from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.types import Enum as SAEnum

from . import Base


class GlobalUserRole(str, Enum):
    """Platform-wide user role.

    Workspace-specific roles (owner/member/readonly) live on WorkspaceMember.
    """

    ADMIN = "admin"
    USER = "user"


class AuthProvider(str, Enum):
    """Authentication provider used to create the user/account."""

    LOCAL = "local"
    GOOGLE = "google"


class User(Base):
    """User model representing a platform account.

    This is a global identity which can belong to multiple workspaces via
    WorkspaceMember. Authorization within a workspace is determined using
    WorkspaceMember.role; this model only stores platform-wide role.
    """

    __tablename__ = "users"

    id: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    email: str = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    password_hash: str = Column(
        String,
        nullable=False,
    )

    global_role: GlobalUserRole = Column(
        SAEnum(GlobalUserRole, name="global_user_role", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=GlobalUserRole.USER,
        server_default=GlobalUserRole.USER.value,
    )

    full_name: Optional[str] = Column(
        String(255),
        nullable=True,
    )

    is_email_verified: bool = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    is_active: bool = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    auth_provider: AuthProvider = Column(
        SAEnum(AuthProvider, name="auth_provider", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=AuthProvider.LOCAL,
        server_default=AuthProvider.LOCAL.value,
    )

    last_login_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    stripe_customer_id: Optional[str] = Column(
        String(255),
        nullable=True,
        index=True,
        doc="Stripe customer ID for billing. One customer per user.",
    )

    created_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default="now()",
    )

    updated_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default="now()",
    )

    # Relationships (string-based to avoid circular imports)
    workspace_memberships: List["WorkspaceMember"] = relationship(
        "WorkspaceMember",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    owned_workspaces: List["Workspace"] = relationship(
        "Workspace",
        back_populates="owner",
        foreign_keys="Workspace.owner_user_id",
    )

    notifications: List["Notification"] = relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    audit_logs: List["AuditLog"] = relationship(
        "AuditLog",
        back_populates="user",
        foreign_keys="AuditLog.user_id",
    )

    projects_created: List["Project"] = relationship(
        "Project",
        back_populates="created_by_user",
        foreign_keys="Project.created_by_user_id",
    )

    templates_created: List["Template"] = relationship(
        "Template",
        back_populates="created_by_user",
        foreign_keys="Template.created_by_user_id",
    )

    uploaded_documents: List["Document"] = relationship(
        "Document",
        back_populates="uploaded_by",
        foreign_keys="Document.uploaded_by_user_id",
    )

    subscriptions: List["Subscription"] = relationship(
        "Subscription",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        doc="User's subscriptions. Billing is per-user, not per-workspace.",
    )

    affiliate: Optional["Affiliate"] = relationship(
        "Affiliate",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
        doc="Affiliate account if user is a partner",
    )

    def __repr__(self) -> str:
        """Return string representation useful for debugging."""
        return f"<User id={self.id} email={self.email!r} role={self.global_role}>"