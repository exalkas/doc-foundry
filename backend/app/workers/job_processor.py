import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Callable, Dict, Optional
from uuid import UUID

import httpx
from sqlalchemy import and_, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

import time

from app.config import settings
from app.core.storage import StorageService
from app.database import AsyncSessionLocal, engine
from app.models.document import Document, DocumentStatusEnum as DocumentStatus
from app.models.extractionlog import ExtractionLog, ExtractionLogLevel
from app.models.extractionresult import ExtractionResult
from app.models.job import Job, JobStatus, JobType
from app.models.subscription import Subscription, SubscriptionStatusEnum
from app.models.template import Template
from app.models.workspace import Workspace
from app.models.webhookconfig import WebhookConfig
from app.models.webhookdelivery import WebhookDelivery, WebhookDeliveryStatus
from app.services.extraction_service import ExtractionService, ExtractionError
from app.services.ai_template_service import AITemplateService, AITemplateGenerationError
from app.services.template_service import TemplateService
from app.services.logging_service import get_logger, log_job_event, set_correlation_id, ErrorCategory
from app.services.metrics_service import get_metrics
from app.services.plan_service import PlanService
from app.services.usage_service import UsageService

logger = get_logger(__name__)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Async context manager that yields an AsyncSession and ensures proper cleanup."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


class JobProcessor:
    """Main job processor for document extraction and webhook delivery."""

    def __init__(
        self,
        poll_interval_seconds: float = 2.0,
        batch_size: int = 10,
        stop_event: Optional[asyncio.Event] = None,
    ) -> None:
        self.poll_interval_seconds = poll_interval_seconds
        self.batch_size = batch_size
        self.stop_event = stop_event or asyncio.Event()
        self.storage = StorageService(settings.STORAGE_ROOT)
        self.extraction_service = ExtractionService()
        self.plan_service = PlanService()
        self.usage_service = UsageService()
        self.metrics = get_metrics()
        self._last_failed_job_log_time: Optional[datetime] = None

        self._job_handlers: Dict[JobType, Callable[[AsyncSession, Job], asyncio.Future]] = {
            JobType.DOCUMENT_EXTRACTION: self._handle_document_extraction_job,
            JobType.WEBHOOK_DELIVERY: self._handle_webhook_delivery_job,
            JobType.TEMPLATE_GENERATION: self._handle_template_generation_job,
        }

    async def start(self) -> None:
        """Start the job processing loop; runs until stop() is called or cancelled."""
        logger.info(f"JobProcessor starting with poll interval {self.poll_interval_seconds}s")
        poll_count = 0
        try:
            while not self.stop_event.is_set():
                try:
                    poll_count += 1
                    if poll_count % 10 == 0:  # Log every 10th poll
                        logger.info(f"JobProcessor polling (iteration {poll_count})")
                    has_work = await self._process_once()
                    if not has_work:
                        await asyncio.wait_for(
                            self.stop_event.wait(), timeout=self.poll_interval_seconds
                        )
                except asyncio.TimeoutError:
                    # normal wake-up after timeout
                    continue
                except Exception as exc:
                    logger.error(
                        f"Unexpected error in job processor loop: {exc}",
                        error_category=ErrorCategory.SYSTEM_ERROR,
                        exc_info=exc,
                    )
                    await asyncio.sleep(self.poll_interval_seconds)
        finally:
            await engine.dispose()
            logger.info("JobProcessor stopped")

    def stop(self) -> None:
        """Signal the job processor loop to stop."""
        self.stop_event.set()

    async def _process_once(self) -> bool:
        """Fetch and process a batch of jobs once. Returns True if any jobs were processed."""
        try:
            async with get_session() as session:
                # First, recover any stuck PROCESSING jobs
                await self._recover_stuck_jobs(session)
                
                jobs = await self._fetch_next_jobs(session)
                if not jobs:
                    return False

                logger.info(f"Found {len(jobs)} job(s) to process")
                for job in jobs:
                    try:
                        await self._process_single_job(session, job)
                    except Exception as exc:
                        logger.error(
                            f"Failed to process job {job.id} of type {job.type}: {exc}",
                            error_category=ErrorCategory.SYSTEM_ERROR,
                            exc_info=exc,
                        )
                return True
        except Exception as exc:
            logger.error(
                f"Error in _process_once: {exc}",
                error_category=ErrorCategory.SYSTEM_ERROR,
                exc_info=exc,
            )
            return False

    async def _recover_stuck_jobs(self, session: AsyncSession) -> None:
        """
        Recover jobs that have been stuck in PROCESSING status for too long.
        This can happen if a worker crashes or is interrupted while processing.
        """
        # Consider a job "stuck" if it's been PROCESSING for longer than configured timeout
        stuck_threshold = datetime.now(timezone.utc) - timedelta(
            minutes=settings.worker_stuck_job_timeout_minutes
        )
        
        try:
            # Use a separate transaction for recovery to avoid conflicts
            async with session.begin():
                stuck_result = await session.execute(
                    select(Job).where(
                        Job.status == JobStatus.PROCESSING,
                        Job.updated_at < stuck_threshold
                    )
                )
                stuck_jobs = list(stuck_result.scalars().all())
                
                if stuck_jobs:
                    logger.warning(
                        f"Found {len(stuck_jobs)} stuck job(s) in PROCESSING status, recovering..."
                    )
                    for job in stuck_jobs:
                        # Check if we can retry
                        if job.attempts < job.max_attempts:
                            job.status = JobStatus.QUEUED
                            job.scheduled_at = datetime.now(timezone.utc)
                            job.last_error = (
                                f"Job was stuck in PROCESSING status since {job.updated_at}. "
                                "Recovered and requeued."
                            )
                            logger.info(
                                f"Recovered stuck job {job.id} (attempt {job.attempts}/{job.max_attempts})"
                            )
                        else:
                            # Max attempts reached, mark as failed
                            job.status = JobStatus.FAILED
                            job.last_error = (
                                f"Job was stuck in PROCESSING status since {job.updated_at}. "
                                "Max attempts reached, marking as failed."
                            )
                            logger.warning(
                                f"Stuck job {job.id} exceeded max attempts, marking as failed"
                            )
                    # Transaction commits automatically when exiting the context
        except Exception as exc:
            logger.error(
                f"Error recovering stuck jobs: {exc}",
                error_category=ErrorCategory.SYSTEM_ERROR,
                exc_info=exc,
            )
            # Transaction will rollback automatically on exception

    async def _fetch_next_jobs(self, session: AsyncSession) -> list[Job]:
        """
        Fetch next batch of queued jobs using FOR UPDATE SKIP LOCKED to avoid
        contention across worker processes. Includes priority ordering.
        """
        now = datetime.now(timezone.utc)
        
        # Use raw SQL for SKIP LOCKED semantics with priority ordering
        # Priority: Pro > Starter > Free (based on payload workspace plan)
        query = text(
            """
            SELECT id
            FROM jobs
            WHERE status = :queued
              AND scheduled_at <= :now
              AND attempts < max_attempts
            ORDER BY scheduled_at ASC
            FOR UPDATE SKIP LOCKED
            LIMIT :limit
            """
        )

        try:
            async with session.begin():
                result = await session.execute(
                    query,
                    {
                        "queued": JobStatus.QUEUED.value,
                        "now": now,
                        "limit": self.batch_size,
                    },
                )
                job_ids = [row[0] for row in result.fetchall()]
                
                # If no jobs found, run diagnostic query to see what's in the database
                if not job_ids:
                    try:
                        # Check total jobs by status
                        total_result = await session.execute(select(Job))
                        all_jobs = list(total_result.scalars().all())
                        status_counts = {}
                        for job in all_jobs:
                            status_counts[job.status] = status_counts.get(job.status, 0) + 1
                        
                        # Check QUEUED jobs specifically
                        queued_result = await session.execute(
                            select(Job).where(Job.status == JobStatus.QUEUED)
                        )
                        queued_jobs = list(queued_result.scalars().all())
                        
                        if queued_jobs:
                            logger.warning(
                                f"Found {len(queued_jobs)} QUEUED jobs but query returned none. "
                                f"Status counts: {status_counts}"
                            )
                            # Show details of first few queued jobs
                            for job in queued_jobs[:3]:
                                scheduled_ok = job.scheduled_at <= now if job.scheduled_at else False
                                attempts_ok = job.attempts < job.max_attempts
                                logger.warning(
                                    f"  Job {job.id}: status={job.status}, "
                                    f"scheduled_at={job.scheduled_at} (ok: {scheduled_ok}), "
                                    f"attempts={job.attempts}/{job.max_attempts} (ok: {attempts_ok})"
                                )
                        elif all_jobs:
                            logger.info(
                                f"No QUEUED jobs found. Total jobs: {len(all_jobs)}, "
                                f"Status counts: {status_counts}"
                            )
                            # Show details of failed jobs if any (but only log occasionally to avoid spam)
                            now_log = datetime.now(timezone.utc)
                            should_log_failed = (
                                self._last_failed_job_log_time is None
                                or (now_log - self._last_failed_job_log_time).total_seconds() > 60
                            )
                            
                            if should_log_failed:
                                failed_result = await session.execute(
                                    select(Job).where(Job.status == JobStatus.FAILED)
                                )
                                failed_jobs = list(failed_result.scalars().all())
                                if failed_jobs:
                                    logger.warning(f"Found {len(failed_jobs)} FAILED job(s):")
                                    for job in failed_jobs[:3]:  # Show first 3
                                        logger.warning(
                                            f"  Job {job.id} ({job.type}): "
                                            f"attempts={job.attempts}/{job.max_attempts}, "
                                            f"error={job.last_error[:200] if job.last_error else 'No error message'}"
                                        )
                                    self._last_failed_job_log_time = now_log
                        else:
                            # No jobs found - this is normal, no need to log
                            pass
                    except Exception as diag_exc:
                        # Diagnostic query failed - log at debug level but don't fail
                        pass
                    
                    return []

                logger.info(f"Found {len(job_ids)} job ID(s) to process: {job_ids}")
                jobs_result = await session.execute(
                    select(Job).where(Job.id.in_(job_ids))
                )
                jobs: list[Job] = list(jobs_result.scalars().all())

                for job in jobs:
                    job.status = JobStatus.PROCESSING
                    job.attempts += 1
                    job.updated_at = now

                return jobs
        except SQLAlchemyError as exc:
            logger.error(
                f"Error fetching next jobs: {exc}",
                error_category=ErrorCategory.SYSTEM_ERROR,
                exc_info=exc,
            )
            return []
        except Exception as exc:
            logger.error(
                f"Unexpected error fetching next jobs: {exc}",
                error_category=ErrorCategory.SYSTEM_ERROR,
                exc_info=exc,
            )
            return []

    async def _process_single_job(self, session: AsyncSession, job: Job) -> None:
        """Dispatch processing to the appropriate handler based on job type."""
        handler = self._job_handlers.get(job.type)
        if not handler:
            logger.error(f"No handler registered for job type {job.type}")
            await self._fail_job(session, job, "No handler registered for this job type")
            return

        try:
            await handler(session, job)
        except Exception as exc:
            error_msg = str(exc)
            logger.error(
                f"Error while handling job {job.id} (type={job.type}, attempts={job.attempts}/{job.max_attempts}): {error_msg}",
                error_category=ErrorCategory.SYSTEM_ERROR,
                exc_info=exc,
            )
            await self._fail_job(session, job, error_msg)

    async def _fail_job(
        self,
        session: AsyncSession,
        job: Job,
        error_message: str,
        retry: bool = True,
    ) -> None:
        """Mark a job as failed, recording the error message.

        Args:
            session: Database session
            job: Job to fail
            error_message: Error message
            retry: Whether to retry (exponential backoff)
        """
        job.last_error = error_message[:2048]
        job.updated_at = datetime.now(timezone.utc)

        if job.attempts >= job.max_attempts:
            job.status = JobStatus.FAILED
            logger.warning(
                f"Job {job.id} reached max attempts ({job.attempts}/{job.max_attempts}) "
                f"and has been marked as failed. Error: {error_message[:200]}"
            )
        elif retry:
            # Schedule retry with exponential backoff
            delay_minutes = min(job.attempts * 5, 60)  # 5, 10, 15, ..., 60 minutes
            job.status = JobStatus.QUEUED
            job.scheduled_at = datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)
            logger.info(
                "Job %s scheduled for retry in %d minutes (attempt %d/%d)",
                job.id,
                delay_minutes,
                job.attempts,
                job.max_attempts,
            )
        else:
            job.status = JobStatus.FAILED

        try:
            await session.commit()
        except SQLAlchemyError as exc:
            logger.error(
                f"Error committing failed job {job.id}: {exc}",
                error_category=ErrorCategory.SYSTEM_ERROR,
                exc_info=exc,
            )
            await session.rollback()

    async def _succeed_job(self, session: AsyncSession, job: Job) -> None:
        """Mark a job as succeeded."""
        job.status = JobStatus.SUCCEEDED
        job.last_error = None
        job.updated_at = datetime.now(timezone.utc)
        try:
            await session.commit()
        except SQLAlchemyError as exc:
            logger.error(
                f"Error committing succeeded job {job.id}: {exc}",
                error_category=ErrorCategory.SYSTEM_ERROR,
                exc_info=exc,
            )
            await session.rollback()

    # -------------------------------------------------------------------------
    # Document Extraction Handling
    # -------------------------------------------------------------------------

    async def _handle_document_extraction_job(self, session: AsyncSession, job: Job) -> None:
        """
        Handle a document_extraction job with real OCR extraction.

        Expected payload:
        {
          "document_id": "<uuid>",
          "template_id": "<uuid>",
          "workspace_id": "<uuid>",
          "idempotency_key": "<string>"
        }
        """
        start_time = time.time()
        payload: Dict[str, Any] = job.payload or {}
        document_id = payload.get("document_id")
        workspace_id = payload.get("workspace_id")
        is_test = payload.get("is_test", False)

        if not document_id:
            raise ValueError("document_id missing from job payload")

        # Set correlation ID for logging
        correlation_id = set_correlation_id()

        log_job_event(
            logger,
            "job_started",
            job_id=str(job.id),
            workspace_id=workspace_id,
            document_id=document_id,
        )

        # Check idempotency - if already processed, skip
        if payload.get("processed_at"):
            logger.info(f"Job {job.id} already processed, skipping")
            await self._succeed_job(session, job)
            return

        doc_result = await session.execute(
            select(Document).where(
                Document.id == document_id,
                Document.deleted_at.is_(None),  # Don't process deleted documents
            )
        )
        document: Optional[Document] = doc_result.scalar_one_or_none()

        if not document:
            raise ValueError(f"Document {document_id} not found")

        # Get workspace and plan tier for usage checks
        workspace_result = await session.execute(
            select(Workspace).where(Workspace.id == document.workspace_id)
        )
        workspace = workspace_result.scalar_one_or_none()

        if not workspace or workspace.status.value in ("suspended", "canceled"):
            raise ValueError(f"Workspace {document.workspace_id} not active")

        # Get plan tier from subscription (subscriptions are per-user, not per-workspace)
        # Use workspace owner's user_id to get subscription
        plan_tier = "free"  # Default
        subscription_result = await session.execute(
            select(Subscription)
            .where(
                Subscription.user_id == workspace.owner_user_id,
                Subscription.status.in_([SubscriptionStatusEnum.ACTIVE, SubscriptionStatusEnum.TRIALING]),
            )
            .order_by(Subscription.created_at.desc())
        )
        subscription = subscription_result.scalar_one_or_none()
        if subscription:
            plan_tier = subscription.plan_id.value

        # Check usage limits before processing
        period_start = subscription.current_period_start if subscription else datetime.now(timezone.utc)
        period_end = subscription.current_period_end if subscription else datetime.now(timezone.utc) + timedelta(days=30)

        is_valid, error_msg, is_hard = await self.usage_service.check_quota_exceeded(
            session, document.workspace_id, plan_tier, period_start, period_end
        )
        if not is_valid and is_hard:
            error_msg = error_msg or "Quota exceeded"
            await self._record_extraction_failure(session, document, error_msg)
            await self._fail_job(session, job, error_msg, retry=False)
            return

        # Get template
        template = None
        template_id = payload.get("template_id") or document.template_id
        if template_id:
            template_result = await session.execute(
                select(Template).where(Template.id == template_id)
            )
            template = template_result.scalar_one_or_none()

        # Handle case when no template is provided - perform OCR-only extraction
        if not template:
            if template_id:
                # Template was specified but not found
                error_msg = f"Template not found: template_id={template_id}, document_id={document_id}. Please ensure the template exists and is assigned to the document."
                logger.error(
                    f"Template validation failed for job {job.id}: {error_msg}",
                    error_category=ErrorCategory.SYSTEM_ERROR,
                )
                await self._record_extraction_failure(session, document, error_msg)
                await self._fail_job(session, job, error_msg, retry=False)
                return
            else:
                # No template specified - perform OCR-only extraction
                logger.info(
                    f"No template provided for document {document_id}, performing OCR-only extraction"
                )
                
                # Mark document as processing
                document.status = DocumentStatus.PROCESSING
                document.updated_at = datetime.now(timezone.utc)
                await session.flush()

                try:
                    # Perform OCR extraction only
                    file_path = self.storage.resolve_path(document.storage_path)
                    from pathlib import Path
                    ext = Path(file_path).suffix.lower()
                    
                    # Get OCR language from document, default to 'eng'
                    ocr_language = document.ocr_language or "eng"
                    
                    # Use the extraction service's OCR method
                    ocr_text, ocr_metadata = await self.extraction_service._perform_ocr(
                        file_path, ext, ocr_language
                    )
                    
                    # Log block count for debugging
                    block_count = len(ocr_metadata.get("blocks", [])) if ocr_metadata else 0
                    logger.info(
                        f"OCR completed for document {document_id}: "
                        f"text_length={len(ocr_text) if ocr_text else 0}, "
                        f"blocks={block_count}, "
                        f"engine={ocr_metadata.get('engine', 'unknown')}"
                    )
                    
                    # Store raw OCR results in document
                    document.raw_ocr_text = ocr_text
                    document.raw_ocr_metadata = ocr_metadata
                    document.status = DocumentStatus.SCANNED  # OCR completed, ready for template application
                    document.last_error = None
                    document.updated_at = datetime.now(timezone.utc)
                    
                    # Create info log entry
                    log = ExtractionLog(
                        document_id=document.id,
                        level=ExtractionLogLevel.INFO,
                        message="OCR extraction completed. Template required for structured extraction.",
                        event_metadata={"ocr_metadata": ocr_metadata},
                    )
                    session.add(log)
                    
                    await session.commit()
                    
                    # Mark job payload as processed (idempotency)
                    job.payload["processed_at"] = datetime.now(timezone.utc).isoformat()
                    
                    # Record metrics
                    duration_ms = (time.time() - start_time) * 1000
                    self.metrics.record_job_processing(
                        "document_extraction",
                        duration_ms,
                        "succeeded",
                        document.workspace_id,
                    )
                    
                    log_job_event(
                        logger,
                        "job_completed",
                        job_id=str(job.id),
                        workspace_id=str(document.workspace_id),
                        document_id=str(document.id),
                        duration_ms=duration_ms,
                        result_status="ocr_complete",
                    )
                    
                    await self._succeed_job(session, job)
                    return
                    
                except Exception as exc:
                    error_msg = f"OCR extraction failed: {str(exc)}"
                    logger.error(
                        f"Error performing OCR-only extraction for job {job.id}: {exc}",
                        error_category=ErrorCategory.SYSTEM_ERROR,
                        exc_info=exc,
                    )
                    try:
                        await self._record_extraction_failure(session, document, error_msg)
                    except Exception as record_exc:
                        logger.error(
                            f"Error recording extraction failure: {record_exc}",
                            error_category=ErrorCategory.SYSTEM_ERROR,
                            exc_info=record_exc,
                        )
                        await session.rollback()
                    duration_ms = (time.time() - start_time) * 1000
                    self.metrics.record_job_processing(
                        "document_extraction", duration_ms, "failed", document.workspace_id
                    )
                    try:
                        await self._fail_job(session, job, error_msg, retry=True)
                    except Exception as fail_exc:
                        logger.error(
                            f"Error failing job: {fail_exc}",
                            error_category=ErrorCategory.SYSTEM_ERROR,
                            exc_info=fail_exc,
                        )
                        await session.rollback()
                    return

        # Mark document as processing
        document.status = DocumentStatus.PROCESSING
        document.updated_at = datetime.now(timezone.utc)
        await session.flush()

        try:
            # Run real extraction with plan tier for confidence threshold
            file_path = self.storage.resolve_path(document.storage_path)
            extraction_result = await self.extraction_service.extract(
                file_path, template, timeout_seconds=300, plan_tier=plan_tier
            )

            # Preserve OCR data from extraction result metadata
            # This ensures OCR data is always available even after extraction
            if extraction_result.metadata.get("ocr_metadata"):
                ocr_metadata = extraction_result.metadata.get("ocr_metadata", {})
                # Preserve OCR text if available
                if ocr_metadata.get("text"):
                    document.raw_ocr_text = ocr_metadata.get("text", "")
                # Always preserve full OCR metadata (includes blocks, confidence, etc.)
                document.raw_ocr_metadata = ocr_metadata

            # Store extraction result with metadata
            await self._store_extraction_result(
                session=session,
                document=document,
                extracted_json=extraction_result.extracted_data,
                template_id=template.id,
                confidence=extraction_result.confidence,
                needs_review=extraction_result.needs_review,
                metadata=extraction_result.metadata,
            )

            # Record usage (skip for test extractions)
            if not is_test:
                pages = document.pages or 1
                await self.usage_service.record_usage(
                    session,
                    document.workspace_id,
                    pages=pages,
                    documents=1,
                    project_id=document.project_id,
                    template_id=template.id,
                    source=document.source.value,
                )

            # Update template stats and document status
            # For test extractions, don't mark document as completed or update template stats
            if is_test:
                logger.info(f"[JOB_PROCESSOR] Test extraction completed for document {document.id}, keeping original status")
                # Don't change document status for tests - keep it as is (likely "scanned" or "pending")
            else:
                # Always set to COMPLETED - needs_review flag is stored in ExtractionResult metadata
                logger.info(f"[JOB_PROCESSOR] Updating document {document.id} status to COMPLETED (needs_review={extraction_result.needs_review})")
                document.status = DocumentStatus.COMPLETED
                if extraction_result.needs_review:
                    # Don't increment failure_count - extraction completed, just needs review
                    # Only increment failure_count if there were actual errors
                    if extraction_result.errors:
                        template.failure_count += 1
                    else:
                        # Low confidence but no errors - still counts as success
                        template.success_count += 1
                else:
                    template.success_count += 1
                template.last_run_at = datetime.now(timezone.utc)

            document.last_error = None
            document.updated_at = datetime.now(timezone.utc)

            # Mark job payload as processed (idempotency)
            job.payload["processed_at"] = datetime.now(timezone.utc).isoformat()

            await session.commit()

            # Record metrics
            duration_ms = (time.time() - start_time) * 1000
            self.metrics.record_job_processing(
                "document_extraction",
                duration_ms,
                "completed",
                document.workspace_id,
            )

            # Mark job as succeeded in the same transaction
            job.status = JobStatus.SUCCEEDED
            job.last_error = None
            job.updated_at = datetime.now(timezone.utc)
            
            logger.info(f"[JOB_PROCESSOR] Preparing to commit: document {document.id} status={document.status.value}, job {job.id} status={job.status.value}")
            
            # Schedule webhook delivery (skip for test extractions)
            if not is_test:
                await self._maybe_schedule_webhook(
                    session, document, extraction_result.extracted_data
                )
            
            # Commit everything together (document status, job status, extraction result, webhooks)
            commit_start = time.time()
            await session.commit()
            commit_time = (time.time() - commit_start) * 1000
            logger.info(f"[JOB_PROCESSOR] Commit completed in {commit_time:.2f}ms: document {document.id} is now {document.status.value}, job {job.id} is {job.status.value}")

            log_job_event(
                logger,
                "job_completed",
                job_id=str(job.id),
                workspace_id=str(document.workspace_id),
                template_id=str(template.id),
                document_id=str(document.id),
                duration_ms=duration_ms,
                result_status="succeeded" if not extraction_result.needs_review else "needs_review",
                confidence=extraction_result.confidence,
            )

        except ExtractionError as exc:
            error_msg = str(exc)
            try:
                await self._record_extraction_failure(session, document, error_msg)
            except Exception as record_exc:
                logger.error(
                    f"Error recording extraction failure: {record_exc}",
                    error_category=ErrorCategory.SYSTEM_ERROR,
                    exc_info=record_exc,
                )
                await session.rollback()
            duration_ms = (time.time() - start_time) * 1000
            self.metrics.record_job_processing(
                "document_extraction", duration_ms, "failed", document.workspace_id
            )
            try:
                await self._fail_job(session, job, error_msg, retry=True)
            except Exception as fail_exc:
                logger.error(
                    f"Error failing job: {fail_exc}",
                    error_category=ErrorCategory.SYSTEM_ERROR,
                    exc_info=fail_exc,
                )
                await session.rollback()
        except Exception as exc:
            error_msg = f"Unexpected error: {str(exc)}"
            logger.error(
                f"Unexpected error processing extraction job {job.id}: {exc}",
                error_category=ErrorCategory.SYSTEM_ERROR,
                exc_info=exc,
            )
            try:
                await self._record_extraction_failure(session, document, error_msg)
            except Exception as record_exc:
                logger.error(
                    f"Error recording extraction failure: {record_exc}",
                    error_category=ErrorCategory.SYSTEM_ERROR,
                    exc_info=record_exc,
                )
                await session.rollback()
            duration_ms = (time.time() - start_time) * 1000
            self.metrics.record_job_processing(
                "document_extraction", duration_ms, "failed", document.workspace_id
            )
            try:
                await self._fail_job(session, job, error_msg, retry=True)
            except Exception as fail_exc:
                logger.error(
                    f"Error failing job: {fail_exc}",
                    error_category=ErrorCategory.SYSTEM_ERROR,
                    exc_info=fail_exc,
                )
                await session.rollback()

    async def _record_extraction_failure(
        self,
        session: AsyncSession,
        document: Document,
        error_message: str,
    ) -> None:
        """Create an ExtractionLog for a failed extraction and update document status."""
        document.status = DocumentStatus.FAILED
        document.last_error = error_message[:2048]
        document.updated_at = datetime.now(timezone.utc)

        log = ExtractionLog(
            document_id=document.id,
            level=ExtractionLogLevel.ERROR,
            message="Extraction failed",
            event_metadata={"error": error_message},
        )
        session.add(log)

    async def _store_extraction_result(
        self,
        session: AsyncSession,
        document: Document,
        extracted_json: Dict[str, Any],
        template_id: Optional[UUID] = None,
        confidence: float = 0.0,
        needs_review: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Persist ExtractionResult and create an info-level ExtractionLog."""
        # Determine next version
        version_query = await session.execute(
            select(ExtractionResult.version)
            .where(ExtractionResult.document_id == document.id)
            .order_by(ExtractionResult.version.desc())
            .limit(1)
        )
        last_version = version_query.scalar_one_or_none() or 0
        new_version = last_version + 1

        template_id = template_id or document.template_id
        if not template_id:
            raise ValueError("Template ID required for extraction result")

        # Build extraction metadata
        extraction_metadata = metadata or {}
        if "needs_review" not in extraction_metadata:
            extraction_metadata["needs_review"] = needs_review
        if "confidence" not in extraction_metadata:
            extraction_metadata["confidence"] = confidence

        result = ExtractionResult(
            document_id=document.id,
            template_id=template_id,
            workspace_id=document.workspace_id,
            extracted_json=extracted_json,
            version=new_version,
            extraction_metadata=extraction_metadata,
            created_at=datetime.now(timezone.utc),
        )
        session.add(result)

        log = ExtractionLog(
            document_id=document.id,
            level=ExtractionLogLevel.INFO,
            message="Extraction succeeded",
            event_metadata={"version": new_version, "confidence": confidence},
        )
        session.add(log)

    async def _maybe_schedule_webhook(
        self,
        session: AsyncSession,
        document: Document,
        extracted_json: Dict[str, Any],
    ) -> None:
        """
        Schedule webhook_delivery jobs for:
        - Document-specific callback_url, if provided.
        - Workspace-wide webhook configs subscribed to 'extraction.completed'.
        """
        now = datetime.now(timezone.utc)
        event_type = "extraction.completed"

        payload = {
            "event_type": event_type,
            "document_id": str(document.id),
            "workspace_id": str(document.workspace_id),
            "status": document.status.value,
            "result": extracted_json,
        }

        jobs_to_add: list[Job] = []

        # 1) Document-specific callback_url
        if getattr(document, "callback_url", None):
            jobs_to_add.append(
                Job(
                    type=JobType.WEBHOOK_DELIVERY,
                    payload={
                        "target_url": document.callback_url,
                        "payload": payload,
                        "event_type": event_type,
                        "workspace_id": str(document.workspace_id),
                        "webhook_config_id": None,
                    },
                    status=JobStatus.QUEUED,
                    attempts=0,
                    max_attempts=5,
                    scheduled_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )

        # 2) Workspace WebhookConfig entries
        configs_result = await session.execute(
            select(WebhookConfig).where(
                and_(
                    WebhookConfig.workspace_id == document.workspace_id,
                    WebhookConfig.enabled.is_(True),
                )
            )
        )
        configs: list[WebhookConfig] = list(configs_result.scalars().all())

        for cfg in configs:
            try:
                events = cfg.events or []
                if event_type not in events:
                    continue
            except TypeError:
                continue

            jobs_to_add.append(
                Job(
                    type=JobType.WEBHOOK_DELIVERY,
                    payload={
                        "target_url": cfg.target_url,
                        "payload": payload,
                        "event_type": event_type,
                        "workspace_id": str(document.workspace_id),
                        "webhook_config_id": str(cfg.id),
                    },
                    status=JobStatus.QUEUED,
                    attempts=0,
                    max_attempts=cfg.retry_policy.get("max_attempts", 5)
                    if isinstance(cfg.retry_policy, dict)
                    else 5,
                    scheduled_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )

        for job in jobs_to_add:
            session.add(job)

    # -------------------------------------------------------------------------
    # Webhook Delivery Handling
    # -------------------------------------------------------------------------

    async def _handle_webhook_delivery_job(self, session: AsyncSession, job: Job) -> None:
        """
        Handle a webhook_delivery job with idempotency and metrics.

        Expected payload:
        {
          "target_url": "<url>",
          "payload": {...},
          "event_type": "extraction.completed",
          "workspace_id": "<uuid>",
          "webhook_config_id": "<uuid|null>",
          "idempotency_key": "<string>"
        }
        """
        start_time = time.time()
        payload: Dict[str, Any] = job.payload or {}
        target_url = payload.get("target_url")
        event_type = payload.get("event_type")
        workspace_id = payload.get("workspace_id")
        webhook_config_id = payload.get("webhook_config_id")
        webhook_payload = payload.get("payload")
        idempotency_key = payload.get("idempotency_key")

        if not target_url or not event_type or not workspace_id or webhook_payload is None:
            raise ValueError("Invalid webhook_delivery job payload")

        # Check idempotency
        if payload.get("processed_at"):
            logger.info(f"Webhook job {job.id} already processed, skipping")
            await self._succeed_job(session, job)
            return

        logger.info(f"Processing webhook_delivery job {job.id} to {target_url}")

        # Fetch webhook config if ID exists (for secret / retry policy)
        webhook_config: Optional[WebhookConfig] = None
        if webhook_config_id:
            cfg_result = await session.execute(
                select(WebhookConfig).where(WebhookConfig.id == webhook_config_id)
            )
            webhook_config = cfg_result.scalar_one_or_none()

            # Check if webhook is disabled due to repeated failures
            if webhook_config and not webhook_config.enabled:
                error_msg = "Webhook endpoint is disabled due to repeated failures"
                await self._fail_job(session, job, error_msg, retry=False)
                return

        signature_headers: Dict[str, str] = {}
        if webhook_config:
            # Generate HMAC signature
            import hmac
            import hashlib
            payload_str = json.dumps(webhook_payload, sort_keys=True)
            signature = hmac.new(
                webhook_config.secret.encode(),
                payload_str.encode(),
                hashlib.sha256,
            ).hexdigest()
            signature_headers["X-DocFoundry-Workspace"] = str(workspace_id)
            signature_headers["X-DocFoundry-Event"] = event_type
            signature_headers["X-DocFoundry-Webhook-Id"] = str(webhook_config.id)
            signature_headers["X-DocFoundry-Signature"] = f"sha256={signature}"

        # Create or update WebhookDelivery record
        delivery: Optional[WebhookDelivery] = None
        if webhook_config_id:
            delivery_result = await session.execute(
                select(WebhookDelivery).where(
                    and_(
                        WebhookDelivery.webhook_config_id == webhook_config_id,
                        WebhookDelivery.event_type == event_type,
                    )
                ).order_by(WebhookDelivery.created_at.desc())
            )
            delivery = delivery_result.scalar_one_or_none()

        now = datetime.now(timezone.utc)
        if not delivery:
            # WebhookDelivery requires webhook_config_id, so we need a config
            if not webhook_config:
                # Create a temporary config for document callback URLs
                # In production, you might want to handle this differently
                error_msg = "Webhook config required for delivery tracking"
                await self._fail_job(session, job, error_msg, retry=False)
                return

            delivery = WebhookDelivery(
                webhook_config_id=webhook_config.id,
                workspace_id=UUID(workspace_id) if isinstance(workspace_id, str) else workspace_id,
                event_type=event_type,
                payload=webhook_payload,
                status_code=None,
                delivery_status=WebhookDeliveryStatus.PENDING,
                attempt_count=0,
                last_error=None,
                created_at=now,
                updated_at=now,
            )
            session.add(delivery)

        delivery.attempt_count += 1
        delivery.updated_at = now

        # Send HTTP POST request
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(10.0, connect=5.0),
                verify=True,
            ) as client:
                response = await client.post(
                    target_url,
                    headers={
                        "Content-Type": "application/json",
                        **signature_headers,
                    },
                    content=json.dumps(webhook_payload),
                )

            duration_ms = (time.time() - start_time) * 1000
            delivery.status_code = response.status_code

            if 200 <= response.status_code < 300:
                delivery.delivery_status = WebhookDeliveryStatus.SUCCEEDED
                delivery.last_error = None
                job.payload["processed_at"] = datetime.now(timezone.utc).isoformat()
                await self._succeed_job(session, job)

                # Record metrics
                self.metrics.record_webhook_delivery(
                    response.status_code, duration_ms, UUID(workspace_id) if isinstance(workspace_id, str) else workspace_id
                )

                logger.info(
                    "Webhook delivery %s to %s succeeded with status %s",
                    delivery.id,
                    target_url,
                    response.status_code,
                )
            else:
                error_msg = f"Non-2xx response: {response.status_code}"
                delivery.delivery_status = WebhookDeliveryStatus.FAILED
                delivery.last_error = error_msg[:2048]

                # Record metrics
                self.metrics.record_webhook_delivery(
                    response.status_code, duration_ms, UUID(workspace_id) if isinstance(workspace_id, str) else workspace_id
                )

                # Check if we should disable webhook after repeated failures
                if delivery.attempt_count >= 5 and webhook_config:
                    webhook_config.enabled = False
                    logger.warning(
                        "Disabling webhook %s after %d failures",
                        webhook_config.id,
                        delivery.attempt_count,
                    )

                await self._fail_job(session, job, error_msg, retry=True)
                logger.warning(
                    "Webhook delivery %s to %s failed with status %s",
                    delivery.id,
                    target_url,
                    response.status_code,
                )

        except httpx.RequestError as exc:
            duration_ms = (time.time() - start_time) * 1000
            error_msg = f"HTTP error: {exc}"
            delivery.delivery_status = WebhookDeliveryStatus.FAILED
            delivery.last_error = error_msg[:2048]

            # Record metrics
            self.metrics.record_webhook_delivery(0, duration_ms, UUID(workspace_id) if isinstance(workspace_id, str) else workspace_id)

            await self._fail_job(session, job, error_msg, retry=True)
            logger.error(
                f"Webhook delivery {delivery.id} to {target_url} encountered HTTP error",
                error_category=ErrorCategory.EXTERNAL_ERROR,
                exc_info=exc,
            )

        try:
            await session.commit()
        except SQLAlchemyError as exc:
            logger.error(
                f"Error committing webhook delivery {delivery.id} changes: {exc}",
                error_category=ErrorCategory.SYSTEM_ERROR,
                exc_info=exc,
            )
            await session.rollback()

    async def _handle_template_generation_job(self, session: AsyncSession, job: Job) -> None:
        """
        Handle a template_generation job.

        Expected payload:
        {
          "document_id": "<uuid>",
          "workspace_id": "<uuid>",
          "user_id": "<uuid>",
          "export_format": "json|csv|excel",
          "template_name": "<string>",
          "description": "<string>",
          "idempotency_key": "<string>"
        }
        """
        start_time = time.time()
        payload: Dict[str, Any] = job.payload or {}
        document_id = payload.get("document_id")
        workspace_id = payload.get("workspace_id")
        user_id = payload.get("user_id")
        export_format = payload.get("export_format", "json")
        template_name = payload.get("template_name")
        description = payload.get("description")

        if not document_id or not workspace_id or not user_id:
            raise ValueError("document_id, workspace_id, and user_id required in job payload")

        # Set correlation ID for logging
        correlation_id = set_correlation_id()

        log_job_event(
            logger,
            "job_started",
            job_id=str(job.id),
            workspace_id=workspace_id,
            document_id=document_id,
        )

        # Check idempotency
        if payload.get("processed_at"):
            logger.info(f"Template generation job {job.id} already processed, skipping")
            await self._succeed_job(session, job)
            return

        # Get document
        doc_result = await session.execute(
            select(Document).where(
                Document.id == UUID(document_id) if isinstance(document_id, str) else document_id,
                Document.workspace_id == UUID(workspace_id) if isinstance(workspace_id, str) else workspace_id,
            )
        )
        document: Optional[Document] = doc_result.scalar_one_or_none()

        if not document:
            raise ValueError(f"Document {document_id} not found")

        # Check if document has OCR text
        if not document.raw_ocr_text or not document.raw_ocr_text.strip():
            error_msg = "Document has no OCR text. Please ensure the document has been processed."
            await self._fail_job(session, job, error_msg, retry=False)
            return

        # Check if template already exists
        if document.template_id:
            error_msg = "Document already has a template assigned. Remove the template first to generate a new one."
            await self._fail_job(session, job, error_msg, retry=False)
            return

        # Get OCR blocks if available
        ocr_blocks = None
        if document.raw_ocr_metadata and "blocks" in document.raw_ocr_metadata:
            ocr_blocks = document.raw_ocr_metadata["blocks"]

        # Generate template using AI
        ai_service = AITemplateService()
        template_service = TemplateService()
        try:
            field_schema = await ai_service.generate_template_from_ocr(
                ocr_text=document.raw_ocr_text,
                ocr_blocks=ocr_blocks,
                export_format=export_format,
                document_type_hint=document.file_name,
            )
        except AITemplateGenerationError as e:
            error_msg = f"AI template generation failed: {str(e)}"
            logger.error(error_msg)
            await self._fail_job(session, job, error_msg, retry=True)
            return

        # Validate generated schema
        is_valid, errors = template_service.validate_field_schema(field_schema)
        if not is_valid:
            error_msg = f"Generated template schema is invalid: {', '.join(errors)}"
            logger.error(error_msg)
            await self._fail_job(session, job, error_msg, retry=False)
            return

        # Generate template name if not provided
        if not template_name:
            template_name = f"Template from {document.file_name}"
        if len(template_name) > 255:
            template_name = template_name[:252] + "..."

        # Add metadata to field_schema indicating this is AI-generated
        if isinstance(field_schema, dict):
            if "_metadata" not in field_schema:
                field_schema["_metadata"] = {}
            field_schema["_metadata"]["ai_generated"] = True
            field_schema["_metadata"]["generated_at"] = datetime.now(timezone.utc).isoformat()

        # Convert export_format string to enum
        try:
            from app.models.template import ExportFormatEnum
            export_format_enum = ExportFormatEnum(export_format.lower())
        except ValueError:
            export_format_enum = ExportFormatEnum.JSON

        # Create template
        template = Template(
            workspace_id=UUID(workspace_id) if isinstance(workspace_id, str) else workspace_id,
            project_id=document.project_id,
            name=template_name,
            description=description or f"Auto-generated template from document: {document.file_name}",
            document_type=None,
            field_schema=field_schema,
            default_export_format=export_format_enum,
            created_by_user_id=UUID(user_id) if isinstance(user_id, str) else user_id,
        )

        session.add(template)
        await session.flush()

        # Mark job payload as processed (idempotency)
        job.payload["processed_at"] = datetime.now(timezone.utc).isoformat()
        job.payload["template_id"] = str(template.id)

        # Record metrics
        duration_ms = (time.time() - start_time) * 1000
        self.metrics.record_job_processing(
            "template_generation",
            duration_ms,
            "succeeded",
            UUID(workspace_id) if isinstance(workspace_id, str) else workspace_id,
        )

        log_job_event(
            logger,
            "job_completed",
            job_id=str(job.id),
            workspace_id=workspace_id,
            document_id=str(document.id),
            duration_ms=duration_ms,
            template_id=str(template.id),
        )

        await self._succeed_job(session, job)
        logger.info(f"Template generated successfully: {template.id} from job {job.id}")


async def run_worker() -> None:
    """
    Entrypoint used by a dedicated worker process.

    Example usage:
        python -m app.workers.job_processor
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    
    # Test database connection before starting
    try:
        logger.info("Testing database connection...")
        async with get_session() as session:
            result = await session.execute(text("SELECT 1"))
            result.fetchone()
        logger.info("Database connection test successful")
    except Exception as exc:
        logger.error(
            f"Failed to connect to database: {exc}",
            error_category=ErrorCategory.SYSTEM_ERROR,
            exc_info=exc,
        )
        raise
    
    processor = JobProcessor(
        poll_interval_seconds=settings.worker_poll_interval_seconds,
        batch_size=settings.worker_batch_size,
    )
    await processor.start()


if __name__ == "__main__":
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Job worker interrupted by user")