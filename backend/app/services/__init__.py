"""
Service layer package initialization.

This module exposes common service interfaces and factory functions
for use throughout the application. Concrete service implementations
should live in sibling modules (e.g. `auth_service.py`, `project_service.py`).

The service layer is responsible for:
- Orchestrating business logic across multiple models.
- Enforcing cross-cutting concerns (multi-tenancy, permissions, audit logging).
- Providing a stable API for routers and background workers.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AuditLoggerProtocol(Protocol):
    """Protocol for the audit logging service."""

    async def log_event(
        self,
        *,
        workspace_id: str | None,
        user_id: str | None,
        actor_type: str,
        event_type: str,
        description: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Persist an audit log entry."""


@runtime_checkable
class NotificationServiceProtocol(Protocol):
    """Protocol for the notification service."""

    async def send_event_notification(
        self,
        *,
        user_id: str,
        workspace_id: str | None,
        channel: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Send a notification for a given event."""
        ...

    async def mark_as_read(self, *, notification_id: str, user_id: str) -> None:
        """Mark a notification as read for the given user."""
        ...


__all__ = [
    "AuditLoggerProtocol",
    "NotificationServiceProtocol",
]