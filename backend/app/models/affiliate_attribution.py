from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.types import Enum as SAEnum

from . import Base


class AttributionSource(str, Enum):
    """Source of affiliate attribution."""

    LINK = "link"
    COUPON = "coupon"


class AffiliateAttribution(Base):
    """Affiliate attribution model linking customers to affiliates."""

    __tablename__ = "affiliate_attributions"

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
        doc="Affiliate that referred this customer",
    )

    affiliate_link_id: Optional[uuid.UUID] = Column(
        UUID(as_uuid=True),
        ForeignKey("affiliate_links.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Specific link used (if applicable)",
    )

    customer_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        doc="Customer that was referred",
    )

    attribution_source: AttributionSource = Column(
        SAEnum(AttributionSource, name="attribution_source_enum", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=AttributionSource.LINK,
        server_default="link",
        doc="How the attribution was established",
    )

    first_attributed_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default="now()",
        doc="When attribution was first established",
    )

    last_attributed_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default="now()",
        doc="When attribution was last updated",
    )

    # Relationships
    affiliate: "Affiliate" = relationship(
        "Affiliate",
        back_populates="attributions",
        lazy="joined",
    )

    affiliate_link: Optional["AffiliateLink"] = relationship(
        "AffiliateLink",
        back_populates="attributions",
        lazy="joined",
    )

    customer: "User" = relationship(
        "User",
        foreign_keys=[customer_id],
        lazy="joined",
    )

    def __repr__(self) -> str:
        """Return string representation useful for debugging."""
        return f"<AffiliateAttribution id={self.id} affiliate_id={self.affiliate_id} customer_id={self.customer_id}>"

