from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SQLEnum, Integer, JSON, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, declarative_mixin, mapped_column

from . import Base


@declarative_mixin
class TimestampMixin:
    """Mixin providing created_at and updated_at columns with automatic defaults."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class JobType(str, Enum):
    """Enumeration of supported job types."""

    DOCUMENT_EXTRACTION = "document_extraction"
    WEBHOOK_DELIVERY = "webhook_delivery"
    TEMPLATE_GENERATION = "template_generation"


class JobStatus(str, Enum):
    """Enumeration of possible job statuses."""

    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Job(TimestampMixin, Base):
    """Represents a background job in the system.

    Used as a simple DB-backed queue for document extraction and webhook delivery.
    Jobs are polled and processed by a separate worker process.
    """

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    type: Mapped[JobType] = mapped_column(
        SQLEnum(JobType, name="job_type_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )

    payload: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        doc="Opaque job payload; structure depends on job type.",
    )

    status: Mapped[JobStatus] = mapped_column(
        SQLEnum(JobStatus, name="job_status_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        server_default=JobStatus.QUEUED.value,
        index=True,
    )

    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )

    max_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="5",
    )

    last_error: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        doc="When this job becomes eligible for processing (for retries/backoff).",
    )

    def can_retry(self) -> bool:
        """Return True if the job is eligible for another processing attempt."""
        return self.attempts < self.max_attempts and self.status in {
            JobStatus.QUEUED,
            JobStatus.FAILED,
        }

    def mark_processing(self) -> None:
        """Mark the job as currently being processed."""
        self.status = JobStatus.PROCESSING  # type: ignore[assignment]

    def mark_succeeded(self) -> None:
        """Mark the job as successfully completed."""
        self.status = JobStatus.SUCCEEDED  # type: ignore[assignment]
        self.last_error = None

    def mark_failed(self, error_message: str | None = None) -> None:
        """Mark the job as failed and optionally store an error message."""
        self.status = JobStatus.FAILED  # type: ignore[assignment]
        if error_message:
            # Truncate overly long error messages to avoid unbounded growth.
            self.last_error = error_message[:2000]
        self.attempts += 1