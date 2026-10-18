from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    UUID,
    Boolean,
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

if TYPE_CHECKING:
    from .user import User
    from .workspace import Workspace


class SubscriptionPlanEnum(str, Enum):
    """Supported subscription plans."""

    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class SubscriptionStatusEnum(str, Enum):
    """Stripe-aligned subscription status for a workspace."""

    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    TRIALING = "trialing"


class Subscription(Base):
    """Represents a Stripe-backed subscription for a user.

    Billing is per-user, not per-workspace. A user may have multiple historical
    Subscription rows, but typically only one active/trialing subscription at a time.
    Stripe is the source of truth; this model mirrors key fields for quick lookup
    and usage/billing logic.
    """

    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Primary key for the subscription record.",
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="User this subscription belongs to. Billing is per-user.",
    )

    workspace_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        doc="DEPRECATED: Kept for historical tracking. Use user_id instead.",
    )

    stripe_subscription_id: Mapped[str] = mapped_column(
        String(length=255),
        nullable=False,
        unique=True,
        doc="Stripe subscription ID (sub_...).",
    )

    plan_id: Mapped[SubscriptionPlanEnum] = mapped_column(
        SAEnum(SubscriptionPlanEnum, name="subscription_plan_enum", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        doc="Internal plan identifier (e.g. basic, pro).",
    )

    status: Mapped[SubscriptionStatusEnum] = mapped_column(
        SAEnum(SubscriptionStatusEnum, name="subscription_status_enum", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        doc="Current status of the subscription as reported by Stripe.",
    )

    current_period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        doc="Start of the current billing period (from Stripe).",
    )

    current_period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        doc="End of the current billing period (from Stripe).",
    )

    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        default=False,
        doc="If true, subscription will cancel at end of the current period.",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Record creation timestamp.",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Last update timestamp.",
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="subscriptions",
        lazy="joined",
        doc="User that owns this subscription.",
    )

    __table_args__ = (
        # Ensure a user cannot have duplicate rows for the same Stripe subscription.
        UniqueConstraint(
            "user_id",
            "stripe_subscription_id",
            name="uq_user_stripe_subscription",
        ),
    )

    def is_active(self, at: datetime | None = None) -> bool:
        """Return True if the subscription is considered active at the given time.

        This helper is intentionally business-logic-light; the canonical status
        comes from Stripe. We treat both ACTIVE and TRIALING as usable
        subscriptions, provided the current time falls within the current period.
        """
        if self.status not in {SubscriptionStatusEnum.ACTIVE, SubscriptionStatusEnum.TRIALING}:
            return False

        now = at or datetime.utcnow()
        # current_period_start/end are expected to be timezone-aware in UTC;
        # for safety, compare via naive UTC if tzinfo is missing.
        cps = self.current_period_start
        cpe = self.current_period_end

        if cps.tzinfo is not None:
            cps = cps.astimezone(tz=None).replace(tzinfo=None)
        if cpe.tzinfo is not None:
            cpe = cpe.astimezone(tz=None).replace(tzinfo=None)

        now_naive = now.replace(tzinfo=None)
        return cps <= now_naive <= cpe