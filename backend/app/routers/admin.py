"""Admin router endpoints."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import (
    SQLAlchemyError,
    ProgrammingError,
    OperationalError,
)

from app.auth.dependencies import (
    get_current_admin_user,
    require_global_admin,
    create_access_token,
    TokenType,
)
from app.database import get_db
from app.models.job import Job, JobStatus, JobType
from app.models.subscription import Subscription, SubscriptionPlanEnum, SubscriptionStatusEnum
from app.models.workspace import Workspace, WorkspaceStatus
from app.models.auditlog import AuditLog
from app.models.workspacemember import WorkspaceMember, WorkspaceMemberRole, WorkspaceMemberStatus
from app.models.user import User, GlobalUserRole
from app.models.document import Document, DocumentStatusEnum
from app.models.apikey import ApiKey, ApiKeyStatusEnum
from app.models.webhookconfig import WebhookConfig
from app.models.webhookdelivery import WebhookDelivery, WebhookDeliveryStatus
from app.services.job_queue_service import JobQueueService
from app.services.logging_service import get_logger, set_correlation_id
from app.services.notification_service import NotificationService
from app.services.usage_service import UsageService

logger = get_logger(__name__)

router = APIRouter()


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    status: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ImpersonateResponse(BaseModel):
    token: str


class AuditLogResponse(BaseModel):
    id: str
    workspace_id: str | None
    user_id: str | None
    actor_type: str
    event_type: str
    description: str
    metadata: dict | None
    created_at: str

    class Config:
        from_attributes = True


class JobReprocessResponse(BaseModel):
    job_id: str
    message: str
    status: str


class UsageAnalyticsResponse(BaseModel):
    workspace_id: str
    current_period: Dict[str, Any]
    breakdown: Dict[str, Any]
    history: List[Dict[str, Any]]


class AbuseDetectionResponse(BaseModel):
    workspace_id: str
    violations: List[Dict[str, Any]]
    risk_score: float
    recommendations: List[str]


class WorkspaceSuspendResponse(BaseModel):
    workspace_id: str
    status: str
    message: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    global_role: str
    is_active: bool
    is_email_verified: bool
    last_login_at: Optional[str]
    created_at: str
    workspaces: List[Dict[str, Any]]

    class Config:
        from_attributes = True


class SubscriptionResponse(BaseModel):
    id: str
    user_id: str
    user_email: str
    plan_id: str
    status: str
    current_period_start: str
    current_period_end: str
    cancel_at_period_end: bool
    stripe_subscription_id: str
    created_at: str

    class Config:
        from_attributes = True


class SubscriptionDetailResponse(BaseModel):
    id: str
    user_id: str
    user_email: str
    plan_id: str
    status: str
    current_period_start: str
    current_period_end: str
    cancel_at_period_end: bool
    stripe_subscription_id: str
    created_at: str
    usage: Dict[str, Any]
    plan_limits: Dict[str, Any]

    class Config:
        from_attributes = True


class DocumentResponse(BaseModel):
    id: str
    workspace_id: str
    workspace_name: Optional[str]
    project_id: Optional[str]
    template_id: Optional[str]
    file_name: str
    file_type: str
    status: str
    pages: Optional[int]
    created_at: str
    uploaded_by_user_id: str

    class Config:
        from_attributes = True


class DocumentDetailResponse(BaseModel):
    id: str
    workspace_id: str
    workspace_name: Optional[str]
    project_id: Optional[str]
    template_id: Optional[str]
    file_name: str
    file_type: str
    status: str
    pages: Optional[int]
    created_at: str
    updated_at: str
    uploaded_by_user_id: str
    last_error: Optional[str]
    extraction_results: List[Dict[str, Any]]
    extraction_logs: List[Dict[str, Any]]

    class Config:
        from_attributes = True


class ApiKeyResponse(BaseModel):
    id: str
    workspace_id: str
    workspace_name: Optional[str]
    name: str
    prefix: str
    scopes: List[str]
    status: str
    expires_at: Optional[str]
    last_used_at: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class WebhookResponse(BaseModel):
    id: str
    workspace_id: str
    workspace_name: Optional[str]
    target_url: str
    events: List[str]
    enabled: bool
    created_at: str
    updated_at: str
    last_delivery: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True


class JobResponse(BaseModel):
    id: str
    type: str
    status: str
    attempts: int
    max_attempts: int
    last_error: Optional[str]
    payload: Dict[str, Any]
    created_at: str
    updated_at: str
    scheduled_at: str

    class Config:
        from_attributes = True


class MetricsResponse(BaseModel):
    queue_depth: int
    avg_processing_time_ms: Optional[float]
    daily_documents_processed: int
    errors_last_24h: int
    trends_7d: Dict[str, Any]
    trends_30d: Dict[str, Any]


class AnalyticsResponse(BaseModel):
    total_workspaces: int
    active_workspaces: int
    suspended_workspaces: int
    active_subscriptions: int
    total_mrr: float
    growth_trends: Dict[str, Any]


@router.get("/workspaces", response_model=List[WorkspaceResponse])
async def list_workspaces(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin_user = Depends(get_current_admin_user),
) -> List[WorkspaceResponse]:
    """List all workspaces (admin only)."""
    logger.info(f"Admin listing workspaces (user: {admin_user.id})")
    
    try:
        query = select(Workspace)
        
        if status_filter:
            try:
                status_enum = WorkspaceStatus(status_filter)
                query = query.where(Workspace.status == status_enum)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status_filter}",
                )
        
        query = query.order_by(Workspace.created_at.desc())
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        result = await db.execute(query)
        workspaces = result.scalars().all()
        
        return [
            WorkspaceResponse(
                id=str(ws.id),
                name=ws.name,
                status=ws.status.value,
                created_at=ws.created_at.isoformat(),
                updated_at=ws.updated_at.isoformat(),
            )
            for ws in workspaces
        ]
    except ProgrammingError as e:
        logger.error(f"Database schema error listing workspaces: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        logger.error(f"Database connection error listing workspaces: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        logger.exception(f"Database error listing workspaces: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list workspaces",
        )
    except Exception as e:
        logger.exception(f"Unexpected error listing workspaces: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.post("/workspaces/{workspace_id}/impersonate-owner", response_model=ImpersonateResponse)
async def impersonate_workspace_owner(
    workspace_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin_user = Depends(get_current_admin_user),
) -> ImpersonateResponse:
    """Impersonate a workspace owner (admin only)."""
    logger.info(f"Admin impersonating workspace owner: {workspace_id} (admin: {admin_user.id})")
    
    try:
        # Verify workspace exists
        workspace_result = await db.execute(
            select(Workspace).where(Workspace.id == workspace_id)
        )
        workspace = workspace_result.scalar_one_or_none()
        
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )
        
        # Find an owner of the workspace
        owner_result = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.role == WorkspaceMemberRole.OWNER,
                WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
            ).limit(1)
        )
        owner_member = owner_result.scalar_one_or_none()
        
        if not owner_member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active owner found for this workspace",
            )
        
        # Create impersonation token
        from app.models.user import User
        owner_result = await db.execute(
            select(User).where(User.id == owner_member.user_id)
        )
        owner_user = owner_result.scalar_one()
        
        token = create_access_token(
            data={
                "sub": str(owner_user.id),
                "workspace_id": str(workspace_id),
            },
            token_type=TokenType.IMPERSONATION,
        )
        
        logger.info(f"Impersonation token created for user: {owner_user.id}")
        
        return ImpersonateResponse(token=token)
    except HTTPException:
        raise
    except ProgrammingError as e:
        logger.error(f"Database schema error impersonating owner: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        logger.error(f"Database connection error impersonating owner: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        logger.exception(f"Database error impersonating owner: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to impersonate owner",
        )
    except Exception as e:
        logger.exception(f"Unexpected error impersonating owner: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.get("/audit-logs", response_model=List[AuditLogResponse])
async def list_admin_audit_logs(
    workspace_id: Optional[UUID] = Query(None),
    actor_type: Optional[str] = Query(None),
    from_date: Optional[datetime] = Query(None, alias="from"),
    to_date: Optional[datetime] = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin_user = Depends(get_current_admin_user),
) -> List[AuditLogResponse]:
    """List audit logs across all workspaces (admin only)."""
    logger.info(f"Admin listing audit logs (user: {admin_user.id})")
    
    try:
        query = select(AuditLog)
        
        # Apply filters
        if workspace_id:
            query = query.where(AuditLog.workspace_id == workspace_id)
        
        if actor_type:
            from app.models.auditlog import AuditActorTypeEnum
            try:
                actor_enum = AuditActorTypeEnum(actor_type)
                query = query.where(AuditLog.actor_type == actor_enum)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid actor_type: {actor_type}",
                )
        
        if from_date:
            query = query.where(AuditLog.created_at >= from_date)
        
        if to_date:
            query = query.where(AuditLog.created_at <= to_date)
        
        # Order by created_at descending
        query = query.order_by(AuditLog.created_at.desc())
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        result = await db.execute(query)
        logs = result.scalars().all()
        
        return [
            AuditLogResponse(
                id=str(log.id),
                workspace_id=str(log.workspace_id) if log.workspace_id else None,
                user_id=str(log.user_id) if log.user_id else None,
                actor_type=log.actor_type.value,
                event_type=log.event_type,
                description=log.description,
                metadata=log.event_metadata,
                created_at=log.created_at.isoformat(),
            )
            for log in logs
        ]
    except HTTPException:
        raise
    except ProgrammingError as e:
        logger.error(f"Database schema error listing admin audit logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        logger.error(f"Database connection error listing admin audit logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        logger.exception(f"Database error listing admin audit logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list audit logs",
        )
    except Exception as e:
        logger.exception(f"Unexpected error listing admin audit logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.post("/jobs/{job_id}/reprocess", response_model=JobReprocessResponse)
async def reprocess_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin_user = Depends(get_current_admin_user),
) -> JobReprocessResponse:
    """Manually reprocess a failed job (admin only)."""
    correlation_id = set_correlation_id()
    logger.info(
        "Admin reprocessing job",
        extra={
            "job_id": str(job_id),
            "admin_user_id": str(admin_user.id),
            "correlation_id": correlation_id,
        },
    )
    
    try:
        # Get job
        job_result = await db.execute(
            select(Job).where(Job.id == job_id)
        )
        job = job_result.scalar_one_or_none()
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found",
            )
        
        # Reset job status
        job.status = JobStatus.QUEUED
        job.attempts = 0
        job.last_error = None
        job.scheduled_at = datetime.now(timezone.utc)
        job.updated_at = datetime.now(timezone.utc)
        
        await db.commit()
        await db.refresh(job)
        
        logger.info(
            "Job reprocessed successfully",
            extra={
                "job_id": str(job_id),
                "correlation_id": correlation_id,
            },
        )
        
        return JobReprocessResponse(
            job_id=str(job.id),
            message="Job queued for reprocessing",
            status=job.status.value,
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.exception(f"Unexpected error reprocessing job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.get("/workspaces/{workspace_id}/usage-analytics", response_model=UsageAnalyticsResponse)
async def get_workspace_usage_analytics(
    workspace_id: UUID,
    days: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    admin_user = Depends(get_current_admin_user),
) -> UsageAnalyticsResponse:
    """Get detailed usage analytics for a workspace (admin only)."""
    logger.info(
        "Admin getting usage analytics",
        extra={
            "workspace_id": str(workspace_id),
            "admin_user_id": str(admin_user.id),
        },
    )
    
    usage_service = UsageService()
    
    try:
        # Verify workspace exists
        workspace_result = await db.execute(
            select(Workspace).where(Workspace.id == workspace_id)
        )
        workspace = workspace_result.scalar_one_or_none()
        
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )
        
        # Get subscription for period (subscriptions are per-user, get from workspace owner)
        subscription_result = await db.execute(
            select(Subscription)
            .where(
                Subscription.user_id == workspace.owner_user_id,
                Subscription.status.in_([SubscriptionStatusEnum.ACTIVE, SubscriptionStatusEnum.TRIALING]),
            )
            .order_by(Subscription.created_at.desc())
        )
        subscription = subscription_result.scalar_one_or_none()
        
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
        
        # Get usage breakdown
        breakdown = await usage_service.get_usage_breakdown(
            db, workspace_id, period_start, period_end, "all"
        )
        
        # Get usage history
        history = await usage_service.get_usage_history(db, workspace_id, days)
        
        return UsageAnalyticsResponse(
            workspace_id=str(workspace_id),
            current_period={
                "start": period_start.isoformat(),
                "end": period_end.isoformat(),
                "usage": await usage_service.get_current_period_usage(
                    db, workspace_id, period_start, period_end
                ),
            },
            breakdown=breakdown,
            history=history,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error getting usage analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.get("/workspaces/{workspace_id}/abuse-detection", response_model=AbuseDetectionResponse)
async def detect_workspace_abuse(
    workspace_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin_user = Depends(get_current_admin_user),
) -> AbuseDetectionResponse:
    """Check for abuse patterns in a workspace (admin only)."""
    logger.info(
        "Admin checking abuse detection",
        extra={
            "workspace_id": str(workspace_id),
            "admin_user_id": str(admin_user.id),
        },
    )
    
    usage_service = UsageService()
    
    try:
        # Verify workspace exists
        workspace_result = await db.execute(
            select(Workspace).where(Workspace.id == workspace_id)
        )
        workspace = workspace_result.scalar_one_or_none()
        
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )
        
        violations = []
        risk_score = 0.0
        recommendations = []
        
        # Check for rapid usage spikes (abuse pattern)
        from app.models.document import Document
        recent_docs_result = await db.execute(
            select(func.count(Document.id)).where(
                and_(
                    Document.workspace_id == workspace_id,
                    Document.created_at >= datetime.now(timezone.utc) - timedelta(hours=1),
                )
            )
        )
        recent_docs_count = recent_docs_result.scalar_one()
        
        if recent_docs_count > 100:  # More than 100 documents in 1 hour
            violations.append({
                "type": "rapid_usage_spike",
                "severity": "high",
                "description": f"{recent_docs_count} documents uploaded in the last hour",
                "threshold": 100,
            })
            risk_score += 0.3
        
        # Check for quota abuse (consistently hitting limits)
        # Get workspace to find owner user_id
        workspace_result = await db.execute(
            select(Workspace).where(Workspace.id == workspace_id)
        )
        workspace_obj = workspace_result.scalar_one_or_none()
        
        if not workspace_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )
        
        subscription_result = await db.execute(
            select(Subscription)
            .where(
                Subscription.user_id == workspace_obj.owner_user_id,
                Subscription.status.in_([SubscriptionStatusEnum.ACTIVE, SubscriptionStatusEnum.TRIALING]),
            )
            .order_by(Subscription.created_at.desc())
        )
        subscription = subscription_result.scalar_one_or_none()
        
        if subscription:
            period_start = subscription.current_period_start
            period_end = subscription.current_period_end
            usage = await usage_service.get_current_period_usage(
                db, workspace_id, period_start, period_end
            )
            
            # Check if usage is consistently at limit (potential abuse)
            from app.services.plan_service import PlanService
            plan_service = PlanService()
            plan_mapping = {
                SubscriptionPlanEnum.STARTER: "starter",
                SubscriptionPlanEnum.PRO: "pro",
            }
            plan_tier = plan_mapping.get(subscription.plan_id, "free")
            limits = plan_service.get_plan_limits(plan_tier)
            
            if limits.included_pages_per_month > 0:
                usage_percentage = usage["total_pages"] / limits.included_pages_per_month
                if usage_percentage >= 0.95:  # Using 95%+ of quota
                    violations.append({
                        "type": "quota_abuse",
                        "severity": "medium",
                        "description": f"Using {usage_percentage:.0%} of monthly quota",
                        "usage": usage["total_pages"],
                        "limit": limits.included_pages_per_month,
                    })
                    risk_score += 0.2
                    recommendations.append("Consider upgrading plan or investigate usage patterns")
        
        # Generate recommendations based on violations
        if risk_score >= 0.5:
            recommendations.append("Consider suspending workspace for review")
        if violations:
            recommendations.append("Monitor workspace activity closely")
        
        return AbuseDetectionResponse(
            workspace_id=str(workspace_id),
            violations=violations,
            risk_score=min(risk_score, 1.0),
            recommendations=recommendations if recommendations else ["No issues detected"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error detecting abuse: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.post("/workspaces/{workspace_id}/suspend", response_model=WorkspaceSuspendResponse)
async def suspend_workspace(
    workspace_id: UUID,
    reason: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    admin_user = Depends(get_current_admin_user),
) -> WorkspaceSuspendResponse:
    """Suspend a workspace (admin only)."""
    correlation_id = set_correlation_id()
    logger.info(
        "Admin suspending workspace",
        extra={
            "workspace_id": str(workspace_id),
            "admin_user_id": str(admin_user.id),
            "reason": reason,
            "correlation_id": correlation_id,
        },
    )
    
    notification_service = NotificationService()
    
    try:
        # Get workspace
        workspace_result = await db.execute(
            select(Workspace).where(Workspace.id == workspace_id)
        )
        workspace = workspace_result.scalar_one_or_none()
        
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )
        
        if workspace.status == WorkspaceStatus.SUSPENDED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Workspace is already suspended",
            )
        
        # Suspend workspace
        workspace.status = WorkspaceStatus.SUSPENDED
        workspace.updated_at = datetime.now(timezone.utc)
        
        await db.commit()
        await db.refresh(workspace)
        
        # Send notification to workspace owner
        try:
            owner_result = await db.execute(
                select(WorkspaceMember).where(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.role == WorkspaceMemberRole.OWNER,
                    WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
                ).limit(1)
            )
            owner_member = owner_result.scalar_one_or_none()
            
            if owner_member:
                from app.models.user import User
                user_result = await db.execute(
                    select(User).where(User.id == owner_member.user_id)
                )
                owner_user = user_result.scalar_one_or_none()
                
                if owner_user:
                    await notification_service.send_workspace_suspended(
                        owner_user.email,
                        workspace.name,
                        reason or "Administrative action",
                    )
        except Exception as e:
            logger.warning(f"Failed to send suspension notification: {e}")
        
        logger.info(
            "Workspace suspended successfully",
            extra={
                "workspace_id": str(workspace_id),
                "correlation_id": correlation_id,
            },
        )
        
        return WorkspaceSuspendResponse(
            workspace_id=str(workspace_id),
            status=workspace.status.value,
            message=f"Workspace suspended. Reason: {reason or 'Administrative action'}",
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.exception(f"Unexpected error suspending workspace: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.post("/workspaces/{workspace_id}/unsuspend", response_model=WorkspaceSuspendResponse)
async def unsuspend_workspace(
    workspace_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin_user = Depends(get_current_admin_user),
) -> WorkspaceSuspendResponse:
    """Unsuspend a workspace (admin only)."""
    correlation_id = set_correlation_id()
    logger.info(
        "Admin unsuspending workspace",
        extra={
            "workspace_id": str(workspace_id),
            "admin_user_id": str(admin_user.id),
            "correlation_id": correlation_id,
        },
    )
    
    try:
        # Get workspace
        workspace_result = await db.execute(
            select(Workspace).where(Workspace.id == workspace_id)
        )
        workspace = workspace_result.scalar_one_or_none()
        
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )
        
        if workspace.status != WorkspaceStatus.SUSPENDED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Workspace is not suspended",
            )
        
        # Unsuspend workspace (set to active)
        workspace.status = WorkspaceStatus.ACTIVE
        workspace.updated_at = datetime.now(timezone.utc)
        
        await db.commit()
        await db.refresh(workspace)
        
        logger.info(
            "Workspace unsuspended successfully",
            extra={
                "workspace_id": str(workspace_id),
                "correlation_id": correlation_id,
            },
        )
        
        return WorkspaceSuspendResponse(
            workspace_id=str(workspace_id),
            status=workspace.status.value,
            message="Workspace unsuspended successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.exception(f"Unexpected error unsuspending workspace: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


# Phase 3: User Management APIs
@router.get("/users", response_model=List[UserResponse])
async def list_users(
    role_filter: Optional[str] = Query(None, alias="role"),
    email_search: Optional[str] = Query(None, alias="email"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin_user = Depends(get_current_admin_user),
) -> List[UserResponse]:
    """List all users (admin only)."""
    logger.info(f"Admin listing users (user: {admin_user.id})")
    
    try:
        query = select(User)
        
        if role_filter:
            try:
                role_enum = GlobalUserRole(role_filter)
                query = query.where(User.global_role == role_enum)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid role: {role_filter}",
                )
        
        if email_search:
            query = query.where(User.email.ilike(f"%{email_search}%"))
        
        query = query.order_by(User.created_at.desc())
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        result = await db.execute(query)
        users = result.scalars().all()
        
        # Get workspace memberships for each user
        user_responses = []
        for user in users:
            memberships_result = await db.execute(
                select(WorkspaceMember, Workspace)
                .join(Workspace, WorkspaceMember.workspace_id == Workspace.id)
                .where(WorkspaceMember.user_id == user.id)
            )
            memberships = memberships_result.all()
            
            workspaces = []
            for member, workspace in memberships:
                workspaces.append({
                    "workspace_id": str(workspace.id),
                    "workspace_name": workspace.name,
                    "role": member.role.value,
                    "status": member.status.value,
                })
            
            user_responses.append(UserResponse(
                id=str(user.id),
                email=user.email,
                full_name=user.full_name,
                global_role=user.global_role.value,
                is_active=user.is_active,
                is_email_verified=user.is_email_verified,
                last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
                created_at=user.created_at.isoformat(),
                workspaces=workspaces,
            ))
        
        return user_responses
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error listing users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin_user = Depends(get_current_admin_user),
) -> UserResponse:
    """Get user details (admin only)."""
    logger.info(f"Admin getting user: {user_id} (admin: {admin_user.id})")
    
    try:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        
        # Get workspace memberships
        memberships_result = await db.execute(
            select(WorkspaceMember, Workspace)
            .join(Workspace, WorkspaceMember.workspace_id == Workspace.id)
            .where(WorkspaceMember.user_id == user.id)
        )
        memberships = memberships_result.all()
        
        workspaces = []
        for member, workspace in memberships:
            workspaces.append({
                "workspace_id": str(workspace.id),
                "workspace_name": workspace.name,
                "role": member.role.value,
                "status": member.status.value,
            })
        
        return UserResponse(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            global_role=user.global_role.value,
            is_active=user.is_active,
            is_email_verified=user.is_email_verified,
            last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
            created_at=user.created_at.isoformat(),
            workspaces=workspaces,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error getting user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


# Phase 3: Subscription Management APIs
@router.get("/subscriptions", response_model=List[SubscriptionResponse])
async def list_subscriptions(
    plan_filter: Optional[str] = Query(None, alias="plan"),
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin_user = Depends(get_current_admin_user),
) -> List[SubscriptionResponse]:
    """List all subscriptions (admin only)."""
    logger.info(f"Admin listing subscriptions (user: {admin_user.id})")
    
    try:
        query = select(Subscription, User).join(User, Subscription.user_id == User.id)
        
        if plan_filter:
            try:
                plan_enum = SubscriptionPlanEnum(plan_filter)
                query = query.where(Subscription.plan_id == plan_enum)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid plan: {plan_filter}",
                )
        
        if status_filter:
            try:
                status_enum = SubscriptionStatusEnum(status_filter)
                query = query.where(Subscription.status == status_enum)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status_filter}",
                )
        
        query = query.order_by(Subscription.created_at.desc())
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        result = await db.execute(query)
        subscriptions_data = result.all()
        
        return [
            SubscriptionResponse(
                id=str(sub.id),
                user_id=str(sub.user_id),
                user_email=user.email,
                plan_id=sub.plan_id.value,
                status=sub.status.value,
                current_period_start=sub.current_period_start.isoformat(),
                current_period_end=sub.current_period_end.isoformat(),
                cancel_at_period_end=sub.cancel_at_period_end,
                stripe_subscription_id=sub.stripe_subscription_id,
                created_at=sub.created_at.isoformat(),
            )
            for sub, user in subscriptions_data
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error listing subscriptions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.get("/subscriptions/{subscription_id}", response_model=SubscriptionDetailResponse)
async def get_subscription(
    subscription_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin_user = Depends(get_current_admin_user),
) -> SubscriptionDetailResponse:
    """Get subscription details (admin only)."""
    logger.info(f"Admin getting subscription: {subscription_id} (admin: {admin_user.id})")
    
    usage_service = UsageService()
    
    try:
        result = await db.execute(
            select(Subscription, User).join(User, Subscription.user_id == User.id)
            .where(Subscription.id == subscription_id)
        )
        data = result.first()
        
        if not data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription not found",
            )
        
        sub, user = data
        
        # Get usage for current period
        usage = await usage_service.get_current_period_usage(
            db, sub.workspace_id or UUID('00000000-0000-0000-0000-000000000000'),
            sub.current_period_start,
            sub.current_period_end,
        )
        
        # Get plan limits
        from app.services.plan_service import PlanService
        plan_service = PlanService()
        plan_tier = sub.plan_id.value
        limits = plan_service.get_plan_limits(plan_tier)
        
        plan_limits = {
            "included_pages_per_month": limits.included_pages_per_month,
            "max_pages_per_document": limits.max_pages_per_document,
            "max_file_size_mb": limits.max_file_size_mb,
            "max_concurrent_jobs": limits.max_concurrent_jobs,
        }
        
        return SubscriptionDetailResponse(
            id=str(sub.id),
            user_id=str(sub.user_id),
            user_email=user.email,
            plan_id=sub.plan_id.value,
            status=sub.status.value,
            current_period_start=sub.current_period_start.isoformat(),
            current_period_end=sub.current_period_end.isoformat(),
            cancel_at_period_end=sub.cancel_at_period_end,
            stripe_subscription_id=sub.stripe_subscription_id,
            created_at=sub.created_at.isoformat(),
            usage=usage,
            plan_limits=plan_limits,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error getting subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


# Phase 3: Document Management APIs
@router.get("/documents", response_model=List[DocumentResponse])
async def list_documents(
    workspace_id_filter: Optional[UUID] = Query(None, alias="workspace_id"),
    status_filter: Optional[str] = Query(None, alias="status"),
    from_date: Optional[datetime] = Query(None, alias="from"),
    to_date: Optional[datetime] = Query(None, alias="to"),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin_user = Depends(get_current_admin_user),
) -> List[DocumentResponse]:
    """List all documents (admin only)."""
    logger.info(f"Admin listing documents (user: {admin_user.id})")
    
    try:
        from sqlalchemy.orm import selectinload, noload
        
        # Use selectinload to control relationship loading explicitly
        # Use noload for relationships we don't need in the list view
        query = (
            select(Document, Workspace)
            .join(Workspace, Document.workspace_id == Workspace.id)
            .options(
                noload(Document.template),  # Don't load template relationship
                noload(Document.project),    # Don't load project relationship
                noload(Document.extraction_results),  # Don't load extraction results
                noload(Document.extraction_logs),    # Don't load extraction logs
            )
        )
        
        if workspace_id_filter:
            query = query.where(Document.workspace_id == workspace_id_filter)
        
        if status_filter:
            try:
                status_enum = DocumentStatusEnum(status_filter)
                query = query.where(Document.status == status_enum)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status_filter}",
                )
        
        if from_date:
            query = query.where(Document.created_at >= from_date)
        
        if to_date:
            query = query.where(Document.created_at <= to_date)
        
        if search:
            query = query.where(Document.file_name.ilike(f"%{search}%"))
        
        query = query.order_by(Document.created_at.desc())
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        result = await db.execute(query)
        documents_data = result.all()
        
        return [
            DocumentResponse(
                id=str(doc.id),
                workspace_id=str(doc.workspace_id),
                workspace_name=workspace.name,
                project_id=str(doc.project_id) if doc.project_id else None,
                template_id=str(doc.template_id) if doc.template_id else None,
                file_name=doc.file_name,
                file_type=doc.file_type,
                status=doc.status.value,
                pages=doc.pages,
                created_at=doc.created_at.isoformat(),
                uploaded_by_user_id=str(doc.uploaded_by_user_id),
            )
            for doc, workspace in documents_data
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error listing documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.get("/documents/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin_user = Depends(get_current_admin_user),
) -> DocumentDetailResponse:
    """Get document details (admin only)."""
    logger.info(f"Admin getting document: {document_id} (admin: {admin_user.id})")
    
    try:
        result = await db.execute(
            select(Document, Workspace)
            .join(Workspace, Document.workspace_id == Workspace.id)
            .where(Document.id == document_id)
        )
        data = result.first()
        
        if not data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )
        
        doc, workspace = data
        
        # Get extraction results
        from app.models.extractionresult import ExtractionResult
        results_result = await db.execute(
            select(ExtractionResult).where(ExtractionResult.document_id == document_id)
        )
        extraction_results = results_result.scalars().all()
        
        results_list = []
        for result in extraction_results:
            results_list.append({
                "id": str(result.id),
                "template_id": str(result.template_id),
                "confidence": float(result.confidence) if result.confidence else None,
                "extracted_data": result.extracted_data,
                "created_at": result.created_at.isoformat(),
            })
        
        # Get extraction logs
        from app.models.extractionlog import ExtractionLog
        logs_result = await db.execute(
            select(ExtractionLog).where(ExtractionLog.document_id == document_id)
            .order_by(ExtractionLog.created_at.desc())
        )
        extraction_logs = logs_result.scalars().all()
        
        logs_list = []
        for log in extraction_logs:
            logs_list.append({
                "id": str(log.id),
                "level": log.level.value if hasattr(log.level, 'value') else str(log.level),
                "message": log.message,
                "metadata": log.metadata,
                "created_at": log.created_at.isoformat(),
            })
        
        return DocumentDetailResponse(
            id=str(doc.id),
            workspace_id=str(doc.workspace_id),
            workspace_name=workspace.name,
            project_id=str(doc.project_id) if doc.project_id else None,
            template_id=str(doc.template_id) if doc.template_id else None,
            file_name=doc.file_name,
            file_type=doc.file_type,
            status=doc.status.value,
            pages=doc.pages,
            created_at=doc.created_at.isoformat(),
            updated_at=doc.updated_at.isoformat(),
            uploaded_by_user_id=str(doc.uploaded_by_user_id),
            last_error=doc.last_error,
            extraction_results=results_list,
            extraction_logs=logs_list,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error getting document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.post("/documents/{document_id}/retry")
async def retry_document_extraction(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin_user = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """Retry document extraction (admin only)."""
    correlation_id = set_correlation_id()
    logger.info(
        "Admin retrying document extraction",
        extra={
            "document_id": str(document_id),
            "admin_user_id": str(admin_user.id),
            "correlation_id": correlation_id,
        },
    )
    
    job_queue_service = JobQueueService()
    
    try:
        # Get document
        result = await db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )
        
        # Get workspace to find owner and plan tier
        workspace_result = await db.execute(
            select(Workspace).where(Workspace.id == document.workspace_id)
        )
        workspace = workspace_result.scalar_one_or_none()
        
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )
        
        # Get subscription to determine plan tier
        subscription_result = await db.execute(
            select(Subscription)
            .where(Subscription.user_id == workspace.owner_user_id)
            .order_by(Subscription.created_at.desc())
        )
        subscription = subscription_result.scalar_one_or_none()
        
        plan_tier = "free"
        if subscription:
            plan_tier = subscription.plan_id.value
        
        # Enqueue extraction job
        job = await job_queue_service.enqueue_extraction_job(
            session=db,
            document_id=document_id,
            workspace_id=document.workspace_id,
            template_id=document.template_id,
            plan_tier=plan_tier,
            check_quota=False,  # Admin override
        )
        
        # Update document status
        document.status = DocumentStatusEnum.PENDING
        document.updated_at = datetime.now(timezone.utc)
        await db.commit()
        
        logger.info(
            "Document extraction retry queued",
            extra={
                "document_id": str(document_id),
                "job_id": str(job.id),
                "correlation_id": correlation_id,
            },
        )
        
        return {
            "document_id": str(document_id),
            "job_id": str(job.id),
            "message": "Document extraction queued for retry",
            "status": "pending",
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.exception(f"Unexpected error retrying document extraction: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


# Phase 3: API Key Management APIs
@router.get("/api-keys", response_model=List[ApiKeyResponse])
async def list_api_keys(
    workspace_id_filter: Optional[UUID] = Query(None, alias="workspace_id"),
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin_user = Depends(get_current_admin_user),
) -> List[ApiKeyResponse]:
    """List all API keys (admin only)."""
    logger.info(f"Admin listing API keys (user: {admin_user.id})")
    
    try:
        query = select(ApiKey, Workspace).join(Workspace, ApiKey.workspace_id == Workspace.id)
        
        if workspace_id_filter:
            query = query.where(ApiKey.workspace_id == workspace_id_filter)
        
        if status_filter:
            try:
                status_enum = ApiKeyStatusEnum(status_filter)
                query = query.where(ApiKey.status == status_enum.value)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status_filter}",
                )
        
        query = query.order_by(ApiKey.created_at.desc())
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        result = await db.execute(query)
        api_keys_data = result.all()
        
        return [
            ApiKeyResponse(
                id=str(key.id),
                workspace_id=str(key.workspace_id),
                workspace_name=workspace.name,
                name=key.name,
                prefix=key.prefix,
                scopes=key.scopes if isinstance(key.scopes, list) else [],
                status=key.status,
                expires_at=key.expires_at.isoformat() if key.expires_at else None,
                last_used_at=key.last_used_at.isoformat() if key.last_used_at else None,
                created_at=key.created_at.isoformat(),
            )
            for key, workspace in api_keys_data
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error listing API keys: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.post("/api-keys/{api_key_id}/revoke")
async def revoke_api_key(
    api_key_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin_user = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """Revoke an API key (admin only)."""
    correlation_id = set_correlation_id()
    logger.info(
        "Admin revoking API key",
        extra={
            "api_key_id": str(api_key_id),
            "admin_user_id": str(admin_user.id),
            "correlation_id": correlation_id,
        },
    )
    
    try:
        result = await db.execute(select(ApiKey).where(ApiKey.id == api_key_id))
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found",
            )
        
        if api_key.status == ApiKeyStatusEnum.REVOKED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="API key is already revoked",
            )
        
        # Revoke the key
        api_key.status = ApiKeyStatusEnum.REVOKED.value
        
        await db.commit()
        await db.refresh(api_key)
        
        logger.info(
            "API key revoked successfully",
            extra={
                "api_key_id": str(api_key_id),
                "correlation_id": correlation_id,
            },
        )
        
        return {
            "id": str(api_key.id),
            "status": api_key.status,
            "message": "API key revoked successfully",
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.exception(f"Unexpected error revoking API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


# Phase 3: Webhook Management APIs
@router.get("/webhooks", response_model=List[WebhookResponse])
async def list_webhooks(
    workspace_id_filter: Optional[UUID] = Query(None, alias="workspace_id"),
    enabled_filter: Optional[bool] = Query(None, alias="enabled"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin_user = Depends(get_current_admin_user),
) -> List[WebhookResponse]:
    """List all webhooks (admin only)."""
    logger.info(f"Admin listing webhooks (user: {admin_user.id})")
    
    try:
        query = select(WebhookConfig, Workspace).join(Workspace, WebhookConfig.workspace_id == Workspace.id)
        
        if workspace_id_filter:
            query = query.where(WebhookConfig.workspace_id == workspace_id_filter)
        
        if enabled_filter is not None:
            query = query.where(WebhookConfig.enabled == enabled_filter)
        
        query = query.order_by(WebhookConfig.created_at.desc())
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        result = await db.execute(query)
        webhooks_data = result.all()
        
        webhooks_list = []
        for webhook, workspace in webhooks_data:
            # Get last delivery
            last_delivery_result = await db.execute(
                select(WebhookDelivery)
                .where(WebhookDelivery.webhook_config_id == webhook.id)
                .order_by(WebhookDelivery.created_at.desc())
                .limit(1)
            )
            last_delivery = last_delivery_result.scalar_one_or_none()
            
            last_delivery_dict = None
            if last_delivery:
                last_delivery_dict = {
                    "id": str(last_delivery.id),
                    "status": last_delivery.delivery_status.value,
                    "status_code": last_delivery.status_code,
                    "created_at": last_delivery.created_at.isoformat(),
                }
            
            webhooks_list.append(WebhookResponse(
                id=str(webhook.id),
                workspace_id=str(webhook.workspace_id),
                workspace_name=workspace.name,
                target_url=webhook.target_url,
                events=webhook.events if isinstance(webhook.events, list) else [],
                enabled=webhook.enabled,
                created_at=webhook.created_at.isoformat(),
                updated_at=webhook.updated_at.isoformat(),
                last_delivery=last_delivery_dict,
            ))
        
        return webhooks_list
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error listing webhooks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.post("/webhook-deliveries/{delivery_id}/retry")
async def retry_webhook_delivery(
    delivery_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin_user = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """Retry webhook delivery (admin only)."""
    correlation_id = set_correlation_id()
    logger.info(
        "Admin retrying webhook delivery",
        extra={
            "delivery_id": str(delivery_id),
            "admin_user_id": str(admin_user.id),
            "correlation_id": correlation_id,
        },
    )
    
    job_queue_service = JobQueueService()
    
    try:
        # Get delivery
        result = await db.execute(select(WebhookDelivery).where(WebhookDelivery.id == delivery_id))
        delivery = result.scalar_one_or_none()
        
        if not delivery:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook delivery not found",
            )
        
        # Get webhook config
        webhook_result = await db.execute(
            select(WebhookConfig).where(WebhookConfig.id == delivery.webhook_config_id)
        )
        webhook_config = webhook_result.scalar_one_or_none()
        
        if not webhook_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook config not found",
            )
        
        # Enqueue webhook delivery job
        job = await job_queue_service.enqueue_webhook_delivery_job(
            session=db,
            target_url=webhook_config.target_url,
            payload=delivery.payload,
            event_type=delivery.event_type,
            workspace_id=delivery.workspace_id,
            webhook_config_id=webhook_config.id,
            max_attempts=5,
        )
        
        logger.info(
            "Webhook delivery retry queued",
            extra={
                "delivery_id": str(delivery_id),
                "job_id": str(job.id),
                "correlation_id": correlation_id,
            },
        )
        
        return {
            "delivery_id": str(delivery_id),
            "job_id": str(job.id),
            "message": "Webhook delivery queued for retry",
            "status": "queued",
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.exception(f"Unexpected error retrying webhook delivery: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


# Phase 3: Job Management API
@router.get("/jobs", response_model=List[JobResponse])
async def list_jobs(
    type_filter: Optional[str] = Query(None, alias="type"),
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin_user = Depends(get_current_admin_user),
) -> List[JobResponse]:
    """List all jobs (admin only)."""
    logger.info(f"Admin listing jobs (user: {admin_user.id})")
    
    try:
        query = select(Job)
        
        if type_filter:
            try:
                type_enum = JobType(type_filter)
                query = query.where(Job.type == type_enum)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid job type: {type_filter}",
                )
        
        if status_filter:
            try:
                status_enum = JobStatus(status_filter)
                query = query.where(Job.status == status_enum)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status_filter}",
                )
        
        query = query.order_by(Job.created_at.desc())
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        result = await db.execute(query)
        jobs = result.scalars().all()
        
        return [
            JobResponse(
                id=str(job.id),
                type=job.type.value,
                status=job.status.value,
                attempts=job.attempts,
                max_attempts=job.max_attempts,
                last_error=job.last_error,
                payload=job.payload,
                created_at=job.created_at.isoformat(),
                updated_at=job.updated_at.isoformat(),
                scheduled_at=job.scheduled_at.isoformat(),
            )
            for job in jobs
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error listing jobs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


# Phase 4: System Metrics Dashboard
@router.get("/metrics", response_model=MetricsResponse)
async def get_system_metrics(
    db: AsyncSession = Depends(get_db),
    admin_user = Depends(get_current_admin_user),
) -> MetricsResponse:
    """Get system health metrics (admin only)."""
    logger.info(f"Admin getting system metrics (user: {admin_user.id})")
    
    try:
        from app.services.metrics_service import get_metrics
        metrics_service = get_metrics()
        
        # Queue depth (queued jobs count)
        queue_depth_result = await db.execute(
            select(func.count(Job.id)).where(Job.status == JobStatus.QUEUED)
        )
        queue_depth = queue_depth_result.scalar_one() or 0
        
        # Average processing time from metrics service
        avg_processing_time = None
        timing_stats = metrics_service.get_timing_stats("job_processing_duration_ms")
        if timing_stats:
            avg_processing_time = timing_stats.get("avg_ms")
        
        # Daily documents processed (last 24 hours)
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        daily_docs_result = await db.execute(
            select(func.count(Document.id)).where(
                Document.created_at >= yesterday
            )
        )
        daily_documents_processed = daily_docs_result.scalar_one() or 0
        
        # Errors last 24 hours
        errors_result = await db.execute(
            select(func.count(Job.id)).where(
                and_(
                    Job.status == JobStatus.FAILED,
                    Job.updated_at >= yesterday,
                )
            )
        )
        errors_last_24h = errors_result.scalar_one() or 0
        
        # Trends for last 7 days
        seven_days_ago = now - timedelta(days=7)
        trends_7d = {
            "documents_processed": [],
            "jobs_failed": [],
            "jobs_succeeded": [],
        }
        
        # Get daily counts for last 7 days
        for i in range(7):
            day_start = seven_days_ago + timedelta(days=i)
            day_end = day_start + timedelta(days=1)
            
            docs_count_result = await db.execute(
                select(func.count(Document.id)).where(
                    and_(
                        Document.created_at >= day_start,
                        Document.created_at < day_end,
                    )
                )
            )
            docs_count = docs_count_result.scalar_one() or 0
            
            failed_jobs_result = await db.execute(
                select(func.count(Job.id)).where(
                    and_(
                        Job.status == JobStatus.FAILED,
                        Job.updated_at >= day_start,
                        Job.updated_at < day_end,
                    )
                )
            )
            failed_count = failed_jobs_result.scalar_one() or 0
            
            succeeded_jobs_result = await db.execute(
                select(func.count(Job.id)).where(
                    and_(
                        Job.status == JobStatus.SUCCEEDED,
                        Job.updated_at >= day_start,
                        Job.updated_at < day_end,
                    )
                )
            )
            succeeded_count = succeeded_jobs_result.scalar_one() or 0
            
            trends_7d["documents_processed"].append({
                "date": day_start.date().isoformat(),
                "count": docs_count,
            })
            trends_7d["jobs_failed"].append({
                "date": day_start.date().isoformat(),
                "count": failed_count,
            })
            trends_7d["jobs_succeeded"].append({
                "date": day_start.date().isoformat(),
                "count": succeeded_count,
            })
        
        # Trends for last 30 days (aggregated weekly)
        thirty_days_ago = now - timedelta(days=30)
        trends_30d = {
            "documents_processed": [],
            "jobs_failed": [],
            "jobs_succeeded": [],
        }
        
        # Get weekly counts for last 30 days
        for i in range(0, 30, 7):
            week_start = thirty_days_ago + timedelta(days=i)
            week_end = min(week_start + timedelta(days=7), now)
            
            docs_count_result = await db.execute(
                select(func.count(Document.id)).where(
                    and_(
                        Document.created_at >= week_start,
                        Document.created_at < week_end,
                    )
                )
            )
            docs_count = docs_count_result.scalar_one() or 0
            
            failed_jobs_result = await db.execute(
                select(func.count(Job.id)).where(
                    and_(
                        Job.status == JobStatus.FAILED,
                        Job.updated_at >= week_start,
                        Job.updated_at < week_end,
                    )
                )
            )
            failed_count = failed_jobs_result.scalar_one() or 0
            
            succeeded_jobs_result = await db.execute(
                select(func.count(Job.id)).where(
                    and_(
                        Job.status == JobStatus.SUCCEEDED,
                        Job.updated_at >= week_start,
                        Job.updated_at < week_end,
                    )
                )
            )
            succeeded_count = succeeded_jobs_result.scalar_one() or 0
            
            trends_30d["documents_processed"].append({
                "week_start": week_start.date().isoformat(),
                "count": docs_count,
            })
            trends_30d["jobs_failed"].append({
                "week_start": week_start.date().isoformat(),
                "count": failed_count,
            })
            trends_30d["jobs_succeeded"].append({
                "week_start": week_start.date().isoformat(),
                "count": succeeded_count,
            })
        
        return MetricsResponse(
            queue_depth=queue_depth,
            avg_processing_time_ms=avg_processing_time,
            daily_documents_processed=daily_documents_processed,
            errors_last_24h=errors_last_24h,
            trends_7d=trends_7d,
            trends_30d=trends_30d,
        )
    except Exception as e:
        logger.exception(f"Unexpected error getting system metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


# Phase 4: Platform Analytics
@router.get("/analytics", response_model=AnalyticsResponse)
async def get_platform_analytics(
    from_date: Optional[datetime] = Query(None, alias="from"),
    to_date: Optional[datetime] = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db),
    admin_user = Depends(get_current_admin_user),
) -> AnalyticsResponse:
    """Get platform-wide analytics (admin only)."""
    logger.info(f"Admin getting platform analytics (user: {admin_user.id})")
    
    try:
        now = datetime.now(timezone.utc)
        start_date = from_date or (now - timedelta(days=30))
        end_date = to_date or now
        
        # Total workspaces
        total_workspaces_result = await db.execute(select(func.count(Workspace.id)))
        total_workspaces = total_workspaces_result.scalar_one() or 0
        
        # Active workspaces
        active_workspaces_result = await db.execute(
            select(func.count(Workspace.id)).where(Workspace.status == WorkspaceStatus.ACTIVE)
        )
        active_workspaces = active_workspaces_result.scalar_one() or 0
        
        # Suspended workspaces
        suspended_workspaces_result = await db.execute(
            select(func.count(Workspace.id)).where(Workspace.status == WorkspaceStatus.SUSPENDED)
        )
        suspended_workspaces = suspended_workspaces_result.scalar_one() or 0
        
        # Active subscriptions
        active_subscriptions_result = await db.execute(
            select(func.count(Subscription.id)).where(
                Subscription.status.in_([SubscriptionStatusEnum.ACTIVE, SubscriptionStatusEnum.TRIALING])
            )
        )
        active_subscriptions = active_subscriptions_result.scalar_one() or 0
        
        # Total MRR (Monthly Recurring Revenue)
        from app.services.plan_service import PlanService
        plan_service = PlanService()
        
        from sqlalchemy.orm import noload
        
        mrr_result = await db.execute(
            select(Subscription)
            .options(noload(Subscription.user))  # Don't load user relationship
            .where(
                Subscription.status.in_([SubscriptionStatusEnum.ACTIVE, SubscriptionStatusEnum.TRIALING])
            )
        )
        subscriptions_data = mrr_result.scalars().all()
        
        total_mrr = 0.0
        for sub in subscriptions_data:
            plan_tier = sub.plan_id.value if sub.plan_id else None
            if plan_tier:
                limits = plan_service.get_plan_limits(plan_tier)
                total_mrr += limits.monthly_base_price
        
        # Growth trends
        growth_trends = {
            "workspaces": [],
            "subscriptions": [],
        }
        
        # Calculate daily growth for date range
        current_date = start_date.date()
        end_date_only = end_date.date()
        
        while current_date <= end_date_only:
            day_start = datetime.combine(current_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            day_end = day_start + timedelta(days=1)
            
            # Workspaces created on this day
            workspaces_result = await db.execute(
                select(func.count(Workspace.id)).where(
                    and_(
                        Workspace.created_at >= day_start,
                        Workspace.created_at < day_end,
                    )
                )
            )
            workspaces_count = workspaces_result.scalar_one() or 0
            
            # Subscriptions created on this day
            subscriptions_result = await db.execute(
                select(func.count(Subscription.id)).where(
                    and_(
                        Subscription.created_at >= day_start,
                        Subscription.created_at < day_end,
                    )
                )
            )
            subscriptions_count = subscriptions_result.scalar_one() or 0
            
            growth_trends["workspaces"].append({
                "date": current_date.isoformat(),
                "count": workspaces_count,
            })
            growth_trends["subscriptions"].append({
                "date": current_date.isoformat(),
                "count": subscriptions_count,
            })
            
            current_date += timedelta(days=1)
        
        return AnalyticsResponse(
            total_workspaces=total_workspaces,
            active_workspaces=active_workspaces,
            suspended_workspaces=suspended_workspaces,
            active_subscriptions=active_subscriptions,
            total_mrr=total_mrr,
            growth_trends=growth_trends,
        )
    except Exception as e:
        logger.exception(f"Unexpected error getting platform analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )

