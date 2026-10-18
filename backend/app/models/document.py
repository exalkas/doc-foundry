from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Index,
    JSON,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.types import Enum as SAEnum

from . import Base


class DocumentStatusEnum(str, Enum):  # type: ignore[misc]
    """Enumeration of document processing statuses."""

    PENDING = "pending"
    PROCESSING = "processing"
    SCANNED = "scanned"  # OCR completed, waiting for template application
    COMPLETED = "completed"  # Extraction completed with template
    FAILED = "failed"


class DocumentSourceEnum(str, Enum):  # type: ignore[misc]
    """Enumeration of document upload sources."""

    UI = "ui"
    API = "api"


class Document(Base):
    """
    Represents an uploaded document within a workspace.

    Documents are processed asynchronously via the job queue to produce
    ExtractionResult records and accompanying ExtractionLog entries.
    """

    __tablename__ = "documents"

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

    # Optional project linkage
    project_id: Mapped[Optional[uuid.UUID]] = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Optional template linkage (may be chosen at upload time or inferred later)
    template_id: Mapped[Optional[uuid.UUID]] = Column(
        UUID(as_uuid=True),
        ForeignKey("templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # File metadata
    file_name: Mapped[str] = Column(String, nullable=False)
    file_type: Mapped[str] = Column(String(128), nullable=False)
    storage_path: Mapped[str] = Column(String, nullable=False)
    pages: Mapped[Optional[int]] = Column(Integer, nullable=True)

    # Processing status
    status: Mapped[DocumentStatusEnum] = mapped_column(
        SAEnum(
            DocumentStatusEnum,
            name="document_status_enum",
            native_enum=True,
            create_type=False,  # Use existing PostgreSQL enum type
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )

    # Uploader
    uploaded_by_user_id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )

    # Upload source (UI vs API)
    source: Mapped[DocumentSourceEnum] = mapped_column(
        SAEnum(
            DocumentSourceEnum,
            name="document_source_enum",
            native_enum=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )

    # Error and callback
    last_error: Mapped[Optional[str]] = Column(Text, nullable=True)
    callback_url: Mapped[Optional[str]] = Column(String, nullable=True)

    # Raw OCR extraction (when no template is provided)
    raw_ocr_text: Mapped[Optional[str]] = Column(Text, nullable=True)
    raw_ocr_metadata: Mapped[Optional[dict]] = Column(JSON, nullable=True)
    
    # OCR language code (e.g., 'eng', 'ell' for Greek, 'fra' for French)
    # Defaults to 'eng' if not specified
    ocr_language: Mapped[Optional[str]] = Column(String(10), nullable=True, default="eng")

    # Timestamps
    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    deleted_at: Mapped[Optional[datetime]] = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="documents",
        lazy="joined",
    )

    project: Mapped[Optional["Project"]] = relationship(
        "Project",
        back_populates="documents",
        lazy="selectin",
    )

    template: Mapped[Optional["Template"]] = relationship(
        "Template",
        back_populates="documents",
        lazy="selectin",
    )

    uploaded_by: Mapped["User"] = relationship(
        "User",
        back_populates="uploaded_documents",
        lazy="joined",
        foreign_keys=[uploaded_by_user_id],
    )

    extraction_results: Mapped[List["ExtractionResult"]] = relationship(
        "ExtractionResult",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    extraction_logs: Mapped[List["ExtractionLog"]] = relationship(
        "ExtractionLog",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """Return string representation for debugging."""
        return (
            f"<Document id={self.id} workspace_id={self.workspace_id} "
            f"file_name={self.file_name!r} status={self.status}>"
        )


# Index to support frequent lookups by workspace + status
Index(
    "ix_documents_workspace_status",
    Document.workspace_id,
    Document.status,
)

# Index to support project-based filtering within a workspace
Index(
    "ix_documents_workspace_project",
    Document.workspace_id,
    Document.project_id,
)