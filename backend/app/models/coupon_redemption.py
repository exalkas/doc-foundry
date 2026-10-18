from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from . import Base


class CouponRedemption(Base):
    """Coupon redemption model tracking coupon usage."""

    __tablename__ = "coupon_redemptions"

    id: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    coupon_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("coupons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Coupon that was redeemed",
    )

    customer_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Customer who redeemed the coupon",
    )

    subscription_id: Optional[uuid.UUID] = Column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Subscription this coupon was applied to",
    )

    used_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default="now()",
        index=True,
        doc="When the coupon was redeemed",
    )

    discount_applied: float = Column(
        Numeric(10, 2),
        nullable=False,
        doc="Amount of discount that was applied (in currency units)",
    )

    # Relationships
    coupon: "Coupon" = relationship(
        "Coupon",
        back_populates="redemptions",
        lazy="joined",
    )

    customer: "User" = relationship(
        "User",
        foreign_keys=[customer_id],
        lazy="joined",
    )

    subscription: Optional["Subscription"] = relationship(
        "Subscription",
        lazy="joined",
    )

    def __repr__(self) -> str:
        """Return string representation useful for debugging."""
        return f"<CouponRedemption id={self.id} coupon_id={self.coupon_id} customer_id={self.customer_id} used_at={self.used_at}>"

