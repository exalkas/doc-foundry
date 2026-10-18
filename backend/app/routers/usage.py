"""Usage router endpoints."""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import (
    SQLAlchemyError,
    ProgrammingError,
    OperationalError,
)

from app.auth.dependencies import get_current_user, get_current_workspace, get_current_workspace_member
from app.database import get_db
from app.models.subscription import Subscription, SubscriptionPlanEnum, SubscriptionStatusEnum
from app.models.usagerecord import UsageRecord
from app.models.user import User
from app.services.authz_service import AuthzService
from app.services.logging_service import get_logger, set_correlation_id
from app.services.plan_service import PlanService
from app.services.usage_service import UsageService

logger = get_logger(__name__)

router = APIRouter()


class UsageSummaryResponse(BaseModel):
    current_period: dict
    documents_processed: int
    pages_processed: int
    plan_limits: dict
    overage: float
    warnings: List[dict] = []
    current_plan: Optional[str] = None


class UsageHistoryResponse(BaseModel):
    date: str
    pages: int
    documents: int


class UsageDailyResponse(BaseModel):
    date: str
    documents_processed: int
    pages_processed: int


class UsageBreakdownResponse(BaseModel):
    total: dict
    by_project: dict
    by_template: dict
    by_source: dict


async def get_plan_tier(db: AsyncSession, user_id) -> str:
    """Get plan tier for user."""
    plan_mapping = {
        SubscriptionPlanEnum.STARTER: "starter",
        SubscriptionPlanEnum.PRO: "pro",
    }
    
    result = await db.execute(
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.status.in_([SubscriptionStatusEnum.ACTIVE, SubscriptionStatusEnum.TRIALING]),
        )
        .order_by(Subscription.created_at.desc())
    )
    subscription = result.scalar_one_or_none()
    
    if subscription:
        return plan_mapping.get(subscription.plan_id, "free")
    return "free"


@router.get("/summary", response_model=UsageSummaryResponse)
async def get_usage_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UsageSummaryResponse:
    """Get usage summary for the current user aggregated across all workspaces."""
    correlation_id = set_correlation_id()
    logger.info(
        "Getting usage summary",
        extra={
            "user_id": str(current_user.id),
            "correlation_id": correlation_id,
        },
    )
    
    usage_service = UsageService()
    plan_service = PlanService()
    
    try:
        # Get current subscription/plan
        subscription_result = await db.execute(
            select(Subscription)
            .where(
                Subscription.user_id == current_user.id,
                Subscription.status.in_([SubscriptionStatusEnum.ACTIVE, SubscriptionStatusEnum.TRIALING])
            )
            .order_by(Subscription.created_at.desc())
        )
        subscription = subscription_result.scalar_one_or_none()
        
        # Determine current period
        now = datetime.now(timezone.utc)
        if subscription:
            period_start = subscription.current_period_start
            period_end = subscription.current_period_end
            plan_tier = await get_plan_tier(db, current_user.id)
        else:
            # Default to current month
            period_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
            if now.month == 12:
                period_end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
            else:
                period_end = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
            plan_tier = "free"
        
        # Get usage aggregated across all user's workspaces
        usage = await usage_service.get_user_usage(
            db, current_user.id, period_start, period_end
        )
        
        # Get plan limits
        limits = plan_service.get_plan_limits(plan_tier)
        
        # Calculate overage
        overage = plan_service.calculate_overage(plan_tier, usage["total_pages"])
        
        # Get quota warnings (aggregated across all workspaces)
        warnings = await usage_service.get_user_quota_warnings(
            db, current_user.id, plan_tier, period_start, period_end
        )
        
        return UsageSummaryResponse(
            current_period={
                "start": period_start.isoformat(),
                "end": period_end.isoformat(),
                "documents_processed": usage["total_documents"],
                "pages_processed": usage["total_pages"],
            },
            documents_processed=usage["total_documents"],
            pages_processed=usage["total_pages"],
            plan_limits={
                "plan_tier": plan_tier,
                "documents_per_month": limits.included_pages_per_month // 10,  # Rough estimate
                "pages_per_month": limits.included_pages_per_month,
                "included_pages": limits.included_pages_per_month,
                "max_pages_per_document": limits.max_pages_per_document,
                "max_file_size_mb": limits.max_file_size_mb,
                "max_templates": limits.max_templates,
                "max_projects": limits.max_projects,
            },
            overage=overage,
            warnings=[w["message"] for w in warnings],
            current_plan=plan_tier,
        )
    except ProgrammingError as e:
        logger.error(f"Database schema error getting usage summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        logger.error(f"Database connection error getting usage summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        logger.exception(f"Database error getting usage summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve usage summary",
        )
    except Exception as e:
        logger.exception(f"Unexpected error getting usage summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.get("/history", response_model=List[UsageHistoryResponse])
async def get_usage_history(
    days: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
) -> List[UsageHistoryResponse]:
    """Get daily usage history for the current workspace."""
    logger.info(f"Getting usage history for workspace: {current_workspace.id}, days={days}")
    
    usage_service = UsageService()
    
    try:
        history = await usage_service.get_usage_history(db, current_workspace.id, days)
        
        return [
            UsageHistoryResponse(
                date=item["date"],
                pages=item["pages"],
                documents=item["documents"],
            )
            for item in history
        ]
    except Exception as e:
        logger.exception(f"Unexpected error getting usage history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.get("/daily", response_model=List[UsageDailyResponse])
async def get_usage_daily(
    days: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
) -> List[UsageDailyResponse]:
    """Get daily usage history for the current workspace (frontend format)."""
    logger.info(f"Getting daily usage for workspace: {current_workspace.id}, days={days}")
    
    usage_service = UsageService()
    
    try:
        history = await usage_service.get_usage_history(db, current_workspace.id, days)
        
        return [
            UsageDailyResponse(
                date=item["date"],
                pages_processed=item["pages"],
                documents_processed=item["documents"],
            )
            for item in history
        ]
    except Exception as e:
        logger.exception(f"Unexpected error getting daily usage: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.get("/breakdown", response_model=UsageBreakdownResponse)
async def get_usage_breakdown(
    breakdown_type: str = Query("all", regex="^(all|project|template|source)$"),
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
    current_user: User = Depends(get_current_user),
) -> UsageBreakdownResponse:
    """Get usage breakdown by project, template, or source."""
    logger.info(f"Getting usage breakdown for workspace: {current_workspace.id}")
    
    usage_service = UsageService()
    
    try:
        # Get current subscription/plan (subscriptions are per-user, not per-workspace)
        subscription_result = await db.execute(
            select(Subscription)
            .where(
                Subscription.user_id == current_user.id,
                Subscription.status.in_([SubscriptionStatusEnum.ACTIVE, SubscriptionStatusEnum.TRIALING])
            )
            .order_by(Subscription.created_at.desc())
        )
        subscription = subscription_result.scalar_one_or_none()
        
        # Determine current period
        now = datetime.now(timezone.utc)
        if subscription:
            period_start = subscription.current_period_start
            period_end = subscription.current_period_end
        else:
            period_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
            if now.month == 12:
                period_end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
            else:
                period_end = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
        
        breakdown = await usage_service.get_usage_breakdown(
            db, current_workspace.id, period_start, period_end, breakdown_type
        )
        
        return UsageBreakdownResponse(
            total=breakdown["total"],
            by_project=breakdown["by_project"],
            by_template=breakdown["by_template"],
            by_source=breakdown["by_source"],
        )
    except Exception as e:
        logger.exception(f"Unexpected error getting usage breakdown: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )

