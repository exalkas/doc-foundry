import asyncio
import hmac
import json
import logging
from hashlib import sha256
from typing import Any, Dict, Optional

import httpx
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.models import AuditLog, Job, WebhookConfig, WebhookDelivery

logger = logging.getLogger(__name__)


class WebhookWorker:
    """
    Worker responsible for processing `webhook_delivery` jobs from the Job queue.

    It will:
      - Load the relevant WebhookDelivery + WebhookConfig records.
      - Compute an HMAC-SHA256 signature over the payload.
      - POST the payload to the configured target_url with signature headers.
      - Update WebhookDelivery with status, attempt_count, and errors.
      - Update Job with success/failure and retry scheduling.
      - Emit AuditLog entries for webhook_sent / webhook_failed.
    """

    def __init__(
        self,
        poll_interval_seconds: int = 5,
        http_timeout_seconds: int = 15,
        max_concurrent_requests: int = 10,
    ) -> None:
        self.poll_interval_seconds = poll_interval_seconds
        self.http_timeout_seconds = http_timeout_seconds
        self._stopping = False
        self._semaphore = asyncio.Semaphore(max_concurrent_requests)

    async def start(self) -> None:
        """
        Start the worker polling loop.

        This is intended to be called from a dedicated worker entrypoint, e.g.:

            python -m app.workers.webhook_worker
        """
        logger.info("WebhookWorker starting with poll interval %s seconds", self.poll_interval_seconds)
        while not self._stopping:
            try:
                processed = await self._process_next_batch()
                # If no jobs processed, sleep for the full interval;
                # otherwise, yield control but poll again quickly.
                if processed == 0:
                    await asyncio.sleep(self.poll_interval_seconds)
                else:
                    await asyncio.sleep(0)
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Unhandled exception in webhook worker loop: %s", exc)
                await asyncio.sleep(self.poll_interval_seconds)

        logger.info("WebhookWorker stopped")

    def stop(self) -> None:
        """Signal the worker loop to stop after the current iteration."""
        self._stopping = True

    async def _process_next_batch(self, batch_size: int = 10) -> int:
        """
        Fetch and process a batch of webhook_delivery jobs.

        Returns:
            Number of jobs successfully claimed for processing (regardless of outcome).
        """
        async with async_session_factory() as session:
            jobs = await self._claim_jobs(session, batch_size=batch_size)
            if not jobs:
                return 0

            tasks = [self._handle_job(job, session) for job in jobs]
            # We want to process concurrently but ensure DB changes are saved.
            await asyncio.gather(*tasks, return_exceptions=False)

            try:
                await session.commit()
            except SQLAlchemyError:
                logger.exception("Failed to commit DB session after processing webhook jobs")
                await session.rollback()

            return len(jobs)

    async def _claim_jobs(self, session: AsyncSession, batch_size: int) -> list[Job]:
        """
        Atomically claim up to `batch_size` webhook_delivery jobs that are queued and due.

        Jobs are selected with FOR UPDATE SKIP LOCKED to allow multiple workers.
        """
        try:
            stmt = (
                select(Job)
                .where(
                    Job.type == "webhook_delivery",
                    Job.status == "queued",
                    Job.scheduled_at <= settings.current_time(),
                )
                .order_by(Job.scheduled_at)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
            result = await session.execute(stmt)
            jobs: list[Job] = list(result.scalars().all())

            for job in jobs:
                job.status = "processing"
                job.attempts += 1

            return jobs
        except SQLAlchemyError:
            logger.exception("Error while claiming webhook_delivery jobs")
            await session.rollback()
            return []

    async def _handle_job(self, job: Job, session: AsyncSession) -> None:
        """
        Process a single webhook_delivery job.

        Expected job.payload structure:
            {
                "webhook_delivery_id": "<uuid>"
            }
        """
        async with self._semaphore:
            logger.info("Processing webhook_delivery job %s", job.id)

            delivery_id = job.payload.get("webhook_delivery_id") if isinstance(job.payload, dict) else None
            if not delivery_id:
                logger.error("Job %s payload missing webhook_delivery_id", job.id)
                await self._mark_job_failed(
                    session=session,
                    job=job,
                    error_message="Invalid payload: missing webhook_delivery_id",
                    permanent=True,
                )
                return

            delivery = await self._get_delivery(session, delivery_id)
            if not delivery:
                logger.error("WebhookDelivery %s not found for job %s", delivery_id, job.id)
                await self._mark_job_failed(
                    session=session,
                    job=job,
                    error_message=f"WebhookDelivery {delivery_id} not found",
                    permanent=True,
                )
                return

            webhook_config = await self._get_webhook_config(session, delivery.webhook_config_id)
            if not webhook_config:
                logger.error(
                    "WebhookConfig %s not found for delivery %s",
                    delivery.webhook_config_id,
                    delivery.id,
                )
                await self._update_delivery_failure(
                    session=session,
                    delivery=delivery,
                    status_code=None,
                    error_message="Webhook config not found",
                    final=True,
                )
                await self._mark_job_failed(
                    session=session,
                    job=job,
                    error_message="Webhook config not found",
                    permanent=True,
                )
                return

            if not webhook_config.enabled:
                logger.warning(
                    "WebhookConfig %s is disabled; marking delivery %s as failed",
                    webhook_config.id,
                    delivery.id,
                )
                await self._update_delivery_failure(
                    session=session,
                    delivery=delivery,
                    status_code=None,
                    error_message="Webhook disabled",
                    final=True,
                )
                await self._mark_job_failed(
                    session=session,
                    job=job,
                    error_message="Webhook disabled",
                    permanent=True,
                )
                return

            # Perform HTTP request
            try:
                status_code, error_message = await self._send_webhook_request(
                    webhook_config=webhook_config,
                    delivery=delivery,
                )
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Exception when sending webhook delivery %s: %s", delivery.id, exc)
                status_code = None
                error_message = f"Exception: {exc}"

            # Decide success/failure and retry
            success = status_code is not None and 200 <= status_code < 300
            max_attempts = self._get_max_attempts(webhook_config)
            final_attempt = delivery.attempt_count + 1 >= max_attempts

            if success:
                await self._update_delivery_success(session, delivery, status_code)
                await self._mark_job_succeeded(session, job)
            else:
                await self._update_delivery_failure(
                    session=session,
                    delivery=delivery,
                    status_code=status_code,
                    error_message=error_message,
                    final=final_attempt,
                )

                if final_attempt:
                    await self._mark_job_failed(
                        session=session,
                        job=job,
                        error_message=error_message or "Webhook failed",
                        permanent=True,
                    )
                else:
                    # Schedule retry with backoff
                    delay = self._get_retry_delay_seconds(webhook_config, attempts=delivery.attempt_count + 1)
                    job.status = "queued"
                    job.scheduled_at = settings.current_time() + delay

    async def _get_delivery(self, session: AsyncSession, delivery_id: str) -> Optional[WebhookDelivery]:
        """Load a WebhookDelivery by ID."""
        stmt = select(WebhookDelivery).where(WebhookDelivery.id == delivery_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_webhook_config(self, session: AsyncSession, config_id: str) -> Optional[WebhookConfig]:
        """Load a WebhookConfig by ID."""
        stmt = select(WebhookConfig).where(WebhookConfig.id == config_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _send_webhook_request(
        self,
        webhook_config: WebhookConfig,
        delivery: WebhookDelivery,
    ) -> tuple[Optional[int], Optional[str]]:
        """
        Send the webhook HTTP request with proper headers and signature.

        Returns:
            (status_code, error_message)
        """
        payload_data: Dict[str, Any] = delivery.payload or {}
        body_bytes = json.dumps(payload_data, separators=(",", ":"), default=str).encode("utf-8")

        timestamp = str(int(settings.current_time().timestamp()))
        signature = self._compute_signature(secret=webhook_config.secret, timestamp=timestamp, body=body_bytes)

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "DocFoundry-Webhook/1.0",
            "X-DocFoundry-Signature": f"t={timestamp},v1={signature}",
            "X-DocFoundry-Event": delivery.event_type,
            "X-DocFoundry-Delivery-Id": str(delivery.id),
        }

        timeout = httpx.Timeout(self.http_timeout_seconds, connect=self.http_timeout_seconds)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    webhook_config.target_url,
                    content=body_bytes,
                    headers=headers,
                    follow_redirects=True,
                )
            status_code = response.status_code
            error_message = None if 200 <= status_code < 300 else f"Non-2xx response: {status_code}"
            return status_code, error_message
        except httpx.RequestError as exc:
            logger.warning(
                "HTTP error sending webhook delivery %s to %s: %s",
                delivery.id,
                webhook_config.target_url,
                exc,
            )
            return None, f"Request error: {exc}"

    def _compute_signature(self, secret: str, timestamp: str, body: bytes) -> str:
        """
        Compute HMAC-SHA256 signature.

        Signed payload is: "{timestamp}.{body}"

        Header format:
            X-DocFoundry-Signature: t=<timestamp>,v1=<hex>
        """
        msg = f"{timestamp}.".encode("utf-8") + body
        digest = hmac.new(secret.encode("utf-8"), msg=msg, digestmod=sha256).hexdigest()
        return digest

    def _get_max_attempts(self, webhook_config: WebhookConfig) -> int:
        """
        Determine max attempts from retry_policy, falling back to job.max_attempts or default.

        Expected retry_policy example:
            {
              "max_attempts": 5,
              "initial_delay_seconds": 30,
              "backoff_factor": 2.0
            }
        """
        policy = webhook_config.retry_policy or {}
        try:
            max_attempts = int(policy.get("max_attempts", 5))
            return max(1, max_attempts)
        except (TypeError, ValueError):
            return 5

    def _get_retry_delay_seconds(self, webhook_config: WebhookConfig, attempts: int) -> Any:
        """
        Compute delay (as timedelta) between attempts based on retry_policy.

        The `attempts` param is 1-based (1 for first retry).
        """
        from datetime import timedelta

        policy = webhook_config.retry_policy or {}
        try:
            base_delay = float(policy.get("initial_delay_seconds", 30.0))
        except (TypeError, ValueError):
            base_delay = 30.0

        try:
            backoff = float(policy.get("backoff_factor", 2.0))
        except (TypeError, ValueError):
            backoff = 2.0

        # Exponential backoff: base_delay * backoff^(attempts-1)
        delay_seconds = base_delay * (backoff ** max(0, attempts - 1))
        delay_seconds = min(delay_seconds, float(policy.get("max_delay_seconds", 3600.0)))
        return timedelta(seconds=int(delay_seconds))

    async def _update_delivery_success(
        self,
        session: AsyncSession,
        delivery: WebhookDelivery,
        status_code: int,
    ) -> None:
        """Mark a WebhookDelivery as succeeded and create an audit log."""
        delivery.status_code = status_code
        delivery.delivery_status = "succeeded"
        delivery.attempt_count += 1
        delivery.last_error = None

        session.add(delivery)

        audit = AuditLog(
            workspace_id=delivery.workspace_id,
            user_id=None,
            actor_type="system",
            event_type="webhook_sent",
            description=f"Webhook delivery {delivery.id} succeeded with status {status_code}",
            metadata={
                "webhook_delivery_id": str(delivery.id),
                "webhook_config_id": str(delivery.webhook_config_id),
                "status_code": status_code,
                "attempt_count": delivery.attempt_count,
            },
        )
        session.add(audit)

    async def _update_delivery_failure(
        self,
        session: AsyncSession,
        delivery: WebhookDelivery,
        status_code: Optional[int],
        error_message: Optional[str],
        final: bool,
    ) -> None:
        """Update a WebhookDelivery as failed (temporary or final) and record audit log."""
        delivery.status_code = status_code
        delivery.delivery_status = "failed" if final else "pending"
        delivery.attempt_count += 1
        delivery.last_error = error_message

        session.add(delivery)

        audit = AuditLog(
            workspace_id=delivery.workspace_id,
            user_id=None,
            actor_type="system",
            event_type="webhook_failed",
            description=f"Webhook delivery {delivery.id} failed",
            metadata={
                "webhook_delivery_id": str(delivery.id),
                "webhook_config_id": str(delivery.webhook_config_id),
                "status_code": status_code,
                "error": error_message,
                "attempt_count": delivery.attempt_count,
                "final": final,
            },
        )
        session.add(audit)

    async def _mark_job_succeeded(self, session: AsyncSession, job: Job) -> None:
        """Mark Job as succeeded."""
        job.status = "succeeded"
        job.last_error = None
        stmt = (
            update(Job)
            .where(Job.id == job.id)
            .values(status="succeeded", last_error=None, attempts=job.attempts, updated_at=settings.current_time())
        )
        await session.execute(stmt)

    async def _mark_job_failed(
        self,
        session: AsyncSession,
        job: Job,
        error_message: str,
        permanent: bool,
    ) -> None:
        """
        Mark Job as failed.

        If not permanent and attempts < max_attempts, caller is responsible for scheduling retry.
        """
        job.last_error = error_message
        if permanent or job.attempts >= job.max_attempts:
            job.status = "failed"
        else:
            job.status = "queued"

        stmt = (
            update(Job)
            .where(Job.id == job.id)
            .values(
                status=job.status,
                last_error=error_message,
                attempts=job.attempts,
                scheduled_at=job.scheduled_at,
                updated_at=settings.current_time(),
            )
        )
        await session.execute(stmt)


async def main() -> None:
    """
    Entry point for running the webhook worker as a standalone process.

    Example:
        python -m app.workers.webhook_worker
    """
    logging.basicConfig(level=logging.INFO)
    worker = WebhookWorker(
        poll_interval_seconds=settings.worker_poll_interval_seconds,
        http_timeout_seconds=settings.webhook_http_timeout_seconds,
        max_concurrent_requests=settings.webhook_max_concurrent_requests,
    )

    loop = asyncio.get_event_loop()

    stop_event = asyncio.Event()

    def _handle_stop_signal() -> None:
        logger.info("Received stop signal for WebhookWorker")
        worker.stop()
        stop_event.set()

    for sig in ("SIGINT", "SIGTERM"):
        try:
            loop.add_signal_handler(getattr(__import__("signal"), sig), _handle_stop_signal)
        except (NotImplementedError, AttributeError):
            # Signal handlers may not be available on some platforms (e.g., Windows)
            pass

    await asyncio.gather(worker.start(), stop_event.wait())


if __name__ == "__main__":
    asyncio.run(main())