"""Affiliate service for managing affiliate accounts and operations."""

import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.affiliate import Affiliate, AffiliateStatus
from app.models.commission_plan import CommissionPlan
from app.models.user import User
from app.services.logging_service import get_logger

logger = get_logger(__name__)

# Configuration from environment
AFFILIATE_EARLY_ACCESS_LIMIT = int(os.getenv("AFFILIATE_EARLY_ACCESS_LIMIT", "20"))


class AffiliateService:
    """Service for affiliate management operations."""

    @staticmethod
    async def apply_to_become_affiliate(
        db: AsyncSession,
        user: User,
        company_name: Optional[str] = None,
        website: Optional[str] = None,
        country: Optional[str] = None,
    ) -> Affiliate:
        """Create an affiliate application for a user."""
        logger.info(f"User {user.id} applying to become affiliate")

        # Check if user already has an affiliate account
        existing = await db.execute(
            select(Affiliate).where(Affiliate.user_id == user.id)
        )
        if existing.scalar_one_or_none():
            raise ValueError("User already has an affiliate account")

        # Generate unique slug from user email or ID
        slug_base = user.email.split("@")[0].lower().replace(".", "").replace("_", "")[:20]
        slug = slug_base
        counter = 1
        
        # Ensure slug is unique
        while True:
            existing_slug = await db.execute(
                select(Affiliate).where(Affiliate.slug == slug)
            )
            if not existing_slug.scalar_one_or_none():
                break
            slug = f"{slug_base}{counter}"
            counter += 1

        # Get default commission plan (Standard)
        plan_result = await db.execute(
            select(CommissionPlan).where(
                CommissionPlan.name == "Standard",
                CommissionPlan.is_active == True
            )
        )
        commission_plan = plan_result.scalar_one_or_none()
        
        if not commission_plan:
            raise ValueError("Default commission plan not found")

        # Check if we're within early access limit
        approved_count = await db.execute(
            select(func.count(Affiliate.id)).where(
                Affiliate.status == AffiliateStatus.APPROVED
            )
        )
        approved_count_value = approved_count.scalar() or 0
        
        # Create affiliate with pending status
        affiliate = Affiliate(
            user_id=user.id,
            slug=slug,
            status=AffiliateStatus.PENDING,
            commission_plan_id=commission_plan.id,
            company_name=company_name,
            website=website,
            country=country,
        )

        db.add(affiliate)
        try:
            await db.commit()
            # Refresh only scalar attributes to avoid loading relationships
            await db.refresh(affiliate)
            logger.info(f"Created affiliate application {affiliate.id} for user {user.id}")
            return affiliate
        except IntegrityError as e:
            await db.rollback()
            logger.error(f"Failed to create affiliate: {e}")
            raise ValueError("Failed to create affiliate account") from e

    @staticmethod
    async def get_affiliate_by_user_id(
        db: AsyncSession,
        user_id: UUID,
    ) -> Optional[Affiliate]:
        """Get affiliate by user ID."""
        result = await db.execute(
            select(Affiliate).where(Affiliate.user_id == user_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_affiliate_by_slug(
        db: AsyncSession,
        slug: str,
    ) -> Optional[Affiliate]:
        """Get affiliate by slug."""
        result = await db.execute(
            select(Affiliate).where(Affiliate.slug == slug)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def approve_affiliate(
        db: AsyncSession,
        affiliate_id: UUID,
        admin_notes: Optional[str] = None,
    ) -> Affiliate:
        """Approve an affiliate application."""
        result = await db.execute(
            select(Affiliate).where(Affiliate.id == affiliate_id)
        )
        affiliate = result.scalar_one_or_none()
        
        if not affiliate:
            raise ValueError("Affiliate not found")

        if affiliate.status == AffiliateStatus.APPROVED:
            logger.warning(f"Affiliate {affiliate_id} already approved")
            return affiliate

        affiliate.status = AffiliateStatus.APPROVED
        if admin_notes:
            affiliate.notes = admin_notes
        affiliate.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(affiliate)
        logger.info(f"Approved affiliate {affiliate_id}")
        return affiliate

    @staticmethod
    async def reject_affiliate(
        db: AsyncSession,
        affiliate_id: UUID,
        admin_notes: Optional[str] = None,
    ) -> Affiliate:
        """Reject an affiliate application."""
        result = await db.execute(
            select(Affiliate).where(Affiliate.id == affiliate_id)
        )
        affiliate = result.scalar_one_or_none()
        
        if not affiliate:
            raise ValueError("Affiliate not found")

        affiliate.status = AffiliateStatus.REJECTED
        if admin_notes:
            affiliate.notes = admin_notes
        affiliate.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(affiliate)
        logger.info(f"Rejected affiliate {affiliate_id}")
        return affiliate

    @staticmethod
    async def block_affiliate(
        db: AsyncSession,
        affiliate_id: UUID,
        admin_notes: Optional[str] = None,
    ) -> Affiliate:
        """Block an affiliate account."""
        result = await db.execute(
            select(Affiliate).where(Affiliate.id == affiliate_id)
        )
        affiliate = result.scalar_one_or_none()
        
        if not affiliate:
            raise ValueError("Affiliate not found")

        affiliate.status = AffiliateStatus.BLOCKED
        if admin_notes:
            affiliate.notes = admin_notes
        affiliate.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(affiliate)
        logger.info(f"Blocked affiliate {affiliate_id}")
        return affiliate

    @staticmethod
    async def update_affiliate_profile(
        db: AsyncSession,
        affiliate: Affiliate,
        company_name: Optional[str] = None,
        website: Optional[str] = None,
        payment_method_type: Optional[str] = None,
        payment_details: Optional[str] = None,
        country: Optional[str] = None,
        tax_id: Optional[str] = None,
    ) -> Affiliate:
        """Update affiliate profile information."""
        if company_name is not None:
            affiliate.company_name = company_name
        if website is not None:
            affiliate.website = website
        if payment_method_type is not None:
            affiliate.payment_method_type = payment_method_type
        if payment_details is not None:
            # In production, encrypt this before storing
            affiliate.payment_details = payment_details
        if country is not None:
            affiliate.country = country
        if tax_id is not None:
            affiliate.tax_id = tax_id

        affiliate.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(affiliate)
        logger.info(f"Updated affiliate profile {affiliate.id}")
        return affiliate

    @staticmethod
    async def get_affiliate_stats(
        db: AsyncSession,
        affiliate_id: UUID,
    ) -> Dict[str, any]:
        """Get statistics for an affiliate."""
        from app.models.affiliate_link import AffiliateLink
        from app.models.affiliate_click import AffiliateClick
        from app.models.affiliate_attribution import AffiliateAttribution
        from app.models.commission import Commission, CommissionStatus

        # Get affiliate
        result = await db.execute(
            select(Affiliate).where(Affiliate.id == affiliate_id)
        )
        affiliate = result.scalar_one_or_none()
        if not affiliate:
            raise ValueError("Affiliate not found")

        # Count clicks
        clicks_result = await db.execute(
            select(func.count(AffiliateClick.id))
            .join(AffiliateLink)
            .where(AffiliateLink.affiliate_id == affiliate_id)
        )
        total_clicks = clicks_result.scalar() or 0

        # Count signups (attributions)
        signups_result = await db.execute(
            select(func.count(AffiliateAttribution.id))
            .where(AffiliateAttribution.affiliate_id == affiliate_id)
        )
        total_signups = signups_result.scalar() or 0

        # Count paying customers (attributions with subscriptions)
        from app.models.subscription import Subscription, SubscriptionStatusEnum
        paying_result = await db.execute(
            select(func.count(func.distinct(AffiliateAttribution.customer_id)))
            .join(User, AffiliateAttribution.customer_id == User.id)
            .join(Subscription, Subscription.user_id == User.id)
            .where(
                AffiliateAttribution.affiliate_id == affiliate_id,
                Subscription.status.in_([SubscriptionStatusEnum.ACTIVE, SubscriptionStatusEnum.TRIALING])
            )
        )
        paying_customers = paying_result.scalar() or 0

        # Calculate earnings
        commissions_result = await db.execute(
            select(
                func.sum(Commission.amount).label("total"),
                func.sum(
                    case(
                        (Commission.status == CommissionStatus.PENDING, Commission.amount),
                        else_=0
                    )
                ).label("pending"),
                func.sum(
                    case(
                        (Commission.status == CommissionStatus.CLEARED, Commission.amount),
                        else_=0
                    )
                ).label("cleared"),
                func.sum(
                    case(
                        (Commission.status == CommissionStatus.PAID, Commission.amount),
                        else_=0
                    )
                ).label("paid"),
            )
            .where(Commission.affiliate_id == affiliate_id)
        )
        earnings = commissions_result.first()
        
        total_earned = float(earnings.total or 0) if earnings else 0.0
        pending_earned = float(earnings.pending or 0) if earnings else 0.0
        cleared_earned = float(earnings.cleared or 0) if earnings else 0.0
        paid_earned = float(earnings.paid or 0) if earnings else 0.0

        # Calculate MRR (Monthly Recurring Revenue generated)
        mrr_result = await db.execute(
            select(func.sum(Commission.amount))
            .join(Subscription, Commission.subscription_id == Subscription.id)
            .where(
                Commission.affiliate_id == affiliate_id,
                Commission.status != CommissionStatus.REVERSED,
                Subscription.status.in_([SubscriptionStatusEnum.ACTIVE, SubscriptionStatusEnum.TRIALING])
            )
        )
        mrr = float(mrr_result.scalar() or 0)

        return {
            "affiliate_id": str(affiliate_id),
            "status": affiliate.status.value,
            "total_clicks": total_clicks,
            "total_signups": total_signups,
            "paying_customers": paying_customers,
            "total_earned": total_earned,
            "pending_earned": pending_earned,
            "cleared_earned": cleared_earned,
            "paid_earned": paid_earned,
            "mrr_generated": mrr,
        }

