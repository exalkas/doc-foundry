"""Webhooks router endpoints."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import (
    SQLAlchemyError,
    IntegrityError,
    ProgrammingError,
    OperationalError,
)

from app.auth.dependencies import (
    get_current_user,
    get_current_workspace,
    get_current_workspace_member,
)
from app.database import get_db
from app.models.subscription import Subscription, SubscriptionPlanEnum, SubscriptionStatusEnum
from app.models.webhookconfig import WebhookConfig
from app.models.webhookdelivery import WebhookDelivery, WebhookDeliveryStatus
from app.services.authz_service import AuthzService
from app.services.job_queue_service import JobQueueService
from app.services.logging_service import get_logger, set_correlation_id
from app.services.notification_service import NotificationService
from app.services.plan_service import PlanService

logger = get_logger(__name__)

router = APIRouter()


class WebhookConfigResponse(BaseModel):
    id: str
    workspace_id: str
    target_url: str
    events: List[str]
    retry_policy: Dict[str, Any]
    enabled: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class WebhookConfigCreateRequest(BaseModel):
    target_url: str
    secret: str
    events: List[str]
    retry_policy: Dict[str, Any]
    enabled: bool = True


class WebhookConfigUpdateRequest(BaseModel):
    target_url: str | None = None
    secret: str | None = None
    events: List[str] | None = None
    retry_policy: Dict[str, Any] | None = None
    enabled: bool | None = None


class WebhookConfigUpsertRequest(BaseModel):
    id: UUID | None = None
    target_url: str
    secret: str
    events: List[str]
    retry_policy: Dict[str, Any]
    enabled: bool = True


class WebhookTestRequest(BaseModel):
    target_url: str
    secret: str
    event_type: str
    payload: Dict[str, Any]


class WebhookDeliveryResponse(BaseModel):
    id: str
    webhook_config_id: str
    workspace_id: str
    event_type: str
    status_code: int | None
    delivery_status: str
    attempt_count: int
    last_error: str | None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
) -> None:
    """Delete a webhook configuration."""
    logger.info(f"Deleting webhook: {webhook_id}")
    
    authz_service = AuthzService()
    
    try:
        result = await db.execute(
            select(WebhookConfig).where(
                WebhookConfig.id == webhook_id,
                WebhookConfig.workspace_id == current_workspace.id,
            )
        )
        webhook = result.scalar_one_or_none()
        
        if not webhook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook not found",
            )
        
        # Authorization check
        await authz_service.assert_resource_ownership(
            db, current_member.user_id, current_workspace.id, webhook.workspace_id
        )
        
        if not authz_service.can_perform_action(current_member.role, "manage_webhooks"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to delete webhooks",
            )
        
        await db.delete(webhook)
        await db.commit()
        
        logger.info(f"Webhook deleted successfully: {webhook_id}")
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.exception(f"Unexpected error deleting webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.get("", response_model=List[WebhookConfigResponse])
async def list_webhooks(
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
) -> List[WebhookConfigResponse]:
    """List webhook configurations for the current workspace."""
    logger.info(f"Listing webhooks for workspace: {current_workspace.id}")
    
    try:
        result = await db.execute(
            select(WebhookConfig)
            .where(WebhookConfig.workspace_id == current_workspace.id)
            .order_by(WebhookConfig.created_at.desc())
        )
        webhooks = result.scalars().all()
        
        return [
            WebhookConfigResponse(
                id=str(w.id),
                workspace_id=str(w.workspace_id),
                target_url=w.target_url,
                events=w.events,
                retry_policy=w.retry_policy,
                enabled=w.enabled,
                created_at=w.created_at.isoformat(),
                updated_at=w.updated_at.isoformat(),
            )
            for w in webhooks
        ]
    except ProgrammingError as e:
        logger.error(f"Database schema error listing webhooks: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        logger.error(f"Database connection error listing webhooks: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        logger.exception(f"Database error listing webhooks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list webhooks",
        )
    except Exception as e:
        logger.exception(f"Unexpected error listing webhooks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.post("", response_model=WebhookConfigResponse, status_code=status.HTTP_201_CREATED)
async def upsert_webhook(
    request: WebhookConfigUpsertRequest,
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
) -> WebhookConfigResponse:
    """Create or update a webhook configuration (upsert) with plan checks."""
    correlation_id = set_correlation_id()
    logger.info(
        "Upserting webhook",
        extra={
            "workspace_id": str(current_workspace.id),
            "correlation_id": correlation_id,
        },
    )
    
    # Authorization check
    authz_service = AuthzService()
    if not authz_service.can_perform_action(current_member.role, "manage_webhooks"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to manage webhooks",
        )
    
    # Check if webhooks are enabled for plan
    plan_service = PlanService()
    
    # Get plan tier (subscriptions are per-user, not per-workspace)
    subscription_result = await db.execute(
        select(Subscription)
        .where(
            Subscription.user_id == current_user.id,
            Subscription.status.in_([SubscriptionStatusEnum.ACTIVE, SubscriptionStatusEnum.TRIALING]),
        )
        .order_by(Subscription.created_at.desc())
    )
    subscription = subscription_result.scalar_one_or_none()
    
    plan_mapping = {
        SubscriptionPlanEnum.STARTER: "starter",
        SubscriptionPlanEnum.PRO: "pro",
    }
    plan_tier = plan_mapping.get(subscription.plan_id, "free") if subscription else "free"
    
    if not plan_service.check_feature_enabled(plan_tier, "webhooks"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Webhooks are not available on your plan. Please upgrade to enable webhooks.",
        )
    
    try:
        webhook: Optional[WebhookConfig] = None
        
        # If ID provided, try to find existing webhook
        if request.id:
            result = await db.execute(
                select(WebhookConfig).where(
                    WebhookConfig.id == request.id,
                    WebhookConfig.workspace_id == current_workspace.id,
                )
            )
            webhook = result.scalar_one_or_none()
        
        if webhook:
            # Update existing
            webhook.target_url = request.target_url
            webhook.secret = request.secret
            webhook.events = request.events
            webhook.retry_policy = request.retry_policy
            webhook.enabled = request.enabled
            logger.info(f"Updating webhook: {webhook.id}")
        else:
            # Create new
            webhook = WebhookConfig(
                workspace_id=current_workspace.id,
                target_url=request.target_url,
                secret=request.secret,
                events=request.events,
                retry_policy=request.retry_policy,
                enabled=request.enabled,
            )
            db.add(webhook)
            logger.info(f"Creating new webhook")
        
        await db.commit()
        await db.refresh(webhook)
        
        logger.info(f"Webhook upserted successfully: {webhook.id}")
        return WebhookConfigResponse(
            id=str(webhook.id),
            workspace_id=str(webhook.workspace_id),
            target_url=webhook.target_url,
            events=webhook.events,
            retry_policy=webhook.retry_policy,
            enabled=webhook.enabled,
            created_at=webhook.created_at.isoformat(),
            updated_at=webhook.updated_at.isoformat(),
        )
    except IntegrityError as e:
        await db.rollback()
        logger.warning(f"Integrity error upserting webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook data",
        )
    except ProgrammingError as e:
        await db.rollback()
        logger.error(f"Database schema error upserting webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        await db.rollback()
        logger.error(f"Database connection error upserting webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        await db.rollback()
        logger.exception(f"Database error upserting webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upsert webhook",
        )
    except Exception as e:
        await db.rollback()
        logger.exception(f"Unexpected error upserting webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.post("/test", status_code=status.HTTP_202_ACCEPTED)
async def test_webhook(
    request: WebhookTestRequest,
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
) -> Dict[str, Any]:
    """Send a test event to a webhook endpoint."""
    logger.info(f"Testing webhook to: {request.target_url}")
    
    authz_service = AuthzService()
    job_queue_service = JobQueueService()
    
    # Authorization check
    if not authz_service.can_perform_action(current_member.role, "manage_webhooks"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to test webhooks",
        )
    
    try:
        # Enqueue webhook delivery job
        job = await job_queue_service.enqueue_webhook_delivery_job(
            db,
            request.target_url,
            request.payload,
            request.event_type,
            current_workspace.id,
            webhook_config_id=None,
            max_attempts=1,  # Test webhooks only try once
        )
        
        await db.commit()
        
        return {
            "message": "Test webhook event enqueued",
            "target_url": request.target_url,
            "event_type": request.event_type,
            "status": "pending",
            "job_id": str(job.id),
        }
    except Exception as e:
        logger.exception(f"Unexpected error testing webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.get("/{webhook_id}/deliveries", response_model=List[WebhookDeliveryResponse])
async def list_webhook_deliveries(
    webhook_id: UUID,
    limit: int = 50,
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
) -> List[WebhookDeliveryResponse]:
    """List deliveries for a webhook configuration with filtering."""
    logger.info(f"Listing deliveries for webhook: {webhook_id}")
    
    authz_service = AuthzService()
    
    try:
        # Verify webhook exists and belongs to workspace
        webhook_result = await db.execute(
            select(WebhookConfig).where(
                WebhookConfig.id == webhook_id,
                WebhookConfig.workspace_id == current_workspace.id,
            )
        )
        webhook = webhook_result.scalar_one_or_none()
        
        if not webhook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook not found",
            )
        
        # Authorization check
        await authz_service.assert_resource_ownership(
            db, current_member.user_id, current_workspace.id, webhook.workspace_id
        )
        
        query = select(WebhookDelivery).where(
            WebhookDelivery.webhook_config_id == webhook_id
        )
        
        # Filter by status if provided
        if status_filter:
            try:
                status_enum = WebhookDeliveryStatus(status_filter.lower())
                query = query.where(WebhookDelivery.delivery_status == status_enum)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status_filter}. Valid values: pending, succeeded, failed",
                )
        
        query = query.order_by(WebhookDelivery.created_at.desc()).limit(limit)
        
        result = await db.execute(query)
        deliveries = result.scalars().all()
        
        return [
            WebhookDeliveryResponse(
                id=str(d.id),
                webhook_config_id=str(d.webhook_config_id),
                workspace_id=str(d.workspace_id),
                event_type=d.event_type,
                status_code=d.status_code,
                delivery_status=d.delivery_status.value,
                attempt_count=d.attempt_count,
                last_error=d.last_error,
                created_at=d.created_at.isoformat(),
                updated_at=d.updated_at.isoformat(),
            )
            for d in deliveries
        ]
    except HTTPException:
        raise
    except ProgrammingError as e:
        logger.error(f"Database schema error listing deliveries: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        logger.error(f"Database connection error listing deliveries: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        logger.exception(f"Database error listing deliveries: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list deliveries",
        )
    except Exception as e:
        logger.exception(f"Unexpected error listing deliveries: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.post("/webhook-deliveries/{delivery_id}/retry", response_model=WebhookDeliveryResponse)
async def retry_webhook_delivery(
    delivery_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
) -> WebhookDeliveryResponse:
    """Retry a failed webhook delivery by enqueuing a new job."""
    logger.info(f"Retrying webhook delivery: {delivery_id}")
    
    authz_service = AuthzService()
    job_queue_service = JobQueueService()
    
    try:
        result = await db.execute(
            select(WebhookDelivery).where(
                WebhookDelivery.id == delivery_id,
                WebhookDelivery.workspace_id == current_workspace.id,
            )
        )
        delivery = result.scalar_one_or_none()
        
        if not delivery:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook delivery not found",
            )
        
        # Authorization check
        await authz_service.assert_resource_ownership(
            db, current_member.user_id, current_workspace.id, delivery.workspace_id
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
        
        # Re-enable webhook if it was disabled
        if not webhook_config.enabled:
            webhook_config.enabled = True
        
        # Enqueue new webhook delivery job
        job = await job_queue_service.enqueue_webhook_delivery_job(
            db,
            webhook_config.target_url,
            delivery.payload,
            delivery.event_type,
            delivery.workspace_id,
            webhook_config.id,
            max_attempts=webhook_config.retry_policy.get("max_attempts", 5) if isinstance(webhook_config.retry_policy, dict) else 5,
        )
        
        await db.commit()
        await db.refresh(delivery)
        
        logger.info(f"Webhook delivery retry enqueued: {delivery_id}, job_id={job.id}")
        
        return WebhookDeliveryResponse(
            id=str(delivery.id),
            webhook_config_id=str(delivery.webhook_config_id),
            workspace_id=str(delivery.workspace_id),
            event_type=delivery.event_type,
            status_code=delivery.status_code,
            delivery_status=delivery.delivery_status.value,
            attempt_count=delivery.attempt_count,
            last_error=delivery.last_error,
            created_at=delivery.created_at.isoformat(),
            updated_at=delivery.updated_at.isoformat(),
        )
    except HTTPException:
        raise
    except ProgrammingError as e:
        await db.rollback()
        logger.error(f"Database schema error retrying delivery: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        await db.rollback()
        logger.error(f"Database connection error retrying delivery: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        await db.rollback()
        logger.exception(f"Database error retrying delivery: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retry delivery",
        )
    except Exception as e:
        await db.rollback()
        logger.exception(f"Unexpected error retrying delivery: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )

