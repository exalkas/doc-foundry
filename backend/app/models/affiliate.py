from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.types import Enum as SAEnum

from . import Base


class AffiliateStatus(str, Enum):
    """Affiliate account status."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    BLOCKED = "blocked"


class Affiliate(Base):
    """Affiliate (partner) model representing a referral partner."""

    __tablename__ = "affiliates"

    id: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    user_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        doc="User account linked to this affiliate",
    )

    slug: str = Column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        doc="Unique slug for affiliate links (e.g., 'alkis42')",
    )

    status: AffiliateStatus = Column(
        SAEnum(AffiliateStatus, name="affiliate_status_enum", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=AffiliateStatus.PENDING,
        server_default="pending",
        index=True,
        doc="Current status of the affiliate account",
    )

    commission_plan_id: Optional[uuid.UUID] = Column(
        UUID(as_uuid=True),
        ForeignKey("commission_plans.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Commission plan assigned to this affiliate",
    )

    company_name: Optional[str] = Column(
        String(255),
        nullable=True,
        doc="Company or brand name",
    )

    website: Optional[str] = Column(
        String(512),
        nullable=True,
        doc="Website URL",
    )

    payment_method_type: Optional[str] = Column(
        String(50),
        nullable=True,
        doc="Payment method type (e.g., 'paypal', 'wise')",
    )

    payment_details: Optional[str] = Column(
        Text,
        nullable=True,
        doc="Encrypted payment details (PayPal email, Wise details, etc.)",
    )

    country: Optional[str] = Column(
        String(100),
        nullable=True,
        doc="Country code or name",
    )

    tax_id: Optional[str] = Column(
        String(100),
        nullable=True,
        doc="Tax identification number",
    )

    notes: Optional[str] = Column(
        Text,
        nullable=True,
        doc="Admin notes about this affiliate",
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
    user: "User" = relationship(
        "User",
        back_populates="affiliate",
        lazy="joined",
    )

    commission_plan: Optional["CommissionPlan"] = relationship(
        "CommissionPlan",
        back_populates="affiliates",
        lazy="selectin",
    )

    links: List["AffiliateLink"] = relationship(
        "AffiliateLink",
        back_populates="affiliate",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    attributions: List["AffiliateAttribution"] = relationship(
        "AffiliateAttribution",
        back_populates="affiliate",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    commissions: List["Commission"] = relationship(
        "Commission",
        back_populates="affiliate",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    payouts: List["Payout"] = relationship(
        "Payout",
        back_populates="affiliate",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    coupons: List["Coupon"] = relationship(
        "Coupon",
        back_populates="affiliate",
        cascade="all, delete-orphan",
        lazy="select",  # Changed from selectin to select to avoid eager loading on refresh
    )

    def __repr__(self) -> str:
        """Return string representation useful for debugging."""
        return f"<Affiliate id={self.id} slug={self.slug!r} status={self.status.value}>"

