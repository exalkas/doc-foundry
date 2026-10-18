from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import (
    UUID,
    Boolean,
    Column,
    DateTime,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from . import Base

if TYPE_CHECKING:
    pass


class Plan(Base):
    """Represents a subscription plan available for workspaces.

    Plans are stored in the database to allow for dynamic management
    without code changes. Plans define pricing, features, and Stripe
    integration details.
    """

    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Primary key for the plan record.",
    )

    plan_id: Mapped[str] = mapped_column(
        String(length=50),
        unique=True,
        nullable=False,
        index=True,
        doc="Unique plan identifier (e.g., 'free', 'basic', 'pro', 'enterprise').",
    )

    name: Mapped[str] = mapped_column(
        String(length=100),
        nullable=False,
        doc="Display name for the plan (e.g., 'Free', 'Basic', 'Pro').",
    )

    price: Mapped[float] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=0,
        doc="Monthly price in USD. 0 for free or custom pricing plans.",
    )

    interval: Mapped[str] = mapped_column(
        String(length=20),
        nullable=False,
        default="month",
        doc="Billing interval: 'month' or 'year'.",
    )

    stripe_price_id: Mapped[str | None] = mapped_column(
        String(length=255),
        nullable=True,
        index=True,
        doc="Stripe price ID (price_...) for this plan. NULL for free/enterprise plans.",
    )

    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        index=True,
        doc="Order for displaying plans (lower numbers appear first).",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        doc="Whether this plan is currently available for subscription.",
    )

    features: Mapped[List[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        doc="List of feature strings describing what's included in this plan.",
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

    def to_dict(self) -> dict:
        """Convert plan to dictionary format compatible with existing API."""
        return {
            "id": self.plan_id,
            "name": self.name,
            "price": float(self.price),
            "interval": self.interval,
            "stripe_price_id": self.stripe_price_id or "",
            "features": self.features if isinstance(self.features, list) else [],
        }

