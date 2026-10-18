"""
Worker package initializer.

This module exposes common worker utilities and a simple task runner
interface used by separate worker entrypoints (e.g. document extraction
worker, webhook delivery worker).

Workers are expected to:

- Use the shared async SQLAlchemy session from `app.database`
- Poll the `jobs` table for work
- Cooperatively cancel via an asyncio.Event
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Protocol

logger = logging.getLogger(__name__)


class WorkerTask(Protocol):
    """Protocol representing an async worker task function.

    Implementations are expected to:

    - Run until `stop_event.is_set()` is True
    - Handle their own exception logging and backoff
    - Not raise unhandled exceptions out of the function
    """

    async def __call__(self, stop_event: asyncio.Event) -> None:  # pragma: no cover - protocol
        ...


async def run_worker(
    task: WorkerTask,
    *,
    shutdown_timeout: float = 30.0,
) -> None:
    """Run a single worker task with cooperative shutdown handling.

    This helper is intended to be used by worker entrypoint scripts, e.g.:

        from app.workers import run_worker
        from app.workers.document_extraction import document_extraction_loop

        if __name__ == "__main__":
            asyncio.run(run_worker(document_extraction_loop))

    Args:
        task: An async callable that accepts an `asyncio.Event` used to signal shutdown.
        shutdown_timeout: Maximum time in seconds to wait for graceful shutdown
            after cancellation is requested.
    """
    stop_event = asyncio.Event()

    loop = asyncio.get_event_loop()

    def _handle_signal() -> None:
        if not stop_event.is_set():
            logger.info("Shutdown signal received; requesting worker stop...")
            stop_event.set()

    # Best-effort signal handling; on some platforms (e.g. Windows) not all
    # signals may be available. We avoid failing hard if registration fails.
    for sig_name in ("SIGINT", "SIGTERM"):
        try:
            import signal

            sig = getattr(signal, sig_name)
            loop.add_signal_handler(sig, _handle_signal)
        except (ImportError, AttributeError, RuntimeError, ValueError):
            # RuntimeError can occur if loop is not running or on incompatible platforms
            logger.debug("Signal %s not available or could not be registered", sig_name)

    logger.info("Starting worker task %s", getattr(task, "__name__", repr(task)))

    worker_task = asyncio.create_task(task(stop_event))

    try:
        await worker_task
    except asyncio.CancelledError:
        logger.info("Worker task was cancelled; beginning shutdown...")
    except Exception:  # pragma: no cover - defensive
        logger.exception("Unhandled exception in worker task; shutting down...")
        stop_event.set()

    if not worker_task.done():
        logger.info("Waiting up to %.1f seconds for worker to shut down gracefully", shutdown_timeout)
        try:
            await asyncio.wait_for(worker_task, timeout=shutdown_timeout)
        except asyncio.TimeoutError:
            logger.warning("Worker did not shut down within timeout; cancelling...")
            worker_task.cancel()
        except Exception:  # pragma: no cover - defensive
            logger.exception("Error while waiting for worker shutdown")

    logger.info("Worker task %s exited", getattr(task, "__name__", repr(task)))


__all__ = ["WorkerTask", "run_worker"]