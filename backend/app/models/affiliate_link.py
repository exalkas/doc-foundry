from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from . import Base


class AffiliateLink(Base):
    """Affiliate link model for tracking unique referral links."""

    __tablename__ = "affiliate_links"

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
        doc="Affiliate that owns this link",
    )

    slug: str = Column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        doc="Unique slug for this link (used in /r/{slug})",
    )

    destination_url: str = Column(
        String(512),
        nullable=False,
        default="/",
        server_default="/",
        doc="Destination URL to redirect to (default: homepage)",
    )

    campaign_id: Optional[str] = Column(
        String(100),
        nullable=True,
        doc="Optional campaign identifier for A/B testing or tracking",
    )

    created_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default="now()",
    )

    # Relationships
    affiliate: "Affiliate" = relationship(
        "Affiliate",
        back_populates="links",
        lazy="joined",
    )

    clicks: List["AffiliateClick"] = relationship(
        "AffiliateClick",
        back_populates="affiliate_link",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    attributions: List["AffiliateAttribution"] = relationship(
        "AffiliateAttribution",
        back_populates="affiliate_link",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """Return string representation useful for debugging."""
        return f"<AffiliateLink id={self.id} slug={self.slug!r} affiliate_id={self.affiliate_id}>"

