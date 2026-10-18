from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import UUID, JSON, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base


class ExtractionResult(Base):
    """
    Represents a single version of an extraction result for a document.

    This is multi-tenant via `workspace_id` and versioned per document/template
    so multiple extraction runs can be stored historically.
    """

    __tablename__ = "extraction_results"

    id: Mapped[uuid.UUID] = mapped_column(
        "id",
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Primary key for the extraction result.",
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        "document_id",
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Reference to the source document.",
    )

    template_id: Mapped[uuid.UUID] = mapped_column(
        "template_id",
        UUID(as_uuid=True),
        ForeignKey("templates.id", ondelete="RESTRICT"),
        nullable=False,
        doc="Reference to the template used for this extraction.",
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        "workspace_id",
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Workspace that owns this extraction result (for multi-tenancy).",
    )

    extracted_json: Mapped[Dict[str, Any]] = mapped_column(
        "extracted_json",
        JSON,
        nullable=False,
        doc="Structured extraction output as JSON (fields, values, nested data).",
    )

    version: Mapped[int] = mapped_column(
        "version",
        Integer,
        nullable=False,
        default=1,
        doc="Monotonic version number for this document/template pair.",
    )

    extraction_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
        doc="Extraction metadata including confidence, needs_review flag, field confidences, etc.",
    )

    created_at: Mapped[datetime] = mapped_column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        doc="Timestamp when this extraction result was created.",
    )

    # Relationships
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="extraction_results",
        lazy="joined",
        doc="The document this extraction result belongs to.",
    )

    template: Mapped["Template"] = relationship(
        "Template",
        lazy="joined",
        doc="The template used to generate this extraction.",
    )

    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        lazy="joined",
        doc="Workspace that owns this extraction result.",
    )

    def to_dict(self, include_extracted_json: bool = True) -> Dict[str, Any]:
        """
        Serialize the extraction result to a dictionary for API responses or logging.

        Args:
            include_extracted_json: When False, omits the heavy `extracted_json` payload.

        Returns:
            A dictionary representation of the extraction result.
        """
        data: Dict[str, Any] = {
            "id": str(self.id),
            "document_id": str(self.document_id),
            "template_id": str(self.template_id),
            "workspace_id": str(self.workspace_id),
            "version": self.version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_extracted_json:
            data["extracted_json"] = self.extracted_json
        if self.extraction_metadata:
            data["metadata"] = self.extraction_metadata
        return data


# Forward references for type checking (these are defined in their own modules)
from .document import Document  # noqa: E402  # isort: skip
from .template import Template  # noqa: E402  # isort: skip
from .workspace import Workspace  # noqa: E402  # isort: skip