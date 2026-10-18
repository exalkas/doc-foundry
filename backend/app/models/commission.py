from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.types import Enum as SAEnum

from . import Base


class CommissionStatus(str, Enum):
    """Commission status."""

    PENDING = "pending"
    CLEARED = "cleared"
    PAID = "paid"
    REVERSED = "reversed"


class CommissionEventType(str, Enum):
    """Type of commission event."""

    INITIAL = "initial"
    RENEWAL = "renewal"
    UPGRADE = "upgrade"


class Commission(Base):
    """Commission model tracking affiliate earnings."""

    __tablename__ = "commissions"

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
        doc="Affiliate earning this commission",
    )

    customer_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Customer subscription generating this commission",
    )

    subscription_id: Optional[uuid.UUID] = Column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Subscription associated with this commission",
    )

    event_type: CommissionEventType = Column(
        SAEnum(CommissionEventType, name="commission_event_type_enum", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        doc="Type of commission event",
    )

    amount: float = Column(
        Numeric(10, 2),
        nullable=False,
        doc="Commission amount in currency units",
    )

    currency: str = Column(
        String(3),
        nullable=False,
        default="EUR",
        server_default="EUR",
        doc="Currency code (ISO 4217)",
    )

    status: CommissionStatus = Column(
        SAEnum(CommissionStatus, name="commission_status_enum", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=CommissionStatus.PENDING,
        server_default="pending",
        index=True,
        doc="Current status of the commission",
    )

    event_date: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default="now()",
        index=True,
        doc="Date of the commission event",
    )

    cleared_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="When commission was cleared (after hold period)",
    )

    payout_id: Optional[uuid.UUID] = Column(
        UUID(as_uuid=True),
        ForeignKey("payouts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Payout this commission was included in",
    )

    notes: Optional[str] = Column(
        Text,
        nullable=True,
        doc="Admin notes about this commission",
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
        back_populates="commissions",
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

    payout: Optional["Payout"] = relationship(
        "Payout",
        back_populates="commissions",
        lazy="joined",
    )

    __table_args__ = (
        CheckConstraint("amount >= 0", name="commissions_amount_non_negative"),
    )

    def __repr__(self) -> str:
        """Return string representation useful for debugging."""
        return f"<Commission id={self.id} affiliate_id={self.affiliate_id} amount={self.amount} {self.currency} status={self.status.value}>"

