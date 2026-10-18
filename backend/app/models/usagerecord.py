from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base

if TYPE_CHECKING:
    from .workspace import Workspace


class UsageRecord(Base):
    """
    Daily usage metering record for a workspace.

    This model stores aggregated counts of documents and pages processed per
    workspace per calendar date. It is used for usage analytics, plan
    enforcement, and billing calculations.

    A unique constraint on (workspace_id, date) ensures that there is at most
    one record per workspace per day. Upserts/aggregation logic should update
    the existing record for a given date instead of inserting duplicates.
    """

    __tablename__ = "usage_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        doc="Primary key identifier for the usage record.",
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key to the workspace this usage record belongs to.",
    )

    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        doc="Calendar date (UTC) this usage record corresponds to.",
    )

    documents_processed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        doc="Number of documents processed on this date for the workspace.",
    )

    pages_processed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        doc="Number of pages processed on this date for the workspace.",
    )

    ai_pages_processed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        doc="Number of AI extraction pages processed on this date for the workspace.",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp when this usage record was created.",
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="usage_records",
        doc="Workspace that owns this usage record.",
    )

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "date",
            name="uq_usage_record_workspace_date",
        ),
    )

    def __repr__(self) -> str:
        """Return a concise string representation of the usage record."""
        return (
            f"<UsageRecord id={self.id} workspace_id={self.workspace_id} "
            f"date={self.date} documents={self.documents_processed} "
            f"pages={self.pages_processed} ai_pages={self.ai_pages_processed}>"
        )