"""Affiliate portal router endpoints."""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.affiliate import Affiliate, AffiliateStatus
from app.models.affiliate_link import AffiliateLink
from app.models.commission import Commission, CommissionStatus
from app.models.payout import Payout, PayoutStatus
from app.models.user import User
from app.services.affiliate_service import AffiliateService
from app.services.commission_service import CommissionService
from app.services.coupon_service import CouponService
from app.services.logging_service import get_logger

logger = get_logger(__name__)

router = APIRouter()


# Request/Response Models
class AffiliateApplyRequest(BaseModel):
    company_name: Optional[str] = None
    website: Optional[str] = None
    country: Optional[str] = None


class AffiliateResponse(BaseModel):
    id: str
    slug: str
    status: str
    company_name: Optional[str] = None
    website: Optional[str] = None
    country: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class AffiliateStatsResponse(BaseModel):
    affiliate_id: str
    status: str
    total_clicks: int
    total_signups: int
    paying_customers: int
    total_earned: float
    pending_earned: float
    cleared_earned: float
    paid_earned: float
    mrr_generated: float


class AffiliateLinkResponse(BaseModel):
    id: str
    slug: str
    destination_url: str
    campaign_id: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class CreateLinkRequest(BaseModel):
    destination_url: str = "/"
    campaign_id: Optional[str] = None


class CommissionResponse(BaseModel):
    id: str
    customer_id: str
    subscription_id: Optional[str] = None
    event_type: str
    amount: float
    currency: str
    status: str
    event_date: str
    cleared_at: Optional[str] = None

    class Config:
        from_attributes = True


class CustomerResponse(BaseModel):
    customer_id: str
    email: str  # Obfuscated: user@***.com
    plan_id: Optional[str] = None
    status: Optional[str] = None
    signup_date: str


class PayoutRequest(BaseModel):
    amount: float
    currency: str = "EUR"


class PayoutResponse(BaseModel):
    id: str
    amount: float
    currency: str
    status: str
    requested_at: str
    processed_at: Optional[str] = None
    payment_method: Optional[str] = None

    class Config:
        from_attributes = True


# Endpoints
@router.post("/apply", response_model=AffiliateResponse)
async def apply_to_become_affiliate(
    request: AffiliateApplyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AffiliateResponse:
    """Apply to become an affiliate."""
    logger.info(f"User {current_user.id} applying to become affiliate")

    try:
        affiliate = await AffiliateService.apply_to_become_affiliate(
            db=db,
            user=current_user,
            company_name=request.company_name,
            website=request.website,
            country=request.country,
        )
        return AffiliateResponse(
            id=str(affiliate.id),
            slug=affiliate.slug,
            status=affiliate.status.value,
            company_name=affiliate.company_name,
            website=affiliate.website,
            country=affiliate.country,
            created_at=affiliate.created_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/me", response_model=AffiliateResponse)
async def get_my_affiliate(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AffiliateResponse:
    """Get current user's affiliate account."""
    affiliate = await AffiliateService.get_affiliate_by_user_id(db, current_user.id)

    if not affiliate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Affiliate account not found. Please apply first.",
        )

    return AffiliateResponse(
        id=str(affiliate.id),
        slug=affiliate.slug,
        status=affiliate.status.value,
        company_name=affiliate.company_name,
        website=affiliate.website,
        country=affiliate.country,
        created_at=affiliate.created_at.isoformat(),
    )


@router.get("/stats", response_model=AffiliateStatsResponse)
async def get_affiliate_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AffiliateStatsResponse:
    """Get affiliate statistics."""
    affiliate = await AffiliateService.get_affiliate_by_user_id(db, current_user.id)

    if not affiliate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Affiliate account not found",
        )

    stats = await AffiliateService.get_affiliate_stats(db, affiliate.id)
    return AffiliateStatsResponse(**stats)


@router.get("/links", response_model=List[AffiliateLinkResponse])
async def list_affiliate_links(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[AffiliateLinkResponse]:
    """List affiliate links."""
    from sqlalchemy import select

    affiliate = await AffiliateService.get_affiliate_by_user_id(db, current_user.id)

    if not affiliate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Affiliate account not found",
        )

    result = await db.execute(
        select(AffiliateLink).where(AffiliateLink.affiliate_id == affiliate.id)
    )
    links = result.scalars().all()

    return [
        AffiliateLinkResponse(
            id=str(link.id),
            slug=link.slug,
            destination_url=link.destination_url,
            campaign_id=link.campaign_id,
            created_at=link.created_at.isoformat(),
        )
        for link in links
    ]


@router.post("/links", response_model=AffiliateLinkResponse)
async def create_affiliate_link(
    request: CreateLinkRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AffiliateLinkResponse:
    """Create a new affiliate link."""
    affiliate = await AffiliateService.get_affiliate_by_user_id(db, current_user.id)

    if not affiliate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Affiliate account not found",
        )

    if affiliate.status != AffiliateStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Affiliate account must be approved to create links",
        )

    # Generate unique slug
    import secrets
    slug = secrets.token_urlsafe(8).lower()[:12]

    # Ensure uniqueness
    from sqlalchemy import select
    while True:
        existing = await db.execute(
            select(AffiliateLink).where(AffiliateLink.slug == slug)
        )
        if not existing.scalar_one_or_none():
            break
        slug = secrets.token_urlsafe(8).lower()[:12]

    link = AffiliateLink(
        affiliate_id=affiliate.id,
        slug=slug,
        destination_url=request.destination_url,
        campaign_id=request.campaign_id,
    )

    db.add(link)
    await db.commit()
    await db.refresh(link)

    logger.info(f"Created affiliate link {link.id} for affiliate {affiliate.id}")

    return AffiliateLinkResponse(
        id=str(link.id),
        slug=link.slug,
        destination_url=link.destination_url,
        campaign_id=link.campaign_id,
        created_at=link.created_at.isoformat(),
    )


class AffiliateCouponResponse(BaseModel):
    id: str
    code: str
    discount_type: str
    discount_value: float
    duration_type: str
    duration_months: Optional[int] = None
    expires_at: Optional[str] = None
    max_redemptions: Optional[int] = None
    max_redemptions_per_customer: int
    eligible_plans: List[str]
    status: str
    redemption_count: int
    created_at: str

    class Config:
        from_attributes = True


@router.get("/coupons", response_model=List[AffiliateCouponResponse])
async def list_affiliate_coupons(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[AffiliateCouponResponse]:
    """List coupons assigned to current affiliate."""
    from sqlalchemy import func, select
    from app.models.coupon import Coupon
    from app.models.coupon_redemption import CouponRedemption
    
    affiliate = await AffiliateService.get_affiliate_by_user_id(db, current_user.id)
    
    if not affiliate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Affiliate account not found",
        )
    
    # Get coupons for this affiliate
    coupons = await CouponService.get_affiliate_coupons(
        db=db,
        affiliate_id=affiliate.id,
        active_only=False,  # Show all coupons, not just active
    )
    
    # Build response with redemption counts
    coupons_data = []
    for coupon in coupons:
        # Get redemption count
        redemption_count_result = await db.execute(
            select(func.count(CouponRedemption.id))
            .where(CouponRedemption.coupon_id == coupon.id)
        )
        redemption_count = redemption_count_result.scalar() or 0
        
        coupons_data.append(
            AffiliateCouponResponse(
                id=str(coupon.id),
                code=coupon.code,
                discount_type=coupon.discount_type.value,
                discount_value=float(coupon.discount_value),
                duration_type=coupon.duration_type.value,
                duration_months=coupon.duration_months,
                expires_at=coupon.expires_at.isoformat() if coupon.expires_at else None,
                max_redemptions=coupon.max_redemptions,
                max_redemptions_per_customer=coupon.max_redemptions_per_customer,
                eligible_plans=coupon.eligible_plans or [],
                status=coupon.status.value,
                redemption_count=redemption_count,
                created_at=coupon.created_at.isoformat(),
            )
        )
    
    return coupons_data


@router.get("/commissions", response_model=List[CommissionResponse])
async def list_commissions(
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[CommissionResponse]:
    """List commissions for current affiliate."""
    from sqlalchemy import select

    affiliate = await AffiliateService.get_affiliate_by_user_id(db, current_user.id)

    if not affiliate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Affiliate account not found",
        )

    query = select(Commission).where(Commission.affiliate_id == affiliate.id)

    if status_filter:
        try:
            status_enum = CommissionStatus(status_filter)
            query = query.where(Commission.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}",
            )

    query = query.order_by(Commission.event_date.desc())

    result = await db.execute(query)
    commissions = result.scalars().all()

    return [
        CommissionResponse(
            id=str(c.id),
            customer_id=str(c.customer_id),
            subscription_id=str(c.subscription_id) if c.subscription_id else None,
            event_type=c.event_type.value,
            amount=float(c.amount),
            currency=c.currency,
            status=c.status.value,
            event_date=c.event_date.isoformat(),
            cleared_at=c.cleared_at.isoformat() if c.cleared_at else None,
        )
        for c in commissions
    ]


@router.get("/customers", response_model=List[CustomerResponse])
async def list_referred_customers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[CustomerResponse]:
    """List customers referred by current affiliate."""
    from sqlalchemy import select
    from app.models.affiliate_attribution import AffiliateAttribution
    from app.models.subscription import Subscription

    affiliate = await AffiliateService.get_affiliate_by_user_id(db, current_user.id)

    if not affiliate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Affiliate account not found",
        )

    result = await db.execute(
        select(AffiliateAttribution, User, Subscription)
        .join(User, AffiliateAttribution.customer_id == User.id)
        .outerjoin(Subscription, Subscription.user_id == User.id)
        .where(AffiliateAttribution.affiliate_id == affiliate.id)
        .order_by(AffiliateAttribution.first_attributed_at.desc())
    )

    customers = []
    for attribution, user, subscription in result.all():
        # Obfuscate email
        email_parts = user.email.split("@")
        if len(email_parts) == 2:
            obfuscated_email = f"{email_parts[0]}@***.{email_parts[1].split('.')[-1]}"
        else:
            obfuscated_email = "***@***.***"

        plan_id = None
        sub_status = None
        if subscription:
            plan_id = subscription.plan_id.value
            sub_status = subscription.status.value

        customers.append(
            CustomerResponse(
                customer_id=str(user.id),
                email=obfuscated_email,
                plan_id=plan_id,
                status=sub_status,
                signup_date=attribution.first_attributed_at.isoformat(),
            )
        )

    return customers


@router.post("/payout-request", response_model=PayoutResponse)
async def request_payout(
    request: PayoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PayoutResponse:
    """Request a payout."""
    import os

    affiliate = await AffiliateService.get_affiliate_by_user_id(db, current_user.id)

    if not affiliate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Affiliate account not found",
        )

    if affiliate.status != AffiliateStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Affiliate account must be approved to request payouts",
        )

    # Check minimum payout threshold
    min_payout = float(os.getenv("AFFILIATE_MIN_PAYOUT_EUR", "50"))
    if request.amount < min_payout:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Minimum payout amount is {min_payout} {request.currency}",
        )

    # Get cleared balance
    cleared_balance = await CommissionService.get_cleared_balance(db, affiliate.id)
    if request.amount > cleared_balance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient cleared balance. Available: {cleared_balance} {request.currency}",
        )

    # Check if payment details are set
    if not affiliate.payment_method_type or not affiliate.payment_details:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment details must be set before requesting payout",
        )

    # Create payout request
    payout = Payout(
        affiliate_id=affiliate.id,
        amount=request.amount,
        currency=request.currency,
        status=PayoutStatus.REQUESTED,
        payment_method=affiliate.payment_method_type,
    )

    db.add(payout)
    await db.commit()
    await db.refresh(payout)

    logger.info(f"Created payout request {payout.id} for affiliate {affiliate.id}")

    return PayoutResponse(
        id=str(payout.id),
        amount=float(payout.amount),
        currency=payout.currency,
        status=payout.status.value,
        requested_at=payout.requested_at.isoformat(),
        processed_at=payout.processed_at.isoformat() if payout.processed_at else None,
        payment_method=payout.payment_method,
    )


@router.get("/payouts", response_model=List[PayoutResponse])
async def list_payouts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[PayoutResponse]:
    """List payout history."""
    from sqlalchemy import select

    affiliate = await AffiliateService.get_affiliate_by_user_id(db, current_user.id)

    if not affiliate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Affiliate account not found",
        )

    result = await db.execute(
        select(Payout)
        .where(Payout.affiliate_id == affiliate.id)
        .order_by(Payout.requested_at.desc())
    )
    payouts = result.scalars().all()

    return [
        PayoutResponse(
            id=str(p.id),
            amount=float(p.amount),
            currency=p.currency,
            status=p.status.value,
            requested_at=p.requested_at.isoformat(),
            processed_at=p.processed_at.isoformat() if p.processed_at else None,
            payment_method=p.payment_method,
        )
        for p in payouts
    ]


@router.patch("/profile")
async def update_affiliate_profile(
    company_name: Optional[str] = None,
    website: Optional[str] = None,
    payment_method_type: Optional[str] = None,
    payment_details: Optional[str] = None,
    country: Optional[str] = None,
    tax_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AffiliateResponse:
    """Update affiliate profile."""
    affiliate = await AffiliateService.get_affiliate_by_user_id(db, current_user.id)

    if not affiliate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Affiliate account not found",
        )

    updated = await AffiliateService.update_affiliate_profile(
        db=db,
        affiliate=affiliate,
        company_name=company_name,
        website=website,
        payment_method_type=payment_method_type,
        payment_details=payment_details,
        country=country,
        tax_id=tax_id,
    )

    return AffiliateResponse(
        id=str(updated.id),
        slug=updated.slug,
        status=updated.status.value,
        company_name=updated.company_name,
        website=updated.website,
        country=updated.country,
        created_at=updated.created_at.isoformat(),
    )

