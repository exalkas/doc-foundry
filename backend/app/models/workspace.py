from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Enum as SAEnum

from . import Base


class WorkspaceStatus(str, Enum):
    """Status values for a workspace lifecycle."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    TRIAL = "trial"
    CANCELED = "canceled"


class Workspace(Base):
    """Represents a tenant workspace in the multi-tenant system."""

    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    stripe_customer_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True
    )

    status: Mapped[WorkspaceStatus] = mapped_column(
        SAEnum(WorkspaceStatus, name="workspace_status", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=WorkspaceStatus.TRIAL,
    )

    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    primary_color: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    custom_domain: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, unique=True, index=True
    )

    onboarding_completed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationships (lazy="raise" to catch accidental N+1, can be tuned per-query)
    owner: Mapped["User"] = relationship(
        "User",
        back_populates="owned_workspaces",
        lazy="raise",
    )

    members: Mapped[List["WorkspaceMember"]] = relationship(
        "WorkspaceMember",
        back_populates="workspace",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    projects: Mapped[List["Project"]] = relationship(
        "Project",
        back_populates="workspace",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    templates: Mapped[List["Template"]] = relationship(
        "Template",
        back_populates="workspace",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    documents: Mapped[List["Document"]] = relationship(
        "Document",
        back_populates="workspace",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    api_keys: Mapped[List["ApiKey"]] = relationship(
        "ApiKey",
        back_populates="workspace",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    webhook_configs: Mapped[List["WebhookConfig"]] = relationship(
        "WebhookConfig",
        back_populates="workspace",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    usage_records: Mapped[List["UsageRecord"]] = relationship(
        "UsageRecord",
        back_populates="workspace",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    webhook_deliveries: Mapped[List["WebhookDelivery"]] = relationship(
        "WebhookDelivery",
        back_populates="workspace",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="workspace",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    notifications: Mapped[List["Notification"]] = relationship(
        "Notification",
        back_populates="workspace",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<Workspace id={self.id} name={self.name!r} status={self.status}>"
