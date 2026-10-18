from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.types import Enum as SAEnum

from . import Base


class CouponStatus(str, Enum):
    """Coupon status."""

    ACTIVE = "active"
    PAUSED = "paused"
    EXPIRED = "expired"


class DiscountType(str, Enum):
    """Discount type."""

    PERCENTAGE = "percentage"
    FIXED = "fixed"


class DurationType(str, Enum):
    """Coupon duration type."""

    ONCE = "once"  # One-time discount
    FIRST_N_MONTHS = "first_n_months"  # Discount for first N months
    UNTIL_DATE = "until_date"  # Discount until expiration date


class Coupon(Base):
    """Coupon model for discount codes and affiliate promotions."""

    __tablename__ = "coupons"

    id: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    code: str = Column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        doc="Unique coupon code (case-insensitive, stored in lowercase)",
    )

    discount_type: DiscountType = Column(
        SAEnum(DiscountType, name="discount_type_enum", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        doc="Type of discount: percentage or fixed amount",
    )

    discount_value: float = Column(
        Numeric(10, 2),
        nullable=False,
        doc="Discount value: percentage (0-100) or fixed amount in currency units",
    )

    duration_type: DurationType = Column(
        SAEnum(DurationType, name="duration_type_enum", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=DurationType.ONCE,
        server_default="once",
        doc="How long the discount applies",
    )

    duration_months: Optional[int] = Column(
        Integer,
        nullable=True,
        doc="Number of months discount applies (for first_n_months duration)",
    )

    expires_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="Expiration date/time for the coupon",
    )

    max_redemptions: Optional[int] = Column(
        Integer,
        nullable=True,
        doc="Maximum number of times this coupon can be redeemed globally",
    )

    max_redemptions_per_customer: Optional[int] = Column(
        Integer,
        nullable=True,
        default=1,
        server_default="1",
        doc="Maximum number of times a single customer can redeem this coupon",
    )

    eligible_plans: List[str] = Column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
        doc="List of plan IDs this coupon applies to (empty = all plans)",
    )

    affiliate_id: Optional[uuid.UUID] = Column(
        UUID(as_uuid=True),
        ForeignKey("affiliates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Affiliate this coupon is linked to (for attribution)",
    )

    status: CouponStatus = Column(
        SAEnum(CouponStatus, name="coupon_status_enum", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=CouponStatus.ACTIVE,
        server_default="active",
        index=True,
        doc="Current status of the coupon",
    )

    stackable: bool = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        doc="Whether this coupon can be stacked with other coupons",
    )

    allow_lifetime_discount: bool = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        doc="Admin override flag to allow lifetime discounts (v1 default: false)",
    )

    metadata_json: Dict[str, any] = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        doc="Additional metadata (FB group name, campaign ID, etc.)",
    )

    created_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default="now()",
    )

    updated_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default="now()",
    )

    # Relationships
    affiliate: Optional["Affiliate"] = relationship(
        "Affiliate",
        back_populates="coupons",
        lazy="joined",
    )

    redemptions: List["CouponRedemption"] = relationship(
        "CouponRedemption",
        back_populates="coupon",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """Return string representation useful for debugging."""
        return f"<Coupon id={self.id} code={self.code!r} discount_type={self.discount_type.value} status={self.status.value}>"

