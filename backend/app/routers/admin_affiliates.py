"""Admin affiliate management router endpoints."""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_admin_user
from app.database import get_db
from app.models.affiliate import Affiliate, AffiliateStatus
from app.models.commission import Commission, CommissionStatus
from app.models.payout import Payout, PayoutStatus
from app.models.user import User
from app.services.affiliate_service import AffiliateService
from app.services.commission_service import CommissionService
from app.services.logging_service import get_logger

logger = get_logger(__name__)

router = APIRouter()


# Request/Response Models
class AffiliateDetailResponse(BaseModel):
    id: str
    user_id: str
    user_email: str
    slug: str
    status: str
    commission_plan_id: Optional[str] = None
    company_name: Optional[str] = None
    website: Optional[str] = None
    payment_method_type: Optional[str] = None
    country: Optional[str] = None
    tax_id: Optional[str] = None
    notes: Optional[str] = None
    created_at: str
    updated_at: str
    stats: dict

    class Config:
        from_attributes = True


class ApproveAffiliateRequest(BaseModel):
    notes: Optional[str] = None


class RejectAffiliateRequest(BaseModel):
    notes: Optional[str] = None


class BlockAffiliateRequest(BaseModel):
    notes: Optional[str] = None


class CommissionAdjustmentRequest(BaseModel):
    amount: float
    reason: str


class PayoutApprovalRequest(BaseModel):
    payment_reference: Optional[str] = None
    notes: Optional[str] = None


class PayoutRejectionRequest(BaseModel):
    reason: str


# Endpoints
@router.get("", response_model=List[AffiliateDetailResponse])
async def list_affiliates(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> List[AffiliateDetailResponse]:
    """List all affiliates with filters."""
    query = select(Affiliate, User).join(User, Affiliate.user_id == User.id)

    if status_filter:
        try:
            status_enum = AffiliateStatus(status_filter)
            query = query.where(Affiliate.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}",
            )

    # Pagination
    offset = (page - 1) * page_size
    query = query.order_by(Affiliate.created_at.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    affiliates_data = result.all()

    affiliates = []
    for affiliate, user in affiliates_data:
        stats = await AffiliateService.get_affiliate_stats(db, affiliate.id)
        affiliates.append(
            AffiliateDetailResponse(
                id=str(affiliate.id),
                user_id=str(affiliate.user_id),
                user_email=user.email,
                slug=affiliate.slug,
                status=affiliate.status.value,
                commission_plan_id=str(affiliate.commission_plan_id) if affiliate.commission_plan_id else None,
                company_name=affiliate.company_name,
                website=affiliate.website,
                payment_method_type=affiliate.payment_method_type,
                country=affiliate.country,
                tax_id=affiliate.tax_id,
                notes=affiliate.notes,
                created_at=affiliate.created_at.isoformat(),
                updated_at=affiliate.updated_at.isoformat(),
                stats=stats,
            )
        )

    return affiliates


@router.get("/{affiliate_id}", response_model=AffiliateDetailResponse)
async def get_affiliate(
    affiliate_id: UUID,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> AffiliateDetailResponse:
    """Get affiliate details."""
    result = await db.execute(
        select(Affiliate, User)
        .join(User, Affiliate.user_id == User.id)
        .where(Affiliate.id == affiliate_id)
    )
    data = result.first()

    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Affiliate not found",
        )

    affiliate, user = data
    stats = await AffiliateService.get_affiliate_stats(db, affiliate.id)

    return AffiliateDetailResponse(
        id=str(affiliate.id),
        user_id=str(affiliate.user_id),
        user_email=user.email,
        slug=affiliate.slug,
        status=affiliate.status.value,
        commission_plan_id=str(affiliate.commission_plan_id) if affiliate.commission_plan_id else None,
        company_name=affiliate.company_name,
        website=affiliate.website,
        payment_method_type=affiliate.payment_method_type,
        country=affiliate.country,
        tax_id=affiliate.tax_id,
        notes=affiliate.notes,
        created_at=affiliate.created_at.isoformat(),
        updated_at=affiliate.updated_at.isoformat(),
        stats=stats,
    )


@router.post("/{affiliate_id}/approve")
async def approve_affiliate(
    affiliate_id: UUID,
    request: ApproveAffiliateRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> AffiliateDetailResponse:
    """Approve an affiliate application."""
    try:
        affiliate = await AffiliateService.approve_affiliate(
            db=db,
            affiliate_id=affiliate_id,
            admin_notes=request.notes,
        )

        result = await db.execute(
            select(User).where(User.id == affiliate.user_id)
        )
        user = result.scalar_one_or_none()

        stats = await AffiliateService.get_affiliate_stats(db, affiliate.id)

        return AffiliateDetailResponse(
            id=str(affiliate.id),
            user_id=str(affiliate.user_id),
            user_email=user.email if user else "unknown",
            slug=affiliate.slug,
            status=affiliate.status.value,
            commission_plan_id=str(affiliate.commission_plan_id) if affiliate.commission_plan_id else None,
            company_name=affiliate.company_name,
            website=affiliate.website,
            payment_method_type=affiliate.payment_method_type,
            country=affiliate.country,
            tax_id=affiliate.tax_id,
            notes=affiliate.notes,
            created_at=affiliate.created_at.isoformat(),
            updated_at=affiliate.updated_at.isoformat(),
            stats=stats,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/{affiliate_id}/reject")
async def reject_affiliate(
    affiliate_id: UUID,
    request: RejectAffiliateRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> AffiliateDetailResponse:
    """Reject an affiliate application."""
    try:
        affiliate = await AffiliateService.reject_affiliate(
            db=db,
            affiliate_id=affiliate_id,
            admin_notes=request.notes,
        )

        result = await db.execute(
            select(User).where(User.id == affiliate.user_id)
        )
        user = result.scalar_one_or_none()

        stats = await AffiliateService.get_affiliate_stats(db, affiliate.id)

        return AffiliateDetailResponse(
            id=str(affiliate.id),
            user_id=str(affiliate.user_id),
            user_email=user.email if user else "unknown",
            slug=affiliate.slug,
            status=affiliate.status.value,
            commission_plan_id=str(affiliate.commission_plan_id) if affiliate.commission_plan_id else None,
            company_name=affiliate.company_name,
            website=affiliate.website,
            payment_method_type=affiliate.payment_method_type,
            country=affiliate.country,
            tax_id=affiliate.tax_id,
            notes=affiliate.notes,
            created_at=affiliate.created_at.isoformat(),
            updated_at=affiliate.updated_at.isoformat(),
            stats=stats,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/{affiliate_id}/block")
async def block_affiliate(
    affiliate_id: UUID,
    request: BlockAffiliateRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> AffiliateDetailResponse:
    """Block an affiliate account."""
    try:
        affiliate = await AffiliateService.block_affiliate(
            db=db,
            affiliate_id=affiliate_id,
            admin_notes=request.notes,
        )

        result = await db.execute(
            select(User).where(User.id == affiliate.user_id)
        )
        user = result.scalar_one_or_none()

        stats = await AffiliateService.get_affiliate_stats(db, affiliate.id)

        return AffiliateDetailResponse(
            id=str(affiliate.id),
            user_id=str(affiliate.user_id),
            user_email=user.email if user else "unknown",
            slug=affiliate.slug,
            status=affiliate.status.value,
            commission_plan_id=str(affiliate.commission_plan_id) if affiliate.commission_plan_id else None,
            company_name=affiliate.company_name,
            website=affiliate.website,
            payment_method_type=affiliate.payment_method_type,
            country=affiliate.country,
            tax_id=affiliate.tax_id,
            notes=affiliate.notes,
            created_at=affiliate.created_at.isoformat(),
            updated_at=affiliate.updated_at.isoformat(),
            stats=stats,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/commissions/list", response_model=List[dict])
async def list_all_commissions(
    affiliate_id: Optional[UUID] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> List[dict]:
    """List all commissions with filters."""
    query = select(Commission)

    if affiliate_id:
        query = query.where(Commission.affiliate_id == affiliate_id)

    if status_filter:
        try:
            status_enum = CommissionStatus(status_filter)
            query = query.where(Commission.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}",
            )

    offset = (page - 1) * page_size
    query = query.order_by(Commission.event_date.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    commissions = result.scalars().all()

    return [
        {
            "id": str(c.id),
            "affiliate_id": str(c.affiliate_id),
            "customer_id": str(c.customer_id),
            "subscription_id": str(c.subscription_id) if c.subscription_id else None,
            "event_type": c.event_type.value,
            "amount": float(c.amount),
            "currency": c.currency,
            "status": c.status.value,
            "event_date": c.event_date.isoformat(),
            "cleared_at": c.cleared_at.isoformat() if c.cleared_at else None,
            "notes": c.notes,
        }
        for c in commissions
    ]


@router.post("/commissions/{commission_id}/adjust")
async def adjust_commission(
    commission_id: UUID,
    request: CommissionAdjustmentRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Manually adjust a commission amount."""
    result = await db.execute(
        select(Commission).where(Commission.id == commission_id)
    )
    commission = result.scalar_one_or_none()

    if not commission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Commission not found",
        )

    old_amount = float(commission.amount)
    commission.amount = request.amount
    commission.notes = f"{commission.notes or ''}\n[Admin Adjustment] {request.reason} (was {old_amount})".strip()

    await db.commit()
    await db.refresh(commission)

    logger.info(
        f"Admin {current_user.id} adjusted commission {commission_id} from {old_amount} to {request.amount}"
    )

    return {
        "id": str(commission.id),
        "amount": float(commission.amount),
        "currency": commission.currency,
        "notes": commission.notes,
    }


@router.get("/payouts/list", response_model=List[dict])
async def list_all_payouts(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> List[dict]:
    """List all payout requests."""
    query = select(Payout)

    if status_filter:
        try:
            status_enum = PayoutStatus(status_filter)
            query = query.where(Payout.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}",
            )

    offset = (page - 1) * page_size
    query = query.order_by(Payout.requested_at.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    payouts = result.scalars().all()

    return [
        {
            "id": str(p.id),
            "affiliate_id": str(p.affiliate_id),
            "amount": float(p.amount),
            "currency": p.currency,
            "status": p.status.value,
            "requested_at": p.requested_at.isoformat(),
            "processed_at": p.processed_at.isoformat() if p.processed_at else None,
            "payment_method": p.payment_method,
            "payment_reference": p.payment_reference,
            "notes": p.notes,
        }
        for p in payouts
    ]


@router.post("/payouts/{payout_id}/approve")
async def approve_payout(
    payout_id: UUID,
    request: PayoutApprovalRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Approve a payout request."""
    result = await db.execute(
        select(Payout).where(Payout.id == payout_id)
    )
    payout = result.scalar_one_or_none()

    if not payout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payout not found",
        )

    if payout.status != PayoutStatus.REQUESTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payout is not in requested status (current: {payout.status.value})",
        )

    # Get cleared commissions for this affiliate
    from sqlalchemy import select
    commissions_result = await db.execute(
        select(Commission)
        .where(
            Commission.affiliate_id == payout.affiliate_id,
            Commission.status == CommissionStatus.CLEARED,
            Commission.payout_id.is_(None),
        )
        .order_by(Commission.event_date.asc())
    )
    available_commissions = commissions_result.scalars().all()

    # Calculate total available
    total_available = sum(float(c.amount) for c in available_commissions)

    if payout.amount > total_available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient cleared commissions. Available: {total_available} {payout.currency}",
        )

    # Mark commissions as paid
    selected_commissions = []
    running_total = 0.0
    for commission in available_commissions:
        if running_total >= payout.amount:
            break
        selected_commissions.append(commission)
        running_total += float(commission.amount)

    # Update payout
    from datetime import datetime
    payout.status = PayoutStatus.APPROVED
    payout.processed_at = datetime.utcnow()
    if request.payment_reference:
        payout.payment_reference = request.payment_reference
    if request.notes:
        payout.notes = request.notes

    # Mark commissions as paid
    await CommissionService.mark_commissions_as_paid(
        db=db,
        payout_id=payout_id,
        commission_ids=[c.id for c in selected_commissions],
    )

    await db.commit()
    await db.refresh(payout)

    logger.info(f"Admin {current_user.id} approved payout {payout_id}")

    return {
        "id": str(payout.id),
        "status": payout.status.value,
        "processed_at": payout.processed_at.isoformat() if payout.processed_at else None,
    }


@router.post("/payouts/{payout_id}/pay")
async def mark_payout_as_paid(
    payout_id: UUID,
    request: PayoutApprovalRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Mark a payout as paid (after external payment)."""
    result = await db.execute(
        select(Payout).where(Payout.id == payout_id)
    )
    payout = result.scalar_one_or_none()

    if not payout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payout not found",
        )

    if payout.status != PayoutStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payout must be approved before marking as paid (current: {payout.status.value})",
        )

    from datetime import datetime
    payout.status = PayoutStatus.PAID
    payout.processed_at = datetime.utcnow()
    if request.payment_reference:
        payout.payment_reference = request.payment_reference
    if request.notes:
        payout.notes = request.notes

    await db.commit()
    await db.refresh(payout)

    logger.info(f"Admin {current_user.id} marked payout {payout_id} as paid")

    return {
        "id": str(payout.id),
        "status": payout.status.value,
        "processed_at": payout.processed_at.isoformat() if payout.processed_at else None,
    }


@router.post("/payouts/{payout_id}/reject")
async def reject_payout(
    payout_id: UUID,
    request: PayoutRejectionRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Reject a payout request."""
    result = await db.execute(
        select(Payout).where(Payout.id == payout_id)
    )
    payout = result.scalar_one_or_none()

    if not payout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payout not found",
        )

    if payout.status != PayoutStatus.REQUESTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payout is not in requested status (current: {payout.status.value})",
        )

    from datetime import datetime
    payout.status = PayoutStatus.REJECTED
    payout.processed_at = datetime.utcnow()
    payout.notes = f"{payout.notes or ''}\n[Rejected] {request.reason}".strip()

    await db.commit()
    await db.refresh(payout)

    logger.info(f"Admin {current_user.id} rejected payout {payout_id}: {request.reason}")

    return {
        "id": str(payout.id),
        "status": payout.status.value,
        "processed_at": payout.processed_at.isoformat() if payout.processed_at else None,
    }

