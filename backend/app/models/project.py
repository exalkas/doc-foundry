from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base


class Project(Base):
    """
    Project model representing a logical folder for organizing documents and templates
    within a workspace.

    This is a multi-tenant entity scoped by `workspace_id`.
    """

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Workspace that owns this project (multi-tenant scope).",
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Human-readable project name.",
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Optional longer description of the project.",
    )

    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        doc="User who created the project.",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        doc="Timestamp when the project was created.",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        doc="Timestamp when the project was last updated.",
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="projects",
        lazy="joined",
    )

    created_by_user: Mapped["User"] = relationship(
        "User",
        back_populates="projects_created",
        lazy="joined",
    )

    documents: Mapped[List["Document"]] = relationship(
        "Document",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    templates: Mapped[List["Template"]] = relationship(
        "Template",
        back_populates="project",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Project id={self.id} workspace_id={self.workspace_id} name={self.name!r}>"