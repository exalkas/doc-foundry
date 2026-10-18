from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, Column, DateTime, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from . import Base


class CommissionPlan(Base):
    """Commission plan model defining commission rates and rules."""

    __tablename__ = "commission_plans"

    id: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    name: str = Column(
        String(255),
        unique=True,
        nullable=False,
        doc="Plan name (e.g., 'Standard', 'VIP')",
    )

    percentage: float = Column(
        Numeric(5, 2),
        nullable=False,
        doc="Commission percentage (0-100)",
    )

    duration_months: int = Column(
        Integer,
        nullable=False,
        doc="Number of months commission is paid (from customer's first payment)",
    )

    is_recurring: bool = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        doc="Whether commission is recurring or one-time",
    )

    allowed_plans: List[str] = Column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
        doc="List of subscription plan IDs this commission applies to",
    )

    is_active: bool = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        doc="Whether this commission plan is currently active",
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
    affiliates: List["Affiliate"] = relationship(
        "Affiliate",
        back_populates="commission_plan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """Return string representation useful for debugging."""
        return f"<CommissionPlan id={self.id} name={self.name!r} percentage={self.percentage}%>"

