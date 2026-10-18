"""Attribution service for tracking affiliate referrals."""

import hashlib
import logging
import os
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.affiliate import Affiliate
from app.models.affiliate_attribution import AffiliateAttribution, AttributionSource
from app.models.affiliate_link import AffiliateLink
from app.models.user import User
from app.services.logging_service import get_logger

logger = get_logger(__name__)

# Configuration from environment
AFFILIATE_ATTRIBUTION_WINDOW_DAYS = int(os.getenv("AFFILIATE_ATTRIBUTION_WINDOW_DAYS", "60"))
AFFILIATE_COOKIE_NAME = os.getenv("AFFILIATE_COOKIE_NAME", "aff_id")


class AttributionService:
    """Service for handling affiliate attribution."""

    @staticmethod
    def hash_ip(ip: str) -> str:
        """Hash IP address for privacy."""
        return hashlib.sha256(ip.encode()).hexdigest()

    @staticmethod
    def hash_user_agent(user_agent: str) -> str:
        """Hash user agent for privacy."""
        return hashlib.sha256(user_agent.encode()).hexdigest()

    @staticmethod
    async def track_click(
        db: AsyncSession,
        affiliate_link_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        referrer: Optional[str] = None,
    ) -> None:
        """Track an affiliate link click."""
        from app.models.affiliate_click import AffiliateClick

        click = AffiliateClick(
            affiliate_link_id=affiliate_link_id,
            ip_hash=AttributionService.hash_ip(ip_address) if ip_address else None,
            user_agent_hash=AttributionService.hash_user_agent(user_agent) if user_agent else None,
            referrer=referrer,
        )

        db.add(click)
        await db.commit()
        logger.debug(f"Tracked click for affiliate_link {affiliate_link_id}")

    @staticmethod
    async def attribute_customer(
        db: AsyncSession,
        customer_id: UUID,
        affiliate_id: Optional[UUID] = None,
        affiliate_link_id: Optional[UUID] = None,
        attribution_source: AttributionSource = AttributionSource.LINK,
    ) -> Optional[AffiliateAttribution]:
        """Attribute a customer to an affiliate."""
        if not affiliate_id:
            return None

        # Check if customer already has an attribution
        existing = await db.execute(
            select(AffiliateAttribution).where(
                AffiliateAttribution.customer_id == customer_id
            )
        )
        existing_attribution = existing.scalar_one_or_none()

        if existing_attribution:
            # Update last_attributed_at but keep original affiliate
            existing_attribution.last_attributed_at = datetime.utcnow()
            await db.commit()
            await db.refresh(existing_attribution)
            logger.info(
                f"Customer {customer_id} already attributed to affiliate {existing_attribution.affiliate_id}"
            )
            return existing_attribution

        # Verify affiliate exists and is approved
        affiliate_result = await db.execute(
            select(Affiliate).where(Affiliate.id == affiliate_id)
        )
        affiliate = affiliate_result.scalar_one_or_none()

        if not affiliate:
            logger.warning(f"Affiliate {affiliate_id} not found for attribution")
            return None

        from app.models.affiliate import AffiliateStatus
        if affiliate.status != AffiliateStatus.APPROVED:
            logger.warning(
                f"Affiliate {affiliate_id} is not approved (status: {affiliate.status.value})"
            )
            return None

        # Create attribution
        attribution = AffiliateAttribution(
            affiliate_id=affiliate_id,
            affiliate_link_id=affiliate_link_id,
            customer_id=customer_id,
            attribution_source=attribution_source,
        )

        db.add(attribution)
        await db.commit()
        await db.refresh(attribution)
        logger.info(
            f"Attributed customer {customer_id} to affiliate {affiliate_id} via {attribution_source.value}"
        )
        return attribution

    @staticmethod
    async def get_attribution_for_customer(
        db: AsyncSession,
        customer_id: UUID,
    ) -> Optional[AffiliateAttribution]:
        """Get affiliate attribution for a customer."""
        result = await db.execute(
            select(AffiliateAttribution).where(
                AffiliateAttribution.customer_id == customer_id
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_affiliate_from_cookie(
        db: AsyncSession,
        cookie_value: str,
    ) -> Optional[Affiliate]:
        """Get affiliate from cookie value (slug)."""
        from app.models.affiliate import AffiliateStatus
        result = await db.execute(
            select(Affiliate).where(
                Affiliate.slug == cookie_value,
                Affiliate.status == AffiliateStatus.APPROVED
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def attribute_via_coupon(
        db: AsyncSession,
        customer_id: UUID,
        coupon_id: UUID,
    ) -> Optional[AffiliateAttribution]:
        """
        Attribute a customer to an affiliate via coupon.
        Coupon-based attribution overrides cookie-based attribution (as per spec).
        """
        from app.models.coupon import Coupon
        
        # Get coupon
        coupon_result = await db.execute(
            select(Coupon).where(Coupon.id == coupon_id)
        )
        coupon = coupon_result.scalar_one_or_none()
        
        if not coupon:
            logger.warning(f"Coupon {coupon_id} not found for attribution")
            return None
        
        if not coupon.affiliate_id:
            logger.debug(f"Coupon {coupon_id} is not linked to an affiliate")
            return None
        
        # Check for existing attribution
        existing = await db.execute(
            select(AffiliateAttribution).where(
                AffiliateAttribution.customer_id == customer_id
            )
        )
        existing_attribution = existing.scalar_one_or_none()
        
        # If coupon attribution exists, it overrides cookie attribution
        if existing_attribution:
            if existing_attribution.attribution_source == AttributionSource.COUPON:
                # Already attributed via coupon, just update timestamp
                existing_attribution.last_attributed_at = datetime.utcnow()
                await db.commit()
                await db.refresh(existing_attribution)
                logger.info(
                    f"Customer {customer_id} already attributed via coupon to affiliate {existing_attribution.affiliate_id}"
                )
                return existing_attribution
            else:
                # Override cookie attribution with coupon attribution
                logger.info(
                    f"Overriding {existing_attribution.attribution_source.value} attribution "
                    f"with coupon attribution for customer {customer_id}"
                )
                existing_attribution.affiliate_id = coupon.affiliate_id
                existing_attribution.affiliate_link_id = None  # No link for coupon attribution
                existing_attribution.attribution_source = AttributionSource.COUPON
                existing_attribution.first_attributed_at = datetime.utcnow()
                existing_attribution.last_attributed_at = datetime.utcnow()
                await db.commit()
                await db.refresh(existing_attribution)
                return existing_attribution
        
        # Create new attribution
        return await AttributionService.attribute_customer(
            db=db,
            customer_id=customer_id,
            affiliate_id=coupon.affiliate_id,
            affiliate_link_id=None,
            attribution_source=AttributionSource.COUPON,
        )

