from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from sqlalchemy import JSON, Column, DateTime, Enum as SQLEnum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base


class AuditActorTypeEnum(str, Enum):  # type: ignore[misc]
    """Enumerates the type of actor that generated the audit event."""

    USER = "user"
    SYSTEM = "system"


class AuditLog(Base):
    """Represents a single immutable audit log entry.

    Audit logs capture security- and compliance-relevant events such as logins,
    configuration changes, billing updates, and API usage. Logs may be scoped
    to a workspace and/or a user, but system-wide events (e.g., admin actions)
    can omit one or both.
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        doc="Primary key for the audit log entry.",
    )

    workspace_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Optional workspace associated with this event (null for global/system events).",
    )

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Optional user associated with this event (null for system actors).",
    )

    actor_type: Mapped[AuditActorTypeEnum] = mapped_column(
        SQLEnum(AuditActorTypeEnum, name="audit_actor_type_enum"),
        nullable=False,
        doc="Indicates whether the actor was an authenticated user or a system process.",
    )

    event_type: Mapped[str] = mapped_column(
        String(length=128),
        nullable=False,
        doc="Machine-readable event key, e.g. 'login', 'billing_update', 'api_key_used'.",
    )

    description: Mapped[str] = mapped_column(
        String(length=1024),
        nullable=False,
        doc="Human-readable summary of the event suitable for display in the UI.",
    )

    event_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        name="metadata",
        doc="Optional structured context (IDs, previous values, IP/user agent, etc.).",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        doc="Timestamp when the audit event was recorded.",
    )

    # Relationships
    workspace: Mapped[Optional["Workspace"]] = relationship(
        "Workspace",
        back_populates="audit_logs",
        lazy="joined",
    )
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="audit_logs",
        lazy="joined",
    )

    def to_safe_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable representation without sensitive internal details.

        This is suitable for returning from public APIs and ensures the shape
        is stable and free of ORM-specific attributes.
        """
        return {
            "id": str(self.id),
            "workspace_id": str(self.workspace_id) if self.workspace_id else None,
            "user_id": str(self.user_id) if self.user_id else None,
            "actor_type": self.actor_type.value,
            "event_type": self.event_type,
            "description": self.description,
            "metadata": self.event_metadata or {},
            "created_at": self.created_at.isoformat(),
        }