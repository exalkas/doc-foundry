from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.types import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, relationship

from . import Base


class ExportFormatEnum(str, Enum):
    """Enum representing supported default export formats for a template."""

    JSON = "json"
    CSV = "csv"
    EXCEL = "excel"


class Template(Base):
    """Extraction template definition.

    Templates belong to a workspace and optionally a project. They describe
    how to map document contents into structured JSON fields and how exports
    should be generated.
    """

    __tablename__ = "templates"

    id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    # Multi-tenant scoping
    workspace_id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Optional project association
    project_id: Mapped[Optional[uuid.UUID]] = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Optional library template source
    library_template_id: Mapped[Optional[uuid.UUID]] = Column(
        UUID(as_uuid=True),
        ForeignKey("template_library.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Basic metadata
    name: Mapped[str] = Column(String(255), nullable=False)
    description: Mapped[Optional[str]] = Column(Text, nullable=True)
    document_type: Mapped[Optional[str]] = Column(String(128), nullable=True)

    # Schema describing fields, types, validation, etc.
    # Stored as JSONB in Postgres via SQLAlchemy's JSON type.
    field_schema: Mapped[Dict[str, Any]] = Column(JSON, nullable=False)

    default_export_format: Mapped[ExportFormatEnum] = Column(
        SAEnum(
            ExportFormatEnum,
            name="export_format_enum",
            native_enum=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ExportFormatEnum.JSON,
    )

    created_by_user_id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )

    # Usage statistics
    last_run_at: Mapped[Optional[datetime]] = Column(DateTime(timezone=True), nullable=True)
    success_count: Mapped[int] = Column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = Column(Integer, nullable=False, default=0)

    # Timestamps
    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships (string-based to avoid circular imports)
    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="templates",
        lazy="joined",
    )

    project: Mapped[Optional["Project"]] = relationship(
        "Project",
        back_populates="templates",
        lazy="selectin",
    )

    created_by_user: Mapped["User"] = relationship(
        "User",
        back_populates="templates_created",
        lazy="joined",
    )

    documents: Mapped[List["Document"]] = relationship(
        "Document",
        back_populates="template",
        lazy="selectin",
        cascade="all,delete-orphan",
        passive_deletes=True,
    )

    extraction_results: Mapped[List["ExtractionResult"]] = relationship(
        "ExtractionResult",
        back_populates="template",
        lazy="selectin",
        cascade="all,delete-orphan",
        passive_deletes=True,
    )

    library_template: Mapped[Optional["TemplateLibrary"]] = relationship(
        "TemplateLibrary",
        back_populates="imported_templates",
        lazy="selectin",
    )

    def increment_success_count(self) -> None:
        """Increment the success counter safely in application code.

        Note: For high-concurrency scenarios, consider doing this with an
        atomic UPDATE statement at the repository/service layer instead of
        relying solely on in-memory increments.
        """
        self.success_count = (self.success_count or 0) + 1

    def increment_failure_count(self) -> None:
        """Increment the failure counter safely in application code."""
        self.failure_count = (self.failure_count or 0) + 1


# Helpful composite indexes for common access patterns
Index(
    "ix_templates_workspace_project",
    Template.workspace_id,
    Template.project_id,
)

Index(
    "ix_templates_workspace_name",
    Template.workspace_id,
    Template.name,
)