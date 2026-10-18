from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.types import Enum as SAEnum

from . import Base


class PayoutStatus(str, Enum):
    """Payout status."""

    REQUESTED = "requested"
    APPROVED = "approved"
    PAID = "paid"
    REJECTED = "rejected"


class Payout(Base):
    """Payout model for affiliate payment requests."""

    __tablename__ = "payouts"

    id: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    affiliate_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("affiliates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Affiliate requesting this payout",
    )

    amount: float = Column(
        Numeric(10, 2),
        nullable=False,
        doc="Payout amount in currency units",
    )

    currency: str = Column(
        String(3),
        nullable=False,
        default="EUR",
        server_default="EUR",
        doc="Currency code (ISO 4217)",
    )

    status: PayoutStatus = Column(
        SAEnum(PayoutStatus, name="payout_status_enum", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=PayoutStatus.REQUESTED,
        server_default="requested",
        index=True,
        doc="Current status of the payout",
    )

    requested_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default="now()",
        index=True,
        doc="When payout was requested",
    )

    processed_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="When payout was processed (approved/paid/rejected)",
    )

    payment_method: Optional[str] = Column(
        String(50),
        nullable=True,
        doc="Payment method used (e.g., 'paypal', 'wise')",
    )

    payment_reference: Optional[str] = Column(
        String(255),
        nullable=True,
        doc="Payment reference number or transaction ID",
    )

    notes: Optional[str] = Column(
        Text,
        nullable=True,
        doc="Admin notes about this payout",
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
    affiliate: "Affiliate" = relationship(
        "Affiliate",
        back_populates="payouts",
        lazy="joined",
    )

    commissions: List["Commission"] = relationship(
        "Commission",
        back_populates="payout",
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="payouts_amount_positive"),
    )

    def __repr__(self) -> str:
        """Return string representation useful for debugging."""
        return f"<Payout id={self.id} affiliate_id={self.affiliate_id} amount={self.amount} {self.currency} status={self.status.value}>"

