import uuid
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from sqlalchemy import (
    UUID,
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    String,
    Text,
    TypeDecorator,
)
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base
from .workspace import Workspace


class ApiKeyStatusEnum(str, Enum):  # type: ignore[misc]
    """Enumeration of possible API key statuses."""

    ACTIVE = "active"
    REVOKED = "revoked"


class ApiKeyStatusType(TypeDecorator):
    """Type decorator to ensure status values are always lowercase strings."""
    
    impl = PG_ENUM
    cache_ok = True
    
    def __init__(self):
        super().__init__("active", "revoked", name="api_key_status_enum", create_type=False)
    
    def process_bind_param(self, value, dialect):
        """Convert value to lowercase string before binding to database."""
        if value is None:
            return None
        if isinstance(value, ApiKeyStatusEnum):
            return value.value
        return str(value).lower()
    
    def process_result_value(self, value, dialect):
        """Return value as-is from database."""
        return value


class ApiKey(Base):
    """API key for programmatic access to the public `/api/v1` endpoints.

    The actual API key value is never stored in plaintext; instead, a secure hash
    of the full key is stored in `key_hash`. Only a short, non-secret `prefix`
    is exposed in logs and UI to help identify which key was used.

    All API keys are scoped to a workspace via `workspace_id` to enforce
    multi-tenant isolation.
    """

    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(length=255),
        nullable=False,
        doc="Human-readable label for the API key.",
    )

    key_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Secure hash of the full API key value (never store plaintext).",
    )

    prefix: Mapped[str] = mapped_column(
        String(length=16),
        nullable=False,
        doc="Short non-secret identifier shown in UI/logs.",
    )

    scopes: Mapped[List[str]] = mapped_column(
        JSONB,
        nullable=False,
        doc="Array of scope strings (e.g. ['documents:read','documents:write']).",
    )

    status: Mapped[str] = mapped_column(
        ApiKeyStatusType(),
        nullable=False,
        default="active",
    )

    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Optional expiration timestamp; null means no automatic expiry.",
    )

    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Last time this key was successfully used for an API call.",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship(
        Workspace,
        back_populates="api_keys",
        lazy="joined",
    )

    __table_args__ = (
        # Ensure prefix is not empty and reasonably sized (already enforced by length, but
        # this adds a DB-level guarantee against blank strings).
        CheckConstraint("char_length(prefix) > 0", name="ck_api_keys_prefix_non_empty"),
    )

    def is_active(self, at: Optional[datetime] = None) -> bool:
        """Return True if the API key is currently active and not expired.

        Args:
            at: Optional point-in-time to evaluate against; defaults to now (UTC).

        Returns:
            True if status is active and (if set) expires_at is in the future.
        """
        if self.status != "active":
            return False

        if at is None:
            at = datetime.utcnow()

        if self.expires_at is not None and self.expires_at <= at:
            return False

        return True

    def has_scope(self, scope: str) -> bool:
        """Check whether this API key grants a particular scope.

        Args:
            scope: Scope string to verify (e.g. 'documents:read').

        Returns:
            True if the key's scopes array contains the requested scope or a wildcard.
        """
        if not isinstance(self.scopes, list):
            return False

        if "*" in self.scopes or "all" in self.scopes:
            return True

        return scope in self.scopes

    def to_safe_dict(self) -> dict[str, Any]:
        """Serialize the API key without exposing sensitive fields.

        This method omits `key_hash` and only includes the publicly safe `prefix`.

        Returns:
            A dictionary representation suitable for API responses.
        """
        return {
            "id": str(self.id),
            "workspace_id": str(self.workspace_id),
            "name": self.name,
            "prefix": self.prefix,
            "scopes": self.scopes,
            "status": self.status,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "created_at": self.created_at.isoformat(),
        }


# Additional index to speed up lookups by prefix for logging/identification.
Index("ix_api_keys_prefix", ApiKey.prefix)