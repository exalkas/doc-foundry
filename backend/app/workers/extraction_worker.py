import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import and_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.storage import StorageService
from app.database import get_async_session
from app.models.document import Document, DocumentStatus
from app.models.extractionlog import ExtractionLog, ExtractionLogLevel
from app.models.extractionresult import ExtractionResult
from app.models.job import Job, JobStatus, JobType
from app.models.template import Template
from app.services.usage_service import UsageService
from app.models.workspace import Workspace
from app.models.subscription import Subscription
from app.services.extraction_service import ExtractionService, ExtractionError, OCRProcessingError
from app.services.plan_service import PlanService
from app.workers.job_processor import BaseWorker

logger = logging.getLogger(__name__)


class ExtractionEngine:
    """Real OCR/ML-based extraction engine using ExtractionService."""

    def __init__(self):
        """Initialize extraction engine with real OCR service."""
        self.storage = StorageService(settings.STORAGE_ROOT)
        self.extraction_service = ExtractionService()
        self.plan_service = PlanService()

    async def extract(
        self,
        file_path: str,
        template: Template,
        plan_tier: str = "free",
        ocr_language: str = "eng",
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Perform extraction on a local file using the given template.

        Args:
            file_path: Storage path to the document file
            template: Template model with field_schema
            plan_tier: Plan tier for confidence threshold calculation
            ocr_language: Language code (e.g., 'eng', 'ell' for Greek, 'en', 'el')

        Returns:
            A tuple of (extracted_json, debug_metadata)

        Raises:
            ExtractionError: If extraction fails
        """
        try:
            # Resolve full file path
            full_path = self.storage.resolve_path(file_path)
            
            # Perform real OCR extraction using ExtractionService
            extraction_result = await self.extraction_service.extract(
                file_path=full_path,
                template=template,
                timeout_seconds=300,
                plan_tier=plan_tier,
                ocr_language=ocr_language,
            )

            # Extract the structured data
            extracted_json = extraction_result.extracted_data

            # Get OCR metadata (contains blocks and other OCR info)
            ocr_metadata = extraction_result.metadata.get("ocr_metadata", {})
            
            # Build metadata from extraction result
            metadata = {
                "engine": extraction_result.metadata.get("engine", "google_vision"),
                "template_id": str(template.id),
                "field_count": len(extracted_json),
                "confidence": extraction_result.confidence,
                "needs_review": extraction_result.needs_review,
                "processing_time_seconds": extraction_result.metadata.get("processing_time_seconds"),
                "ocr_metadata": ocr_metadata,
                "errors": extraction_result.errors,
                "warnings": extraction_result.warnings,
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "file_path": file_path,
            }

            return extracted_json, metadata

        except OCRProcessingError as e:
            logger.error(f"OCR processing failed: {e}")
            raise ExtractionError(f"OCR processing failed: {str(e)}") from e
        except ExtractionError:
            raise
        except Exception as e:
            logger.exception(f"Unexpected error during extraction: {e}")
            raise ExtractionError(f"Extraction failed: {str(e)}") from e


class ExtractionWorker(BaseWorker):
    """Worker process that pulls `document_extraction` jobs and processes them."""

    def __init__(
        self,
        poll_interval_seconds: float = 2.0,
        batch_size: int = 5,
        engine: Optional[ExtractionEngine] = None,
        usage_service: Optional[UsageService] = None,
    ) -> None:
        super().__init__(poll_interval_seconds=poll_interval_seconds)
        self.batch_size = batch_size
        self.engine = engine or ExtractionEngine()
        self.usage_service = usage_service or UsageService()

    async def _acquire_jobs(self, session: AsyncSession) -> list[Job]:
        """Acquire a batch of queued document_extraction jobs in a transactional way."""
        now = datetime.now(timezone.utc)
        try:
            async with session.begin():
                result = await session.execute(
                    select(Job)
                    .where(
                        and_(
                            Job.type == JobType.DOCUMENT_EXTRACTION,
                            Job.status == JobStatus.QUEUED,
                            Job.scheduled_at <= now,
                        )
                    )
                    .order_by(Job.created_at)
                    .limit(self.batch_size)
                    .with_for_update(skip_locked=True)
                )
                jobs = list(result.scalars().all())
                for job in jobs:
                    job.status = JobStatus.PROCESSING
                    job.attempts += 1
                    job.updated_at = now
                return jobs
        except SQLAlchemyError:
            logger.exception("Failed to acquire extraction jobs from queue")
            await session.rollback()
            return []

    async def _process_job(self, session: AsyncSession, job: Job) -> None:
        """Process a single document_extraction job."""
        payload = job.payload or {}
        document_id = payload.get("document_id")
        template_id = payload.get("template_id")

        if not document_id:
            await self._fail_job(
                session,
                job,
                "Invalid payload: missing document_id",
            )
            return

        try:
            document = await session.get(Document, document_id)
            if not document:
                await self._fail_job(
                    session,
                    job,
                    f"Document {document_id} not found",
                )
                return

            if template_id:
                template = await session.get(Template, template_id)
            else:
                template = (
                    await session.get(Template, document.template_id)
                    if document.template_id
                    else None
                )

            if not template:
                await self._fail_job(
                    session,
                    job,
                    "No template associated with document or payload",
                    document=document,
                )
                return

            workspace = await session.get(Workspace, document.workspace_id)
            if not workspace or workspace.status in ("suspended", "canceled"):
                await self._fail_job(
                    session,
                    job,
                    f"Workspace {document.workspace_id} not active",
                    document=document,
                )
                return

            # Get plan tier for confidence threshold (subscriptions are per-user, not per-workspace)
            plan_tier = "free"
            # Get workspace owner to find user subscription
            workspace_result = await session.execute(
                select(Workspace).where(Workspace.id == document.workspace_id)
            )
            workspace = workspace_result.scalar_one_or_none()
            
            if workspace:
                subscription = await session.execute(
                    select(Subscription).where(
                        and_(
                            Subscription.user_id == workspace.owner_user_id,
                            Subscription.status.in_(["active", "trialing"])
                        )
                    ).order_by(Subscription.created_at.desc()).limit(1)
                )
                sub = subscription.scalar_one_or_none()
                if sub:
                    plan_tier = sub.plan_id.lower() if sub.plan_id else "free"

            document.status = DocumentStatus.PROCESSING
            document.last_error = None
            document.updated_at = datetime.now(timezone.utc)
            await session.flush()

            try:
                # Get OCR language from document, default to 'eng'
                ocr_language = document.ocr_language or "eng"
                extracted_json, metadata = await self.engine.extract(
                    file_path=document.storage_path,
                    template=template,
                    plan_tier=plan_tier,
                    ocr_language=ocr_language,
                )

                # Store raw OCR text and metadata if available
                ocr_metadata = metadata.get("ocr_metadata", {})
                
                if ocr_metadata:
                    # Store OCR text if available
                    ocr_text = ocr_metadata.get("text")
                    if ocr_text and not document.raw_ocr_text:
                        document.raw_ocr_text = ocr_text
                    elif ocr_metadata.get("blocks") and not document.raw_ocr_text:
                        # Reconstruct OCR text from blocks as fallback
                        blocks = ocr_metadata.get("blocks", [])
                        if blocks:
                            ocr_text_parts = [block.get("text", "") for block in blocks if block.get("text")]
                            document.raw_ocr_text = "\n".join(ocr_text_parts)
                    
                    # Store OCR metadata including blocks (but not the text itself, it's in raw_ocr_text)
                    ocr_metadata_to_store = {k: v for k, v in ocr_metadata.items() if k != "text"}
                    if not document.raw_ocr_metadata:
                        document.raw_ocr_metadata = ocr_metadata_to_store
                    else:
                        # Merge with existing metadata, preserving blocks
                        existing = document.raw_ocr_metadata or {}
                        document.raw_ocr_metadata = {
                            **existing,
                            **ocr_metadata_to_store,
                            # Preserve blocks if they exist (blocks are the most important)
                            "blocks": ocr_metadata.get("blocks") or existing.get("blocks", []),
                        }

                # Determine document status based on extraction result
                needs_review = metadata.get("needs_review", False)
                confidence = metadata.get("confidence", 0.0)
                
                # Store extraction metadata including needs_review flag and confidence
                extraction_metadata = {
                    "needs_review": needs_review,
                    "confidence": confidence,
                    "field_confidences": metadata.get("field_confidences", {}),
                    "errors": metadata.get("errors", []),
                    "warnings": metadata.get("warnings", []),
                    "engine": metadata.get("engine", "google_vision"),
                }
                
                # Create extraction result
                extraction_result = ExtractionResult(
                    document_id=document.id,
                    template_id=template.id,
                    workspace_id=document.workspace_id,
                    extracted_json=extracted_json,
                    version=1,
                    extraction_metadata=extraction_metadata,
                    created_at=datetime.now(timezone.utc),
                )
                session.add(extraction_result)

                # Log extraction with appropriate level
                log_level = ExtractionLogLevel.WARNING if needs_review else ExtractionLogLevel.INFO
                log_message = "Extraction succeeded"
                if needs_review:
                    log_message = f"Extraction completed but needs review (confidence: {confidence:.2f})"
                elif metadata.get("warnings"):
                    log_message = f"Extraction succeeded with warnings: {', '.join(metadata.get('warnings', []))}"

                await self._log_extraction(
                    session=session,
                    document=document,
                    level=log_level,
                    message=log_message,
                    metadata=metadata,
                )

                # Log any errors as warnings
                if metadata.get("errors"):
                    for error in metadata.get("errors", []):
                        await self._log_extraction(
                            session=session,
                            document=document,
                            level=ExtractionLogLevel.ERROR,
                            message=f"Extraction error: {error}",
                            metadata={"error": error},
                        )

                # Determine if AI extraction was used based on metadata
                is_ai_extraction = metadata.get("engine") == "llm"
                pages = document.pages or 1
                ai_pages = pages if is_ai_extraction else 0
                
                # Record usage with AI pages tracked separately
                await self.usage_service.record_usage(
                    session=session,
                    workspace_id=document.workspace_id,
                    pages=pages,
                    documents=1,
                    ai_pages=ai_pages,
                )

                # Update template stats and document status
                # Always set to COMPLETED - needs_review flag is stored in ExtractionResult metadata
                document.status = DocumentStatus.COMPLETED
                if needs_review:
                    # Don't increment failure_count - extraction completed, just needs review
                    # Only increment failure_count if there were actual errors
                    if metadata.get("errors"):
                        template.failure_count += 1
                    else:
                        # Low confidence but no errors - still counts as success
                        template.success_count += 1
                else:
                    template.success_count += 1
                
                template.last_run_at = datetime.now(timezone.utc)
                document.updated_at = datetime.now(timezone.utc)

                job.status = JobStatus.SUCCEEDED
                job.last_error = None
                job.updated_at = datetime.now(timezone.utc)

                await session.commit()

            except ExtractionError as e:
                # Handle extraction errors
                error_message = str(e)
                logger.error(f"Extraction failed for document {document_id}: {error_message}")
                
                await self._log_extraction(
                    session=session,
                    document=document,
                    level=ExtractionLogLevel.ERROR,
                    message=f"Extraction failed: {error_message}",
                    metadata={"error": error_message, "job_id": str(job.id)},
                )
                
                template.failure_count += 1
                document.status = DocumentStatus.FAILED
                document.last_error = error_message
                document.updated_at = datetime.now(timezone.utc)
                
                await self._fail_job(session, job, error_message, document=document)
                await session.commit()

        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected error while processing extraction job %s", job.id)
            await session.rollback()
            # Reload entities to avoid stale state
            async with session.begin():
                job_db = await session.get(Job, job.id, with_for_update=True)
                document_db = None
                if document_id:
                    document_db = await session.get(Document, document_id, with_for_update=True)
                await self._handle_job_exception(session, job_db, document_db, exc)
                await session.commit()

    async def _fail_job(
        self,
        session: AsyncSession,
        job: Job,
        error_message: str,
        document: Optional[Document] = None,
    ) -> None:
        """Mark a job (and optionally its document) as failed with an error message."""
        now = datetime.now(timezone.utc)
        job.last_error = error_message
        job.updated_at = now

        if job.attempts >= job.max_attempts:
            job.status = JobStatus.FAILED
        else:
            # Simple backoff: schedule next attempt in N * 60 seconds
            delay_minutes = min(job.attempts, 10)
            job.status = JobStatus.QUEUED
            job.scheduled_at = now.replace(microsecond=0) + (
                delay_minutes * 60  # type: ignore[operator]
            )  # naive; depends on DB adapter

        if document:
            document.status = DocumentStatus.FAILED
            document.last_error = error_message
            document.updated_at = now

            await self._log_extraction(
                session=session,
                document=document,
                level=ExtractionLogLevel.ERROR,
                message=error_message,
                metadata={"job_id": str(job.id)},
            )

        await session.commit()

    async def _handle_job_exception(
        self,
        session: AsyncSession,
        job: Optional[Job],
        document: Optional[Document],
        exc: Exception,
    ) -> None:
        """Handle unexpected exception during job processing."""
        if not job:
            return

        error_message = str(exc)[:1024]
        await self._fail_job(
            session=session,
            job=job,
            error_message=error_message,
            document=document,
        )

    async def _log_extraction(
        self,
        session: AsyncSession,
        document: Document,
        level: ExtractionLogLevel,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Create an ExtractionLog entry for a document."""
        log_entry = ExtractionLog(
            document_id=document.id,
            level=level,
            message=message,
            metadata=metadata,
            created_at=datetime.now(timezone.utc),
        )
        session.add(log_entry)


    async def run_once(self) -> None:
        """Run a single polling/processing cycle."""
        async for session in get_async_session():
            jobs = await self._acquire_jobs(session)
            if not jobs:
                return

            for job in jobs:
                await self._process_job(session, job)

    async def start(self) -> None:
        """Start the worker loop, polling and processing jobs indefinitely."""
        logger.info("Starting ExtractionWorker loop with interval=%ss", self.poll_interval_seconds)
        while not self._stopped.is_set():
            try:
                await self.run_once()
            except Exception:  # pragma: no cover - defensive
                logger.exception("Unhandled error in ExtractionWorker loop")

            await asyncio.wait(
                [self._stopped.wait()],
                timeout=self.poll_interval_seconds,
            )


async def main() -> None:
    """Entry point for running the extraction worker as a standalone process."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    worker = ExtractionWorker()
    await worker.start()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())