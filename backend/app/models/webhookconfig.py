import uuid
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base


class WebhookConfig(Base):
    """
    Webhook configuration for a workspace.

    Stores the target URL, signing secret, subscribed events, and retry policy.
    Used by the webhook delivery job worker to enqueue and send events such as
    extraction completion notifications.
    """

    __tablename__ = "webhook_configs"

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
    )

    target_url: Mapped[str] = mapped_column(
        String,
        nullable=False,
        doc="Absolute HTTPS URL to receive webhook deliveries.",
    )

    secret: Mapped[str] = mapped_column(
        String,
        nullable=False,
        doc="HMAC signing secret used to sign webhook payloads.",
    )

    events: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
        doc="Array of subscribed event types, e.g. ['extraction.completed'].",
    )

    retry_policy: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        doc="Retry/backoff configuration for failed deliveries.",
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="webhook_configs",
        lazy="joined",
    )

    deliveries: Mapped[List["WebhookDelivery"]] = relationship(
        "WebhookDelivery",
        back_populates="webhook_config",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def is_event_enabled(self, event_type: str) -> bool:
        """
        Check whether a given event type is enabled for this webhook.

        Args:
            event_type: The event type string to check.

        Returns:
            True if the event is subscribed and webhook is enabled, False otherwise.
        """
        if not self.enabled:
            return False
        if not self.events:
            return False
        return event_type in self.events