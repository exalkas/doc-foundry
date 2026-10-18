from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from sqlalchemy import (
    JSON,
    UUID,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base
from .workspace import Workspace  # noqa: F401  # imported for type checking / relationships
from .webhookconfig import WebhookConfig  # noqa: F401


class WebhookDeliveryStatus(str, Enum):
    """Enumeration of possible webhook delivery states."""

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class WebhookDelivery(Base):
    """
    Represents a single attempt (or logical delivery record) of sending a webhook event
    to an external system.

    This model is used both for operational retry logic (via jobs) and for
    user-facing observability in the dashboard.
    """

    __tablename__ = "webhook_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
        doc="Primary key for the webhook delivery.",
    )

    webhook_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("webhook_configs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        doc="Foreign key to the webhook configuration used for this delivery.",
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        doc="Workspace that owns this webhook delivery (multi-tenant scoping).",
    )

    event_type: Mapped[str] = mapped_column(
        String(length=255),
        nullable=False,
        doc="Type of event delivered (e.g. 'extraction.completed').",
    )

    payload: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        doc="JSON payload that was sent to the target webhook endpoint.",
    )

    status_code: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="HTTP status code returned by the webhook target, if any.",
    )

    delivery_status: Mapped[WebhookDeliveryStatus] = mapped_column(
        SQLEnum(
            WebhookDeliveryStatus,
            name="webhook_delivery_status_enum",
        ),
        nullable=False,
        default=WebhookDeliveryStatus.PENDING,
        server_default=WebhookDeliveryStatus.PENDING.value,
        doc="Logical status of this delivery (pending/succeeded/failed).",
    )

    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        doc="Number of attempts that have been made to deliver this webhook.",
    )

    last_error: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True,
        doc="Last error message encountered when attempting delivery, if any.",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        doc="Timestamp when this delivery record was created.",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        onupdate=datetime.utcnow,
        doc="Timestamp when this delivery record was last updated.",
    )

    # Relationships
    webhook_config: Mapped["WebhookConfig"] = relationship(
        "WebhookConfig",
        back_populates="deliveries",
        lazy="joined",
        doc="The webhook configuration associated with this delivery.",
    )

    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="webhook_deliveries",
        lazy="joined",
        doc="Workspace that owns this webhook delivery.",
    )

    def mark_succeeded(self, status_code: int) -> None:
        """
        Mark this webhook delivery as successfully delivered.

        Args:
            status_code: HTTP status code returned by the target endpoint.
        """
        self.delivery_status = WebhookDeliveryStatus.SUCCEEDED
        self.status_code = status_code
        self.last_error = None

    def mark_failed(self, error_message: str, status_code: Optional[int] = None) -> None:
        """
        Mark this webhook delivery as failed, storing error context.

        Args:
            error_message: Description of the error encountered.
            status_code: Optional HTTP status code returned by target.
        """
        self.delivery_status = WebhookDeliveryStatus.FAILED
        self.last_error = error_message
        if status_code is not None:
            self.status_code = status_code

    def increment_attempts(self) -> None:
        """
        Increment the attempt counter for this delivery.

        This should be called each time a new delivery attempt is made.
        """
        self.attempt_count += 1