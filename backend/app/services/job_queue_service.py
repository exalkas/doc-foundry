"""Job queue service for enqueueing extraction jobs with validation and idempotency."""

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobStatus, JobType
from app.services.plan_service import PlanService
from app.services.usage_service import UsageService

logger = logging.getLogger(__name__)


class JobQueueError(Exception):
    """Base exception for job queue errors."""

    pass


class QuotaExceededError(JobQueueError):
    """Raised when workspace quota is exceeded."""

    pass


class JobQueueService:
    """Service for enqueueing and managing extraction jobs."""

    def __init__(
        self,
        plan_service: Optional[PlanService] = None,
        usage_service: Optional[UsageService] = None,
    ):
        """Initialize job queue service.

        Args:
            plan_service: Plan service instance
            usage_service: Usage service instance
        """
        self.plan_service = plan_service or PlanService()
        self.usage_service = usage_service or UsageService()

    def generate_idempotency_key(
        self,
        document_id: UUID,
        template_id: Optional[UUID],
        workspace_id: UUID,
    ) -> str:
        """Generate an idempotency key for a job.

        Args:
            document_id: Document ID
            template_id: Optional template ID
            workspace_id: Workspace ID

        Returns:
            Idempotency key string
        """
        key_data = f"{workspace_id}:{document_id}:{template_id or 'none'}"
        return hashlib.sha256(key_data.encode()).hexdigest()

    async def enqueue_extraction_job(
        self,
        session: AsyncSession,
        document_id: UUID,
        workspace_id: UUID,
        template_id: Optional[UUID] = None,
        plan_tier: str = "free",
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
        check_quota: bool = True,
        is_test: bool = False,
    ) -> Job:
        """Enqueue a document extraction job.

        Args:
            session: Database session
            document_id: Document ID to extract
            workspace_id: Workspace ID
            template_id: Optional template ID
            plan_tier: Plan tier identifier
            period_start: Billing period start (for quota checks)
            period_end: Billing period end (for quota checks)
            check_quota: Whether to check quota before enqueueing
            is_test: Whether this is a test extraction (won't mark document as completed)

        Returns:
            Created Job object

        Raises:
            QuotaExceededError: If quota is exceeded and hard limit is enforced
            JobQueueError: If job creation fails
        """
        # Check quota if enabled
        if check_quota:
            if period_start and period_end:
                is_valid, error_msg, is_hard = await self.usage_service.check_quota_exceeded(
                    session, workspace_id, plan_tier, period_start, period_end
                )
                if not is_valid and is_hard:
                    raise QuotaExceededError(error_msg or "Quota exceeded")

        # Generate idempotency key
        idempotency_key = self.generate_idempotency_key(
            document_id, template_id, workspace_id
        )

        # Check if job with same idempotency key already exists
        # Query all queued/processing jobs and check payload in Python
        # (PostgreSQL JSONB queries can be complex, so we filter in code for now)
        existing_result = await session.execute(
            select(Job).where(
                Job.type == JobType.DOCUMENT_EXTRACTION,
                Job.status.in_([JobStatus.QUEUED, JobStatus.PROCESSING]),
            )
        )
        existing_jobs = existing_result.scalars().all()
        existing_job = None
        for job in existing_jobs:
            if job.payload.get("idempotency_key") == idempotency_key:
                existing_job = job
                break

        if existing_job:
            logger.info(
                "Job with idempotency key %s already exists: %s",
                idempotency_key,
                existing_job.id,
            )
            return existing_job

        # Get plan limits for retry configuration
        max_attempts = self.plan_service.get_max_retries(plan_tier)

        # Create job payload
        payload: Dict[str, Any] = {
            "document_id": str(document_id),
            "workspace_id": str(workspace_id),
            "idempotency_key": idempotency_key,
            "is_test": is_test,
        }
        if template_id:
            payload["template_id"] = str(template_id)

        # Create job
        job = Job(
            id=uuid.uuid4(),
            type=JobType.DOCUMENT_EXTRACTION,
            payload=payload,
            status=JobStatus.QUEUED,
            attempts=0,
            max_attempts=max_attempts,
            scheduled_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        session.add(job)
        await session.flush()

        logger.info(
            "Enqueued extraction job: id=%s, document=%s, workspace=%s, template=%s",
            job.id,
            document_id,
            workspace_id,
            template_id,
        )

        return job

    async def enqueue_webhook_delivery_job(
        self,
        session: AsyncSession,
        target_url: str,
        payload: Dict[str, Any],
        event_type: str,
        workspace_id: UUID,
        webhook_config_id: Optional[UUID] = None,
        max_attempts: int = 5,
    ) -> Job:
        """Enqueue a webhook delivery job.

        Args:
            session: Database session
            target_url: Webhook target URL
            payload: Webhook payload
            event_type: Event type identifier
            workspace_id: Workspace ID
            webhook_config_id: Optional webhook config ID
            max_attempts: Maximum retry attempts

        Returns:
            Created Job object
        """
        # Generate idempotency key for webhook
        key_data = f"{workspace_id}:{webhook_config_id or 'none'}:{event_type}:{target_url}"
        idempotency_key = hashlib.sha256(key_data.encode()).hexdigest()

        # Check for existing job
        existing_result = await session.execute(
            select(Job).where(
                Job.type == JobType.WEBHOOK_DELIVERY,
                Job.status.in_([JobStatus.QUEUED, JobStatus.PROCESSING]),
            )
        )
        existing_jobs = existing_result.scalars().all()
        existing_job = None
        for job in existing_jobs:
            if job.payload.get("idempotency_key") == idempotency_key:
                existing_job = job
                break

        if existing_job:
            logger.info(
                "Webhook job with idempotency key %s already exists: %s",
                idempotency_key,
                existing_job.id,
            )
            return existing_job

        # Create job payload
        job_payload: Dict[str, Any] = {
            "target_url": target_url,
            "payload": payload,
            "event_type": event_type,
            "workspace_id": str(workspace_id),
            "idempotency_key": idempotency_key,
        }
        if webhook_config_id:
            job_payload["webhook_config_id"] = str(webhook_config_id)

        # Create job
        job = Job(
            id=uuid.uuid4(),
            type=JobType.WEBHOOK_DELIVERY,
            payload=job_payload,
            status=JobStatus.QUEUED,
            attempts=0,
            max_attempts=max_attempts,
            scheduled_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        session.add(job)
        await session.flush()

        logger.info(
            "Enqueued webhook delivery job: id=%s, target_url=%s, event_type=%s",
            job.id,
            target_url,
            event_type,
        )

        return job

    async def enqueue_template_generation_job(
        self,
        session: AsyncSession,
        document_id: UUID,
        workspace_id: UUID,
        user_id: UUID,
        export_format: str = "json",
        template_name: Optional[str] = None,
        description: Optional[str] = None,
        plan_tier: str = "free",
    ) -> Job:
        """Enqueue a template generation job.

        Args:
            session: Database session
            document_id: Document ID to generate template from
            workspace_id: Workspace ID
            user_id: User ID requesting the generation
            export_format: Export format (json, csv, excel)
            template_name: Optional template name
            description: Optional template description
            plan_tier: Plan tier identifier

        Returns:
            Created Job object
        """
        # Generate idempotency key
        key_data = f"{workspace_id}:{document_id}:template_generation"
        idempotency_key = hashlib.sha256(key_data.encode()).hexdigest()

        # Check for existing job
        existing_result = await session.execute(
            select(Job).where(
                Job.type == JobType.TEMPLATE_GENERATION,
                Job.status.in_([JobStatus.QUEUED, JobStatus.PROCESSING]),
            )
        )
        existing_jobs = existing_result.scalars().all()
        existing_job = None
        for job in existing_jobs:
            if job.payload.get("idempotency_key") == idempotency_key:
                existing_job = job
                break

        if existing_job:
            logger.info(
                "Template generation job with idempotency key %s already exists: %s",
                idempotency_key,
                existing_job.id,
            )
            return existing_job

        # Get plan limits for retry configuration
        max_attempts = self.plan_service.get_max_retries(plan_tier)

        # Create job payload
        payload: Dict[str, Any] = {
            "document_id": str(document_id),
            "workspace_id": str(workspace_id),
            "user_id": str(user_id),
            "export_format": export_format,
            "idempotency_key": idempotency_key,
        }
        if template_name:
            payload["template_name"] = template_name
        if description:
            payload["description"] = description

        # Create job
        job = Job(
            id=uuid.uuid4(),
            type=JobType.TEMPLATE_GENERATION,
            payload=payload,
            status=JobStatus.QUEUED,
            attempts=0,
            max_attempts=max_attempts,
            scheduled_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        session.add(job)
        await session.flush()

        logger.info(
            "Enqueued template generation job: id=%s, document=%s, workspace=%s",
            job.id,
            document_id,
            workspace_id,
        )

        return job

    async def retry_job(
        self,
        session: AsyncSession,
        job_id: UUID,
        delay_minutes: Optional[int] = None,
    ) -> Job:
        """Retry a failed job.

        Args:
            session: Database session
            job_id: Job ID to retry
            delay_minutes: Optional delay before retry (exponential backoff)

        Returns:
            Updated Job object

        Raises:
            JobQueueError: If job not found or cannot be retried
        """
        result = await session.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()

        if not job:
            raise JobQueueError(f"Job not found: {job_id}")

        if job.status == JobStatus.SUCCEEDED:
            raise JobQueueError(f"Job already succeeded: {job_id}")

        if job.attempts >= job.max_attempts:
            raise JobQueueError(f"Job exceeded max attempts: {job_id}")

        # Calculate delay (exponential backoff)
        if delay_minutes is None:
            delay_minutes = min(job.attempts * 5, 60)  # 5, 10, 15, ..., 60 minutes

        # Reset job status
        job.status = JobStatus.QUEUED
        job.scheduled_at = datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)
        job.last_error = None
        job.updated_at = datetime.now(timezone.utc)

        await session.flush()

        logger.info(
            "Retried job: id=%s, attempts=%d, scheduled_at=%s",
            job.id,
            job.attempts,
            job.scheduled_at,
        )

        return job

