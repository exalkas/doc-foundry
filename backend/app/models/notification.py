from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from sqlalchemy import UUID, JSON, Column, DateTime, Enum as SQLEnum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base


class NotificationChannel(str, Enum):
    """Supported notification delivery channels."""

    EMAIL = "email"
    IN_APP = "in_app"


class Notification(Base):
    """
    Notification model representing user-facing notifications.

    Supports both email and in-app channels. Workspaces are optional to allow for
    cross-workspace or global notifications, but most notifications will be scoped
    to a single workspace for multi-tenant isolation and querying.
    """

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    workspace_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="SET NULL"),
        nullable=True,
    )

    channel: Mapped[NotificationChannel] = mapped_column(
        SQLEnum(NotificationChannel, name="notification_channel"),
        nullable=False,
    )

    event_type: Mapped[str] = mapped_column(
        String(length=128),
        nullable=False,
        doc="Identifier for the triggering event, e.g. 'payment_failed'.",
    )

    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        doc="Structured payload used to render the notification.",
    )

    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when the notification was marked as read.",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    # Relationships (lazy='selectin' typically used in async contexts; can be configured in session)
    user: Mapped["User"] = relationship(
        "User",
        back_populates="notifications",
        lazy="selectin",
    )

    workspace: Mapped[Optional["Workspace"]] = relationship(
        "Workspace",
        back_populates="notifications",
        lazy="selectin",
    )

    __table_args__ = (
        Index(
            "ix_notifications_user_unread",
            "user_id",
            "read_at",
        ),
        Index(
            "ix_notifications_workspace_created_at",
            "workspace_id",
            "created_at",
        ),
    )

    def mark_read(self, when: Optional[datetime] = None) -> None:
        """
        Mark the notification as read.

        :param when: Optional datetime; defaults to current UTC time.
        """
        self.read_at = when or datetime.utcnow()


# Avoid circular import issues in type checking / runtime
from .user import User  # noqa: E402  # isort: skip
from .workspace import Workspace  # noqa: E402  # isort: skip

# Back-populate relationships on related models if not already defined.
# NOTE: These attributes should be referenced in the corresponding model files
# via back_populates="notifications" for symmetry.
if not hasattr(User, "notifications"):
    User.notifications = relationship(  # type: ignore[attr-defined]
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

if not hasattr(Workspace, "notifications"):
    Workspace.notifications = relationship(  # type: ignore[attr-defined]
        "Notification",
        back_populates="workspace",
        cascade="all, delete-orphan",
        lazy="selectin",
    )