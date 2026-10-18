"""Structured logging service with correlation IDs and error taxonomy."""

import contextvars
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

import structlog

# Context variable for correlation ID
correlation_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "correlation_id", default=None
)

# Context variable for request metadata
request_metadata_var: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar(
    "request_metadata", default=None
)


class ErrorCategory(str, Enum):
    """Error categories for taxonomy."""

    USER_ERROR = "user_error"  # Invalid input, validation failures
    SYSTEM_ERROR = "system_error"  # Internal errors, bugs
    OCR_ERROR = "ocr_error"  # OCR processing failures
    EXTERNAL_ERROR = "external_error"  # Third-party service failures
    AUTH_ERROR = "auth_error"  # Authentication/authorization failures
    QUOTA_ERROR = "quota_error"  # Quota/limit exceeded
    NETWORK_ERROR = "network_error"  # Network timeouts, connection errors


class StructuredLogger:
    """Structured logger with correlation IDs and error taxonomy."""

    def __init__(self, name: str):
        """Initialize structured logger.

        Args:
            name: Logger name
        """
        self.logger = structlog.get_logger(name)

    def _get_context(self) -> Dict[str, Any]:
        """Get current context (correlation ID, metadata)."""
        context: Dict[str, Any] = {}
        correlation_id = correlation_id_var.get()
        if correlation_id:
            context["correlation_id"] = correlation_id

        metadata = request_metadata_var.get()
        if metadata:
            context.update(metadata)

        return context

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message with context."""
        self.logger.info(message, **self._get_context(), **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message with context."""
        self.logger.warning(message, **self._get_context(), **kwargs)

    def error(
        self,
        message: str,
        error_category: Optional[ErrorCategory] = None,
        exc_info: Optional[Exception] = None,
        **kwargs: Any,
    ) -> None:
        """Log error message with context and error category."""
        error_data: Dict[str, Any] = {}
        if error_category:
            error_data["error_category"] = error_category.value
        if exc_info:
            error_data["exception_type"] = type(exc_info).__name__
            error_data["exception_message"] = str(exc_info)

        self.logger.error(
            message,
            **self._get_context(),
            **error_data,
            **kwargs,
            exc_info=exc_info,
        )

    def exception(self, message: str, **kwargs: Any) -> None:
        """Log exception message with context and exception info.
        
        This is a convenience method that logs at ERROR level with exc_info=True.
        It's equivalent to logger.error(message, exc_info=True).
        """
        import sys
        self.logger.error(
            message,
            **self._get_context(),
            **kwargs,
            exc_info=sys.exc_info(),
        )

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message with context."""
        self.logger.debug(message, **self._get_context(), **kwargs)


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name

    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(name)


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """Set correlation ID for current context.

    Args:
        correlation_id: Optional correlation ID (generates if None)

    Returns:
        Correlation ID string
    """
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    correlation_id_var.set(correlation_id)
    return correlation_id


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID.

    Returns:
        Correlation ID or None
    """
    return correlation_id_var.get()


def set_request_metadata(metadata: Dict[str, Any]) -> None:
    """Set request metadata for current context.

    Args:
        metadata: Metadata dictionary
    """
    request_metadata_var.set(metadata)


def get_request_metadata() -> Optional[Dict[str, Any]]:
    """Get current request metadata.

    Returns:
        Metadata dictionary or None
    """
    return request_metadata_var.get()


def configure_logging(log_level: str = "INFO", json_output: bool = True) -> None:
    """Configure structured logging.

    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_output: Whether to output JSON format
    """
    # Configure structlog
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )


def log_job_event(
    logger: StructuredLogger,
    event_type: str,
    job_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    template_id: Optional[str] = None,
    document_id: Optional[str] = None,
    duration_ms: Optional[float] = None,
    result_status: Optional[str] = None,
    **kwargs: Any,
) -> None:
    """Log a job processing event with standard fields.

    Args:
        logger: Structured logger instance
        event_type: Event type (e.g., "job_started", "job_completed")
        job_id: Job ID
        workspace_id: Workspace ID
        template_id: Template ID
        document_id: Document ID
        duration_ms: Processing duration in milliseconds
        result_status: Result status (succeeded, failed, etc.)
        **kwargs: Additional fields
    """
    log_data: Dict[str, Any] = {
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if job_id:
        log_data["job_id"] = job_id
    if workspace_id:
        log_data["workspace_id"] = workspace_id
    if template_id:
        log_data["template_id"] = template_id
    if document_id:
        log_data["document_id"] = document_id
    if duration_ms is not None:
        log_data["duration_ms"] = duration_ms
    if result_status:
        log_data["result_status"] = result_status

    log_data.update(kwargs)

    logger.info(f"Job event: {event_type}", **log_data)

