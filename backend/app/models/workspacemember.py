from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    UUID,
    CheckConstraint,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base

if TYPE_CHECKING:  # pragma: no cover
    from .user import User
    from .workspace import Workspace


class WorkspaceMemberRole(str, Enum):
    """Workspace-scoped role for a user."""

    OWNER = "owner"
    MEMBER = "member"
    READONLY = "readonly"


class WorkspaceMemberStatus(str, Enum):
    """Membership lifecycle status."""

    PENDING = "pending"
    ACTIVE = "active"
    REVOKED = "revoked"


class WorkspaceMember(Base):
    """Association table linking users to workspaces with a scoped role.

    This model powers multi-tenant membership and per-workspace permissions.
    """

    __tablename__ = "workspace_members"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        doc="Primary key.",
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key to workspaces.id.",
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key to users.id.",
    )

    role: Mapped[WorkspaceMemberRole] = mapped_column(
        SAEnum(
            WorkspaceMemberRole,
            name="workspace_member_role_enum",
            native_enum=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        doc="Role of the user within this workspace.",
    )

    status: Mapped[WorkspaceMemberStatus] = mapped_column(
        SAEnum(
            WorkspaceMemberStatus,
            name="workspace_member_status_enum",
            native_enum=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=WorkspaceMemberStatus.PENDING,
        server_default=WorkspaceMemberStatus.PENDING.value,
        doc="Current membership status.",
    )

    invited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
        doc="Timestamp when the invitation was created.",
    )

    joined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when the user accepted the invitation and joined.",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
        doc="Creation timestamp.",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
        doc="Last update timestamp.",
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="members",
        lazy="joined",
        doc="Associated workspace.",
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="workspace_memberships",
        lazy="joined",
        doc="Associated user.",
    )

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "user_id",
            name="uq_workspace_member_workspace_user",
        ),
        CheckConstraint(
            "role IN ('owner', 'member', 'readonly')",
            name="ck_workspace_member_role_valid",
        ),
        CheckConstraint(
            "status IN ('pending', 'active', 'revoked')",
            name="ck_workspace_member_status_valid",
        ),
    )

    def __repr__(self) -> str:
        """Return a concise string representation for debugging."""
        return (
            f"WorkspaceMember(id={self.id}, workspace_id={self.workspace_id}, "
            f"user_id={self.user_id}, role={self.role}, status={self.status})"
        )

    def is_owner(self) -> bool:
        """Return True if the member is an owner of the workspace."""
        return self.role == WorkspaceMemberRole.OWNER

    def is_active(self) -> bool:
        """Return True if the membership is active."""
        return self.status == WorkspaceMemberStatus.ACTIVE