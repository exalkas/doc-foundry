from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from sqlalchemy import JSON, Column, DateTime, Enum as SQLEnum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, declarative_mixin, mapped_column, relationship

from . import Base


class ExtractionLogLevel(str, Enum):
    """Log severity levels for document extraction pipeline."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@declarative_mixin
class TimestampMixin:
    """Mixin providing created_at timestamp column."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )


class ExtractionLog(Base, TimestampMixin):
    """Represents a single log entry produced during document extraction.

    These logs power the 'Logs' tab in the Extraction Preview UI and are useful
    for debugging extraction issues as well as providing transparency to users.
    """

    __tablename__ = "extraction_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    level: Mapped[ExtractionLogLevel] = mapped_column(
        SQLEnum(ExtractionLogLevel, name="extraction_log_level", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ExtractionLogLevel.INFO,
    )

    message: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    event_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        name="metadata",
    )

    # Relationships
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="extraction_logs",
        lazy="joined",
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the log entry to a plain dictionary for JSON responses."""
        return {
            "id": str(self.id),
            "document_id": str(self.document_id),
            "level": self.level.value,
            "message": self.message,
            "metadata": self.event_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }