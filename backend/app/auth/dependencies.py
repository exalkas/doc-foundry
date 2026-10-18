import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import bcrypt
from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.apikey import ApiKey
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspacemember import WorkspaceMember

logger = logging.getLogger(__name__)

# Suppress passlib's bcrypt version warning and all passlib warnings
# This warning occurs due to a compatibility issue between passlib 1.7.4 and bcrypt 4.x
# We suppress warnings from passlib handlers to prevent noise in logs

# Create a filter to suppress passlib warnings
class PasslibWarningFilter(logging.Filter):
    def filter(self, record):
        # Suppress warnings from passlib, especially bcrypt version warnings
        if record.name.startswith("passlib"):
            if record.levelno == logging.WARNING:
                # Suppress all passlib warnings
                return False
        return True

# Apply filter to root logger to catch all passlib warnings
passlib_filter = PasslibWarningFilter()
logging.getLogger().addFilter(passlib_filter)

# Also set log levels explicitly
passlib_bcrypt_logger = logging.getLogger("passlib.handlers.bcrypt")
passlib_bcrypt_logger.setLevel(logging.ERROR)  # Only show errors, suppress warnings
passlib_logger = logging.getLogger("passlib")
passlib_logger.setLevel(logging.ERROR)

# Configure CryptContext with bcrypt
# Note: We handle bcrypt's 72-byte limit by truncating passwords before hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)

# Pre-initialize bcrypt backend to avoid lazy-loading issues
# This triggers the backend initialization early and handles any errors silently
_use_passlib = True
try:
    # Try to initialize with a safe, short password
    _test_init_password = "init_test_123"
    test_hash = pwd_context.hash(_test_init_password)
    # Also test verification to catch AttributeError issues
    try:
        pwd_context.verify(_test_init_password, test_hash)
    except (AttributeError, Exception):
        # If verification fails with AttributeError, passlib has compatibility issues
        _use_passlib = False
except (ValueError, AttributeError, Exception) as e:
    # If initialization fails (e.g., due to wrap bug detection issue or AttributeError),
    # we'll use bcrypt directly as fallback
    error_str = str(e)
    if "password cannot be longer than 72 bytes" in error_str or "AttributeError" in str(type(e).__name__):
        # Passlib has compatibility issues with bcrypt 4.x
        # Use bcrypt directly instead
        _use_passlib = False
    # Silently handle - no logging needed as this is expected behavior


class TokenType:
    """Constants for JWT token types."""

    SESSION = "session"
    IMPERSONATION = "impersonation"
    API_KEY = "api_key"


def _truncate_password_for_bcrypt(password: str) -> str:
    """
    Truncate password to 72 bytes for bcrypt compatibility.
    
    Bcrypt has a hard limit of 72 bytes. This function ensures passwords
    are truncated to this limit before hashing/verification.
    
    If truncation occurs, it may cut in the middle of a multi-byte UTF-8
    character, but this is acceptable for password hashing purposes.
    """
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        # Truncate to exactly 72 bytes
        truncated_bytes = password_bytes[:72]
        # Decode with error handling to avoid issues with incomplete UTF-8 sequences
        return truncated_bytes.decode('utf-8', errors='replace')
    return password


def verify_password(plain_password: str, password_hash: str) -> bool:
    """
    Verify a plaintext password against a stored hash.

    Raises no exceptions; returns False if verification fails.
    """
    # Truncate password to 72 bytes for bcrypt compatibility
    truncated_password = _truncate_password_for_bcrypt(plain_password)
    password_bytes = truncated_password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    
    # If passlib initialization failed, use bcrypt directly
    if not _use_passlib:
        try:
            hash_bytes = password_hash.encode('utf-8')
            return bcrypt.checkpw(password_bytes, hash_bytes)
        except Exception:
            return False
    
    # Try passlib first
    try:
        truncated_password_str = password_bytes.decode('utf-8', errors='replace')
        return pwd_context.verify(truncated_password_str, password_hash)
    except (ValueError, AttributeError, Exception) as e:
        # If passlib fails due to initialization issues, try bcrypt directly
        # Silently fall back - no logging to avoid noise
        try:
            hash_bytes = password_hash.encode('utf-8')
            return bcrypt.checkpw(password_bytes, hash_bytes)
        except Exception:
            return False


def get_password_hash(password: str) -> str:
    """
    Hash a plaintext password for storage.
    
    Passwords are truncated to 72 bytes to comply with bcrypt's limitation.
    
    Note: This function handles a known issue with passlib 1.7.4 and bcrypt 4.x
    where passlib's internal wrap bug detection may fail during backend initialization.
    If passlib fails, we fall back to using bcrypt directly.
    """
    # Truncate password to 72 bytes for bcrypt compatibility
    truncated_password = _truncate_password_for_bcrypt(password)
    
    # Ensure the password is definitely 72 bytes or less
    password_bytes = truncated_password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    
    # If passlib initialization failed, use bcrypt directly
    if not _use_passlib:
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')
    
    # Try passlib first
    try:
        truncated_password = password_bytes.decode('utf-8', errors='replace')
        return pwd_context.hash(truncated_password)
    except ValueError as e:
        error_msg = str(e)
        if "password cannot be longer than 72 bytes" in error_msg:
            # Fall back to bcrypt directly
            salt = bcrypt.gensalt()
            hashed = bcrypt.hashpw(password_bytes, salt)
            return hashed.decode('utf-8')
        # Re-raise other ValueError exceptions
        raise


def create_access_token(
    data: Dict[str, Any],
    expires_delta_seconds: Optional[int] = None,
    token_type: str = TokenType.SESSION,
) -> str:
    """
    Create a signed JWT access token.

    :param data: Claims to embed in the token.
    :param expires_delta_seconds: Lifetime in seconds; uses default from settings if None.
    :param token_type: Logical token type (session, impersonation, etc.).
    """
    to_encode = data.copy()
    now = datetime.now(tz=timezone.utc)

    if expires_delta_seconds is None:
        expires_delta_seconds = settings.auth_access_token_expire_seconds

    expire = now + settings.auth_access_token_timedelta(expires_delta_seconds)
    to_encode.update(
        {
            "exp": expire,
            "iat": now,
            "type": token_type,
        }
    )
    encoded_jwt = jwt.encode(
        to_encode,
        settings.auth_jwt_secret_key,
        algorithm=settings.auth_jwt_algorithm,
    )
    return encoded_jwt


def _decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT, raising HTTPException on failure.
    """
    try:
        payload = jwt.decode(
            token,
            settings.auth_jwt_secret_key,
            algorithms=[settings.auth_jwt_algorithm],
            options={"verify_aud": False},
        )
        return payload
    except JWTError as exc:
        logger.warning("Failed to decode JWT: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        ) from exc


async def _get_user_by_id(session: AsyncSession, user_id: Any) -> Optional[User]:
    """
    Fetch a user by ID from the database.
    """
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def _get_workspace_by_id(
    session: AsyncSession, workspace_id: Any
) -> Optional[Workspace]:
    """
    Fetch a workspace by ID from the database.
    """
    result = await session.execute(select(Workspace).where(Workspace.id == workspace_id))
    return result.scalar_one_or_none()


async def _get_memberships_for_user(
    session: AsyncSession, user_id: Any
) -> List[WorkspaceMember]:
    """
    Fetch all workspace memberships for a given user.
    """
    result = await session.execute(
        select(WorkspaceMember).where(WorkspaceMember.user_id == user_id)
    )
    return list(result.scalars().all())


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    access_token_cookie: Optional[str] = Cookie(
        None, alias=settings.auth_cookie_name, include_in_schema=False
    ),
    authorization: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> User:
    """
    Resolve the currently authenticated user using either:

    - HTTP-only JWT cookie (primary for web sessions).
    - `Authorization: Bearer <token>` header (fallback, e.g., for admin tools).

    Raises 401 if authentication fails.
    """
    token: Optional[str] = None

    # Prefer cookie-based session
    if access_token_cookie:
        token = access_token_cookie
    # Fallback to Authorization header for non-cookie clients (e.g. Postman)
    elif authorization and authorization.scheme.lower() == "bearer":
        token = authorization.credentials

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    payload = _decode_token(token)

    if payload.get("type") not in {TokenType.SESSION, TokenType.IMPERSONATION}:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type for user session",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token subject missing",
        )

    user = await _get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    # Attach raw token/claims to request state if needed by downstream handlers
    request.state.token_payload = payload
    request.state.token = token
    # Set user_id for rate limiting
    request.state.user_id = str(user.id)

    return user


async def get_current_workspace(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Workspace:
    """
    Resolve the current workspace for the authenticated user.

    Uses `workspace_id` claim from the JWT if present and valid for this user.
    Falls back to:
    - the workspace specified in `X-Workspace-Id` header (if the user is a member), or
    - the first active workspace membership.

    Raises 403 if the user has no accessible workspace.
    """
    # Try JWT workspace_id claim first
    token_workspace_id = getattr(request.state, "token_payload", {}).get("workspace_id")

    candidate_workspace_ids: List[Any] = []
    if token_workspace_id:
        candidate_workspace_ids.append(token_workspace_id)

    # Optional override via header for explicit selection
    header_workspace_id = request.headers.get("X-Workspace-Id")
    if header_workspace_id and header_workspace_id not in candidate_workspace_ids:
        candidate_workspace_ids.append(header_workspace_id)

    memberships = await _get_memberships_for_user(db, current_user.id)
    if not memberships:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a member of any workspace",
        )

    # Map workspace_id -> membership for quick lookup
    membership_by_ws: Dict[Any, WorkspaceMember] = {
        m.workspace_id: m for m in memberships
    }

    selected_workspace_id: Optional[Any] = None

    # Respect explicit workspace hints if they correspond to a membership
    for ws_id in candidate_workspace_ids:
        if ws_id in membership_by_ws:
            selected_workspace_id = ws_id
            break

    # Fallback: choose first active membership workspace
    if not selected_workspace_id:
        selected_workspace_id = memberships[0].workspace_id

    workspace = await _get_workspace_by_id(db, selected_workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    if workspace.status == "suspended":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workspace is suspended",
        )

    request.state.workspace = workspace
    request.state.workspace_member = membership_by_ws.get(selected_workspace_id)

    return workspace


async def get_current_workspace_member(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
) -> WorkspaceMember:
    """
    Get the WorkspaceMember record for the current user in the current workspace.

    Raises 403 if the user is not a member of the workspace.
    """
    result = await db.execute(
        select(WorkspaceMember).where(
            and_(
                WorkspaceMember.user_id == current_user.id,
                WorkspaceMember.workspace_id == current_workspace.id,
                WorkspaceMember.status == "active",
            )
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not an active member of this workspace",
        )
    return member


async def get_current_admin_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_token_cookie: Optional[str] = Cookie(
        None, alias="admin_session", include_in_schema=False
    ),
    authorization: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> User:
    """
    Resolve the currently authenticated admin user using either:
    - HTTP-only admin JWT cookie (primary for admin web sessions).
    - `Authorization: Bearer <token>` header (fallback).

    This is separate from regular user auth to avoid workspace context conflicts.
    Admin users don't need workspace context.
    """
    token: Optional[str] = None

    # Prefer admin cookie
    if admin_token_cookie:
        token = admin_token_cookie
    # Fallback to Authorization header
    elif authorization and authorization.scheme.lower() == "bearer":
        token = authorization.credentials

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    payload = _decode_token(token)

    # Check if it's an admin session (has is_admin flag or no workspace_id)
    is_admin_session = payload.get("is_admin") or payload.get("workspace_id") is None

    if not is_admin_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin session required",
        )

    if payload.get("type") not in {TokenType.SESSION, TokenType.IMPERSONATION}:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type for admin session",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token subject missing",
        )

    user = await _get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    from app.models.user import GlobalUserRole
    if user.global_role != GlobalUserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )

    # Attach raw token/claims to request state
    request.state.token_payload = payload
    request.state.token = token
    request.state.user_id = str(user.id)

    return user


def require_global_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency that restricts access to global platform administrators.
    
    For admin endpoints, prefer using get_current_admin_user instead
    to avoid workspace context conflicts.
    """
    from app.models.user import GlobalUserRole
    if current_user.global_role != GlobalUserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


def require_workspace_role(*allowed_roles: str):
    """
    Factory to create a dependency that checks the user's role within the workspace.

    Usage:
        router.get("/")(Depends(require_workspace_role("owner", "member")))
    """

    async def _checker(
        member: WorkspaceMember = Depends(get_current_workspace_member),
    ) -> WorkspaceMember:
        if member.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient workspace role",
            )
        return member

    return _checker


# === API KEY AUTH (for /api/v1/* public programmatic endpoints) ===


async def get_current_api_key(
    request: Request,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> ApiKey:
    """
    Authenticate programmatic access using an API key provided as:

        Authorization: Bearer <API_KEY>

    The API key is stored hashed in the database; this function:
    - Parses the header.
    - Separates prefix (e.g. 'dk_live_abc123...').
    - Finds the ApiKey row by prefix.
    - Verifies the full key against the stored hash.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    try:
        scheme, credentials = authorization.split(" ", 1)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format",
        )

    if scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization scheme",
        )

    raw_key = credentials.strip()
    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empty API key",
        )

    # We assume keys are formatted like "<prefix>.<secret>" where prefix is stable
    if "." not in raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed API key",
        )

    prefix, _secret = raw_key.split(".", 1)

    result = await db.execute(select(ApiKey).where(ApiKey.prefix == prefix))
    api_key: Optional[ApiKey] = result.scalar_one_or_none()

    if api_key is None or api_key.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    if api_key.expires_at and api_key.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key expired",
        )

    # Verify raw key against stored hash
    if not verify_password(raw_key, api_key.key_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Update last_used_at asynchronously; don't block the request on commit
    api_key.last_used_at = datetime.now(timezone.utc)
    try:
        await db.flush()
    except Exception:
        logger.exception("Failed to update api_key.last_used_at")

    # Set API key ID in request state for rate limiting
    if hasattr(request, 'state'):
        request.state.api_key_id = str(api_key.id)

    return api_key


def require_api_key_scopes(required_scopes: List[str]):
    """
    Factory for an API key scope-checking dependency.

    `required_scopes` should be a list of strings like:
      - "documents:read"
      - "documents:write"

    The ApiKey.scopes field is expected to be an array of such strings.
    """

    async def _checker(api_key: ApiKey = Depends(get_current_api_key)) -> ApiKey:
        key_scopes: List[str] = api_key.scopes or []
        missing = [s for s in required_scopes if s not in key_scopes]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API key lacks required scopes",
            )
        return api_key

    return _checker


async def get_current_workspace_for_api_key(
    api_key: ApiKey = Depends(get_current_api_key),
    db: AsyncSession = Depends(get_db),
) -> Workspace:
    """
    Resolve the workspace associated with the provided API key.

    Used by `/api/v1/*` endpoints to scope data by workspace.
    """
    workspace = await _get_workspace_by_id(db, api_key.workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found for API key",
        )

    if workspace.status == "suspended":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workspace is suspended",
        )

    return workspace


__all__ = [
    "verify_password",
    "get_password_hash",
    "create_access_token",
    "get_current_user",
    "get_current_admin_user",
    "get_current_workspace",
    "get_current_workspace_member",
    "require_global_admin",
    "require_workspace_role",
    "get_current_api_key",
    "require_api_key_scopes",
    "get_current_workspace_for_api_key",
    "TokenType",
]