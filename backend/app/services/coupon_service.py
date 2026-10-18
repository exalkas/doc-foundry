"""Coupon service for managing discount codes and coupon redemptions."""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.coupon import Coupon, CouponStatus, DiscountType, DurationType
from app.models.coupon_redemption import CouponRedemption
from app.models.affiliate import Affiliate, AffiliateStatus
from app.models.user import User
from app.services.logging_service import get_logger

logger = get_logger(__name__)


class CouponService:
    """Service for coupon management and validation."""

    @staticmethod
    async def get_coupon_by_code(
        db: AsyncSession,
        code: str,
    ) -> Optional[Coupon]:
        """Get coupon by code (case-insensitive)."""
        code_lower = code.strip().lower()
        result = await db.execute(
            select(Coupon).where(func.lower(Coupon.code) == code_lower)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def validate_coupon(
        db: AsyncSession,
        code: str,
        plan_id: str,
        customer_id: Optional[UUID] = None,
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Validate a coupon code for a given plan and customer.
        
        Returns:
            Tuple of (is_valid, error_message, discount_info)
            discount_info contains: discount_type, discount_value, duration_type, duration_months
        """
        coupon = await CouponService.get_coupon_by_code(db, code)
        
        if not coupon:
            return False, "Coupon code not found", None
        
        # Check status
        if coupon.status == CouponStatus.EXPIRED:
            return False, "This coupon has expired", None
        
        if coupon.status == CouponStatus.PAUSED:
            return False, "This coupon is currently paused", None
        
        # Check expiration date
        if coupon.expires_at and coupon.expires_at < datetime.utcnow():
            # Auto-update status to expired
            coupon.status = CouponStatus.EXPIRED
            await db.commit()
            return False, "This coupon has expired", None
        
        # Check plan eligibility
        if coupon.eligible_plans and len(coupon.eligible_plans) > 0:
            if plan_id not in coupon.eligible_plans:
                return False, f"This coupon is not valid for the {plan_id} plan", None
        
        # Check max redemptions (global)
        if coupon.max_redemptions is not None:
            redemption_count_result = await db.execute(
                select(func.count(CouponRedemption.id))
                .where(CouponRedemption.coupon_id == coupon.id)
            )
            redemption_count = redemption_count_result.scalar() or 0
            if redemption_count >= coupon.max_redemptions:
                return False, "This coupon has reached its maximum redemption limit", None
        
        # Check max redemptions per customer
        if customer_id:
            customer_redemption_count_result = await db.execute(
                select(func.count(CouponRedemption.id))
                .where(
                    CouponRedemption.coupon_id == coupon.id,
                    CouponRedemption.customer_id == customer_id,
                )
            )
            customer_redemption_count = customer_redemption_count_result.scalar() or 0
            if customer_redemption_count >= coupon.max_redemptions_per_customer:
                return False, "You have already used this coupon the maximum number of times", None
        
        # Check for lifetime discount prevention (unless admin override)
        if not coupon.allow_lifetime_discount:
            if coupon.duration_type == DurationType.UNTIL_DATE and coupon.expires_at is None:
                return False, "Lifetime discounts are not allowed", None
            # Check if duration_months would result in lifetime discount
            if coupon.duration_type == DurationType.FIRST_N_MONTHS and coupon.duration_months is None:
                return False, "Invalid coupon configuration", None
        
        # Return discount info
        discount_info = {
            "discount_type": coupon.discount_type.value,
            "discount_value": float(coupon.discount_value),
            "duration_type": coupon.duration_type.value,
            "duration_months": coupon.duration_months,
            "expires_at": coupon.expires_at.isoformat() if coupon.expires_at else None,
        }
        
        return True, None, discount_info

    @staticmethod
    async def apply_coupon(
        db: AsyncSession,
        code: str,
        customer_id: UUID,
        plan_id: str,
        subscription_id: Optional[UUID] = None,
        subscription_amount: Optional[float] = None,
    ) -> Tuple[Optional[Coupon], Optional[CouponRedemption], Optional[str]]:
        """
        Apply a coupon and create redemption record.
        
        Returns:
            Tuple of (coupon, redemption, error_message)
        """
        # Validate coupon
        is_valid, error_msg, discount_info = await CouponService.validate_coupon(
            db, code, plan_id, customer_id
        )
        
        if not is_valid:
            return None, None, error_msg
        
        coupon = await CouponService.get_coupon_by_code(db, code)
        if not coupon:
            return None, None, "Coupon not found"
        
        # Calculate discount amount
        discount_amount = 0.0
        if subscription_amount:
            if coupon.discount_type == DiscountType.PERCENTAGE:
                discount_amount = float(subscription_amount) * float(coupon.discount_value) / 100.0
            elif coupon.discount_type == DiscountType.FIXED:
                discount_amount = min(float(coupon.discount_value), float(subscription_amount))
        
        # Create redemption record
        redemption = CouponRedemption(
            coupon_id=coupon.id,
            customer_id=customer_id,
            subscription_id=subscription_id,
            discount_applied=discount_amount,
        )
        
        db.add(redemption)
        try:
            await db.commit()
            await db.refresh(redemption)
            logger.info(
                f"Applied coupon {code} for customer {customer_id}, "
                f"discount: {discount_amount}"
            )
            return coupon, redemption, None
        except IntegrityError as e:
            await db.rollback()
            logger.error(f"Failed to create coupon redemption: {e}")
            return None, None, "Failed to apply coupon"

    @staticmethod
    async def create_coupon(
        db: AsyncSession,
        code: str,
        discount_type: DiscountType,
        discount_value: float,
        duration_type: DurationType,
        duration_months: Optional[int] = None,
        expires_at: Optional[datetime] = None,
        max_redemptions: Optional[int] = None,
        max_redemptions_per_customer: int = 1,
        eligible_plans: Optional[List[str]] = None,
        affiliate_id: Optional[UUID] = None,
        stackable: bool = False,
        allow_lifetime_discount: bool = False,
        metadata_json: Optional[Dict] = None,
    ) -> Coupon:
        """Create a new coupon (admin function)."""
        # Normalize code to lowercase
        code_lower = code.strip().lower()
        
        # Check if code already exists
        existing = await CouponService.get_coupon_by_code(db, code_lower)
        if existing:
            raise ValueError(f"Coupon code '{code_lower}' already exists")
        
        # Validate discount value
        if discount_value < 0:
            raise ValueError("Discount value must be non-negative")
        
        if discount_type == DiscountType.PERCENTAGE and discount_value > 100:
            raise ValueError("Percentage discount cannot exceed 100%")
        
        # Validate duration
        if duration_type == DurationType.FIRST_N_MONTHS and duration_months is None:
            raise ValueError("duration_months is required for first_n_months duration type")
        
        # Check lifetime discount prevention
        if not allow_lifetime_discount:
            if duration_type == DurationType.UNTIL_DATE and expires_at is None:
                raise ValueError("Lifetime discounts are not allowed. Set expires_at or allow_lifetime_discount=true")
        
        # Verify affiliate exists if provided
        if affiliate_id:
            affiliate_result = await db.execute(
                select(Affiliate).where(Affiliate.id == affiliate_id)
            )
            affiliate = affiliate_result.scalar_one_or_none()
            if not affiliate:
                raise ValueError(f"Affiliate {affiliate_id} not found")
            if affiliate.status != AffiliateStatus.APPROVED:
                raise ValueError(f"Affiliate {affiliate_id} is not approved")
        
        coupon = Coupon(
            code=code_lower,
            discount_type=discount_type,
            discount_value=discount_value,
            duration_type=duration_type,
            duration_months=duration_months,
            expires_at=expires_at,
            max_redemptions=max_redemptions,
            max_redemptions_per_customer=max_redemptions_per_customer,
            eligible_plans=eligible_plans or [],
            affiliate_id=affiliate_id,
            status=CouponStatus.ACTIVE,
            stackable=stackable,
            allow_lifetime_discount=allow_lifetime_discount,
            metadata_json=metadata_json or {},
        )
        
        db.add(coupon)
        try:
            await db.commit()
            await db.refresh(coupon)
            logger.info(f"Created coupon {coupon.id} with code {code_lower}")
            return coupon
        except IntegrityError as e:
            await db.rollback()
            logger.error(f"Failed to create coupon: {e}")
            raise ValueError("Failed to create coupon") from e

    @staticmethod
    async def update_coupon(
        db: AsyncSession,
        coupon_id: UUID,
        code: Optional[str] = None,
        discount_type: Optional[DiscountType] = None,
        discount_value: Optional[float] = None,
        duration_type: Optional[DurationType] = None,
        duration_months: Optional[int] = None,
        expires_at: Optional[datetime] = None,
        max_redemptions: Optional[int] = None,
        max_redemptions_per_customer: Optional[int] = None,
        eligible_plans: Optional[List[str]] = None,
        affiliate_id: Optional[UUID] = None,
        status: Optional[CouponStatus] = None,
        stackable: Optional[bool] = None,
        allow_lifetime_discount: Optional[bool] = None,
        metadata_json: Optional[Dict] = None,
    ) -> Coupon:
        """Update an existing coupon (admin function)."""
        result = await db.execute(
            select(Coupon).where(Coupon.id == coupon_id)
        )
        coupon = result.scalar_one_or_none()
        
        if not coupon:
            raise ValueError("Coupon not found")
        
        # Update fields
        if code is not None:
            code_lower = code.strip().lower()
            if code_lower != coupon.code:
                # Check if new code already exists
                existing = await CouponService.get_coupon_by_code(db, code_lower)
                if existing and existing.id != coupon_id:
                    raise ValueError(f"Coupon code '{code_lower}' already exists")
                coupon.code = code_lower
        
        if discount_type is not None:
            coupon.discount_type = discount_type
        if discount_value is not None:
            if discount_value < 0:
                raise ValueError("Discount value must be non-negative")
            if coupon.discount_type == DiscountType.PERCENTAGE and discount_value > 100:
                raise ValueError("Percentage discount cannot exceed 100%")
            coupon.discount_value = discount_value
        if duration_type is not None:
            coupon.duration_type = duration_type
        if duration_months is not None:
            coupon.duration_months = duration_months
        if expires_at is not None:
            coupon.expires_at = expires_at
        if max_redemptions is not None:
            coupon.max_redemptions = max_redemptions
        if max_redemptions_per_customer is not None:
            coupon.max_redemptions_per_customer = max_redemptions_per_customer
        if eligible_plans is not None:
            coupon.eligible_plans = eligible_plans
        if affiliate_id is not None:
            if affiliate_id:
                affiliate_result = await db.execute(
                    select(Affiliate).where(Affiliate.id == affiliate_id)
                )
                affiliate = affiliate_result.scalar_one_or_none()
                if not affiliate:
                    raise ValueError(f"Affiliate {affiliate_id} not found")
            coupon.affiliate_id = affiliate_id
        if status is not None:
            coupon.status = status
        if stackable is not None:
            coupon.stackable = stackable
        if allow_lifetime_discount is not None:
            coupon.allow_lifetime_discount = allow_lifetime_discount
        if metadata_json is not None:
            coupon.metadata_json = metadata_json
        
        coupon.updated_at = datetime.utcnow()
        
        try:
            await db.commit()
            await db.refresh(coupon)
            logger.info(f"Updated coupon {coupon_id}")
            return coupon
        except IntegrityError as e:
            await db.rollback()
            logger.error(f"Failed to update coupon: {e}")
            raise ValueError("Failed to update coupon") from e

    @staticmethod
    async def get_affiliate_coupons(
        db: AsyncSession,
        affiliate_id: UUID,
        active_only: bool = True,
    ) -> List[Coupon]:
        """Get coupons assigned to an affiliate."""
        query = select(Coupon).where(Coupon.affiliate_id == affiliate_id)
        
        if active_only:
            query = query.where(Coupon.status == CouponStatus.ACTIVE)
        
        query = query.order_by(Coupon.created_at.desc())
        
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_coupon_redemptions(
        db: AsyncSession,
        coupon_id: UUID,
        limit: int = 100,
    ) -> List[CouponRedemption]:
        """Get redemption history for a coupon."""
        result = await db.execute(
            select(CouponRedemption)
            .where(CouponRedemption.coupon_id == coupon_id)
            .order_by(CouponRedemption.used_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def check_self_referral(
        db: AsyncSession,
        coupon: Coupon,
        customer: User,
    ) -> bool:
        """Check if coupon redemption would be a self-referral."""
        if not coupon.affiliate_id:
            return False
        
        # Get affiliate
        affiliate_result = await db.execute(
            select(Affiliate).where(Affiliate.id == coupon.affiliate_id)
        )
        affiliate = affiliate_result.scalar_one_or_none()
        
        if not affiliate:
            return False
        
        # Get affiliate's user
        affiliate_user_result = await db.execute(
            select(User).where(User.id == affiliate.user_id)
        )
        affiliate_user = affiliate_user_result.scalar_one_or_none()
        
        if not affiliate_user:
            return False
        
        # Check if emails match
        if affiliate_user.email.lower() == customer.email.lower():
            return True
        
        # Check if same domain (basic check)
        customer_domain = customer.email.split("@")[-1].lower()
        affiliate_domain = affiliate_user.email.split("@")[-1].lower()
        if customer_domain == affiliate_domain:
            logger.warning(
                f"Potential self-referral: customer {customer.email} and affiliate {affiliate_user.email} "
                f"share domain {customer_domain}"
            )
            # Don't block, but log warning
        
        return False

