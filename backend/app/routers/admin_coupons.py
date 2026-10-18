"""Admin coupon management router endpoints."""

import logging
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_global_admin
from app.database import get_db
from app.models.coupon import Coupon, CouponStatus, DiscountType, DurationType
from app.models.coupon_redemption import CouponRedemption
from app.models.affiliate import Affiliate
from app.models.user import User
from app.services.coupon_service import CouponService
from app.services.logging_service import get_logger

logger = get_logger(__name__)

router = APIRouter()


# Request/Response Models
class CouponResponse(BaseModel):
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
    affiliate_id: Optional[str] = None
    affiliate_name: Optional[str] = None
    status: str
    stackable: bool
    allow_lifetime_discount: bool
    metadata_json: Dict
    redemption_count: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class CreateCouponRequest(BaseModel):
    code: str
    discount_type: str
    discount_value: float
    duration_type: str
    duration_months: Optional[int] = None
    expires_at: Optional[datetime] = None
    max_redemptions: Optional[int] = None
    max_redemptions_per_customer: int = 1
    eligible_plans: Optional[List[str]] = None
    affiliate_id: Optional[str] = None
    stackable: bool = False
    allow_lifetime_discount: bool = False
    metadata_json: Optional[Dict] = None


class UpdateCouponRequest(BaseModel):
    code: Optional[str] = None
    discount_type: Optional[str] = None
    discount_value: Optional[float] = None
    duration_type: Optional[str] = None
    duration_months: Optional[int] = None
    expires_at: Optional[datetime] = None
    max_redemptions: Optional[int] = None
    max_redemptions_per_customer: Optional[int] = None
    eligible_plans: Optional[List[str]] = None
    affiliate_id: Optional[str] = None
    status: Optional[str] = None
    stackable: Optional[bool] = None
    allow_lifetime_discount: Optional[bool] = None
    metadata_json: Optional[Dict] = None


class CouponRedemptionResponse(BaseModel):
    id: str
    coupon_id: str
    coupon_code: str
    customer_id: str
    customer_email: Optional[str] = None
    subscription_id: Optional[str] = None
    used_at: str
    discount_applied: float

    class Config:
        from_attributes = True


# Endpoints
@router.get("", response_model=List[CouponResponse])
async def list_coupons(
    status_filter: Optional[str] = Query(None, alias="status"),
    affiliate_id: Optional[str] = Query(None),
    plan_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_global_admin),
    db: AsyncSession = Depends(get_db),
) -> List[CouponResponse]:
    """List all coupons with filters."""
    
    query = select(Coupon)
    
    # Apply filters
    if status_filter:
        try:
            status_enum = CouponStatus(status_filter)
            query = query.where(Coupon.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}",
            )
    
    if affiliate_id:
        try:
            affiliate_uuid = UUID(affiliate_id)
            query = query.where(Coupon.affiliate_id == affiliate_uuid)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid affiliate_id: {affiliate_id}",
            )
    
    if plan_id:
        # Filter by eligible_plans JSONB array
        query = query.where(Coupon.eligible_plans.contains([plan_id]))
    
    # Pagination
    offset = (page - 1) * page_size
    query = query.order_by(Coupon.created_at.desc()).offset(offset).limit(page_size)
    
    result = await db.execute(query)
    coupons = result.scalars().all()
    
    # Build response with redemption counts
    coupons_data = []
    for coupon in coupons:
        # Get redemption count
        redemption_count_result = await db.execute(
            select(func.count(CouponRedemption.id))
            .where(CouponRedemption.coupon_id == coupon.id)
        )
        redemption_count = redemption_count_result.scalar() or 0
        
        # Get affiliate name if exists
        affiliate_name = None
        if coupon.affiliate_id:
            affiliate_result = await db.execute(
                select(Affiliate).where(Affiliate.id == coupon.affiliate_id)
            )
            affiliate = affiliate_result.scalar_one_or_none()
            if affiliate:
                affiliate_name = affiliate.company_name or affiliate.slug
        
        coupons_data.append(
            CouponResponse(
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
                affiliate_id=str(coupon.affiliate_id) if coupon.affiliate_id else None,
                affiliate_name=affiliate_name,
                status=coupon.status.value,
                stackable=coupon.stackable,
                allow_lifetime_discount=coupon.allow_lifetime_discount,
                metadata_json=coupon.metadata_json or {},
                redemption_count=redemption_count,
                created_at=coupon.created_at.isoformat(),
                updated_at=coupon.updated_at.isoformat(),
            )
        )
    
    return coupons_data


@router.get("/{coupon_id}", response_model=CouponResponse)
async def get_coupon(
    coupon_id: UUID,
    current_user: User = Depends(require_global_admin),
    db: AsyncSession = Depends(get_db),
) -> CouponResponse:
    """Get coupon details."""
    
    result = await db.execute(
        select(Coupon).where(Coupon.id == coupon_id)
    )
    coupon = result.scalar_one_or_none()
    
    if not coupon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Coupon not found",
        )
    
    # Get redemption count
    redemption_count_result = await db.execute(
        select(func.count(CouponRedemption.id))
        .where(CouponRedemption.coupon_id == coupon.id)
    )
    redemption_count = redemption_count_result.scalar() or 0
    
    # Get affiliate name if exists
    affiliate_name = None
    if coupon.affiliate_id:
        affiliate_result = await db.execute(
            select(Affiliate).where(Affiliate.id == coupon.affiliate_id)
        )
        affiliate = affiliate_result.scalar_one_or_none()
        if affiliate:
            affiliate_name = affiliate.company_name or affiliate.slug
    
    return CouponResponse(
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
        affiliate_id=str(coupon.affiliate_id) if coupon.affiliate_id else None,
        affiliate_name=affiliate_name,
        status=coupon.status.value,
        stackable=coupon.stackable,
        allow_lifetime_discount=coupon.allow_lifetime_discount,
        metadata_json=coupon.metadata_json or {},
        redemption_count=redemption_count,
        created_at=coupon.created_at.isoformat(),
        updated_at=coupon.updated_at.isoformat(),
    )


@router.post("", response_model=CouponResponse, status_code=status.HTTP_201_CREATED)
async def create_coupon(
    request: CreateCouponRequest,
    current_user: User = Depends(require_global_admin),
    db: AsyncSession = Depends(get_db),
) -> CouponResponse:
    """Create a new coupon."""
    
    try:
        # Convert string enums to enum types
        discount_type = DiscountType(request.discount_type)
        duration_type = DurationType(request.duration_type)
        
        affiliate_uuid = None
        if request.affiliate_id:
            try:
                affiliate_uuid = UUID(request.affiliate_id)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid affiliate_id: {request.affiliate_id}",
                )
        
        coupon = await CouponService.create_coupon(
            db=db,
            code=request.code,
            discount_type=discount_type,
            discount_value=request.discount_value,
            duration_type=duration_type,
            duration_months=request.duration_months,
            expires_at=request.expires_at,
            max_redemptions=request.max_redemptions,
            max_redemptions_per_customer=request.max_redemptions_per_customer,
            eligible_plans=request.eligible_plans,
            affiliate_id=affiliate_uuid,
            stackable=request.stackable,
            allow_lifetime_discount=request.allow_lifetime_discount,
            metadata_json=request.metadata_json,
        )
        
        # Get affiliate name if exists
        affiliate_name = None
        if coupon.affiliate_id:
            affiliate_result = await db.execute(
                select(Affiliate).where(Affiliate.id == coupon.affiliate_id)
            )
            affiliate = affiliate_result.scalar_one_or_none()
            if affiliate:
                affiliate_name = affiliate.company_name or affiliate.slug
        
        return CouponResponse(
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
            affiliate_id=str(coupon.affiliate_id) if coupon.affiliate_id else None,
            affiliate_name=affiliate_name,
            status=coupon.status.value,
            stackable=coupon.stackable,
            allow_lifetime_discount=coupon.allow_lifetime_discount,
            metadata_json=coupon.metadata_json or {},
            redemption_count=0,
            created_at=coupon.created_at.isoformat(),
            updated_at=coupon.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.patch("/{coupon_id}", response_model=CouponResponse)
async def update_coupon(
    coupon_id: UUID,
    request: UpdateCouponRequest,
    current_user: User = Depends(require_global_admin),
    db: AsyncSession = Depends(get_db),
) -> CouponResponse:
    """Update an existing coupon."""
    
    try:
        # Convert string enums to enum types if provided
        discount_type = None
        if request.discount_type:
            discount_type = DiscountType(request.discount_type)
        
        duration_type = None
        if request.duration_type:
            duration_type = DurationType(request.duration_type)
        
        status_enum = None
        if request.status:
            status_enum = CouponStatus(request.status)
        
        affiliate_uuid = None
        if request.affiliate_id is not None:
            if request.affiliate_id:
                try:
                    affiliate_uuid = UUID(request.affiliate_id)
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid affiliate_id: {request.affiliate_id}",
                    )
        
        coupon = await CouponService.update_coupon(
            db=db,
            coupon_id=coupon_id,
            code=request.code,
            discount_type=discount_type,
            discount_value=request.discount_value,
            duration_type=duration_type,
            duration_months=request.duration_months,
            expires_at=request.expires_at,
            max_redemptions=request.max_redemptions,
            max_redemptions_per_customer=request.max_redemptions_per_customer,
            eligible_plans=request.eligible_plans,
            affiliate_id=affiliate_uuid,
            status=status_enum,
            stackable=request.stackable,
            allow_lifetime_discount=request.allow_lifetime_discount,
            metadata_json=request.metadata_json,
        )
        
        # Get redemption count
        redemption_count_result = await db.execute(
            select(func.count(CouponRedemption.id))
            .where(CouponRedemption.coupon_id == coupon.id)
        )
        redemption_count = redemption_count_result.scalar() or 0
        
        # Get affiliate name if exists
        affiliate_name = None
        if coupon.affiliate_id:
            affiliate_result = await db.execute(
                select(Affiliate).where(Affiliate.id == coupon.affiliate_id)
            )
            affiliate = affiliate_result.scalar_one_or_none()
            if affiliate:
                affiliate_name = affiliate.company_name or affiliate.slug
        
        return CouponResponse(
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
            affiliate_id=str(coupon.affiliate_id) if coupon.affiliate_id else None,
            affiliate_name=affiliate_name,
            status=coupon.status.value,
            stackable=coupon.stackable,
            allow_lifetime_discount=coupon.allow_lifetime_discount,
            metadata_json=coupon.metadata_json or {},
            redemption_count=redemption_count,
            created_at=coupon.created_at.isoformat(),
            updated_at=coupon.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete("/{coupon_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_coupon(
    coupon_id: UUID,
    current_user: User = Depends(require_global_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete/deactivate a coupon."""
    
    result = await db.execute(
        select(Coupon).where(Coupon.id == coupon_id)
    )
    coupon = result.scalar_one_or_none()
    
    if not coupon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Coupon not found",
        )
    
    # Soft delete by setting status to expired
    coupon.status = CouponStatus.EXPIRED
    await db.commit()
    
    logger.info(f"Deactivated coupon {coupon_id} by admin {current_user.id}")


@router.get("/{coupon_id}/redemptions", response_model=List[CouponRedemptionResponse])
async def get_coupon_redemptions(
    coupon_id: UUID,
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(require_global_admin),
    db: AsyncSession = Depends(get_db),
) -> List[CouponRedemptionResponse]:
    """Get redemption history for a coupon."""
    
    # Verify coupon exists
    coupon_result = await db.execute(
        select(Coupon).where(Coupon.id == coupon_id)
    )
    coupon = coupon_result.scalar_one_or_none()
    
    if not coupon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Coupon not found",
        )
    
    # Get redemptions
    redemptions = await CouponService.get_coupon_redemptions(
        db=db,
        coupon_id=coupon_id,
        limit=limit,
    )
    
    # Build response with customer emails
    redemptions_data = []
    for redemption in redemptions:
        # Get customer email
        from app.models.user import User
        customer_result = await db.execute(
            select(User).where(User.id == redemption.customer_id)
        )
        customer = customer_result.scalar_one_or_none()
        customer_email = customer.email if customer else None
        
        redemptions_data.append(
            CouponRedemptionResponse(
                id=str(redemption.id),
                coupon_id=str(redemption.coupon_id),
                coupon_code=coupon.code,
                customer_id=str(redemption.customer_id),
                customer_email=customer_email,
                subscription_id=str(redemption.subscription_id) if redemption.subscription_id else None,
                used_at=redemption.used_at.isoformat(),
                discount_applied=float(redemption.discount_applied),
            )
        )
    
    return redemptions_data

