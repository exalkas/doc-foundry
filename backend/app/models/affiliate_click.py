from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from . import Base


class AffiliateClick(Base):
    """Affiliate click tracking model with privacy-preserving hashing."""

    __tablename__ = "affiliate_clicks"

    id: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    affiliate_link_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("affiliate_links.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Affiliate link that was clicked",
    )

    ip_hash: str = Column(
        String(64),
        nullable=True,
        doc="Hashed IP address for privacy",
    )

    user_agent_hash: str = Column(
        String(64),
        nullable=True,
        doc="Hashed user agent for privacy",
    )

    referrer: str = Column(
        String(512),
        nullable=True,
        doc="HTTP referrer URL",
    )

    timestamp: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default="now()",
        index=True,
        doc="When the click occurred",
    )

    # Relationships
    affiliate_link: "AffiliateLink" = relationship(
        "AffiliateLink",
        back_populates="clicks",
        lazy="joined",
    )

    def __repr__(self) -> str:
        """Return string representation useful for debugging."""
        return f"<AffiliateClick id={self.id} affiliate_link_id={self.affiliate_link_id} timestamp={self.timestamp}>"

