"""Commission service for calculating and managing affiliate commissions."""

import logging
import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.affiliate import Affiliate
from app.models.affiliate_attribution import AffiliateAttribution
from app.models.commission import Commission, CommissionStatus, CommissionEventType
from app.models.commission_plan import CommissionPlan
from app.models.subscription import Subscription
from app.services.logging_service import get_logger

logger = get_logger(__name__)

# Configuration from environment
AFFILIATE_HOLD_PERIOD_DAYS = int(os.getenv("AFFILIATE_HOLD_PERIOD_DAYS", "30"))


class CommissionService:
    """Service for commission calculation and management."""

    @staticmethod
    async def calculate_commission_rate(
        db: AsyncSession,
        affiliate_id: UUID,
    ) -> float:
        """Get commission rate for an affiliate."""
        result = await db.execute(
            select(Affiliate)
            .join(CommissionPlan)
            .where(Affiliate.id == affiliate_id)
        )
        affiliate = result.scalar_one_or_none()

        if not affiliate or not affiliate.commission_plan:
            logger.warning(f"Affiliate {affiliate_id} or commission plan not found")
            return 0.0

        return float(affiliate.commission_plan.percentage)

    @staticmethod
    async def create_commission(
        db: AsyncSession,
        affiliate_id: UUID,
        customer_id: UUID,
        subscription_id: UUID,
        subscription_amount: float,
        currency: str = "EUR",
        event_type: CommissionEventType = CommissionEventType.INITIAL,
    ) -> Commission:
        """Create a commission record for a subscription payment."""
        # Get attribution
        attribution_result = await db.execute(
            select(AffiliateAttribution).where(
                AffiliateAttribution.customer_id == customer_id,
                AffiliateAttribution.affiliate_id == affiliate_id,
            )
        )
        attribution = attribution_result.scalar_one_or_none()

        if not attribution:
            raise ValueError(f"No attribution found for customer {customer_id} and affiliate {affiliate_id}")

        # Get commission rate
        commission_rate = await CommissionService.calculate_commission_rate(db, affiliate_id)
        if commission_rate == 0:
            raise ValueError(f"Commission rate is 0 for affiliate {affiliate_id}")

        # Calculate commission amount
        commission_amount = Decimal(str(subscription_amount)) * Decimal(str(commission_rate)) / Decimal("100")

        # Check if commission already exists for this subscription and event type
        existing = await db.execute(
            select(Commission).where(
                Commission.affiliate_id == affiliate_id,
                Commission.customer_id == customer_id,
                Commission.subscription_id == subscription_id,
                Commission.event_type == event_type,
            )
        )
        if existing.scalar_one_or_none():
            logger.warning(
                f"Commission already exists for affiliate {affiliate_id}, "
                f"customer {customer_id}, subscription {subscription_id}, event {event_type.value}"
            )
            # Return existing commission
            return existing.scalar_one()

        # Create commission
        commission = Commission(
            affiliate_id=affiliate_id,
            customer_id=customer_id,
            subscription_id=subscription_id,
            event_type=event_type,
            amount=commission_amount,
            currency=currency,
            status=CommissionStatus.PENDING,
            event_date=datetime.utcnow(),
        )

        db.add(commission)
        try:
            await db.commit()
            await db.refresh(commission)
            logger.info(
                f"Created commission {commission.id} for affiliate {affiliate_id}: "
                f"{commission_amount} {currency} ({commission_rate}% of {subscription_amount})"
            )
            return commission
        except IntegrityError as e:
            await db.rollback()
            logger.error(f"Failed to create commission: {e}")
            raise ValueError("Failed to create commission") from e

    @staticmethod
    async def clear_commissions_after_hold_period(
        db: AsyncSession,
    ) -> int:
        """Clear commissions that have passed the hold period."""
        hold_date = datetime.utcnow() - timedelta(days=AFFILIATE_HOLD_PERIOD_DAYS)

        result = await db.execute(
            select(Commission).where(
                Commission.status == CommissionStatus.PENDING,
                Commission.event_date <= hold_date,
            )
        )
        commissions = result.scalars().all()

        cleared_count = 0
        for commission in commissions:
            commission.status = CommissionStatus.CLEARED
            commission.cleared_at = datetime.utcnow()
            cleared_count += 1

        if cleared_count > 0:
            await db.commit()
            logger.info(f"Cleared {cleared_count} commissions after hold period")

        return cleared_count

    @staticmethod
    async def reverse_commission(
        db: AsyncSession,
        commission_id: UUID,
        reason: Optional[str] = None,
    ) -> Commission:
        """Reverse a commission (e.g., due to refund)."""
        result = await db.execute(
            select(Commission).where(Commission.id == commission_id)
        )
        commission = result.scalar_one_or_none()

        if not commission:
            raise ValueError("Commission not found")

        if commission.status == CommissionStatus.REVERSED:
            logger.warning(f"Commission {commission_id} already reversed")
            return commission

        if commission.status == CommissionStatus.PAID:
            logger.warning(
                f"Reversing paid commission {commission_id} - may require manual payout adjustment"
            )

        commission.status = CommissionStatus.REVERSED
        if reason:
            commission.notes = reason
        commission.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(commission)
        logger.info(f"Reversed commission {commission_id}: {reason}")
        return commission

    @staticmethod
    async def get_cleared_balance(
        db: AsyncSession,
        affiliate_id: UUID,
    ) -> float:
        """Get cleared (payable) balance for an affiliate."""
        result = await db.execute(
            select(Commission).where(
                Commission.affiliate_id == affiliate_id,
                Commission.status == CommissionStatus.CLEARED,
            )
        )
        commissions = result.scalars().all()

        total = sum(float(c.amount) for c in commissions)
        return total

    @staticmethod
    async def mark_commissions_as_paid(
        db: AsyncSession,
        payout_id: UUID,
        commission_ids: List[UUID],
    ) -> int:
        """Mark commissions as paid when included in a payout."""
        result = await db.execute(
            select(Commission).where(
                Commission.id.in_(commission_ids),
                Commission.status == CommissionStatus.CLEARED,
            )
        )
        commissions = result.scalars().all()

        paid_count = 0
        for commission in commissions:
            commission.status = CommissionStatus.PAID
            commission.payout_id = payout_id
            commission.updated_at = datetime.utcnow()
            paid_count += 1

        if paid_count > 0:
            await db.commit()
            logger.info(f"Marked {paid_count} commissions as paid for payout {payout_id}")

        return paid_count

