import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple, Union
from uuid import UUID

from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# -----------------------------
# Password hashing utilities
# -----------------------------


def hash_password(password: str) -> str:
    """
    Hash a plaintext password using a secure one-way algorithm.

    Args:
        password: Plaintext password.

    Returns:
        Hashed password string.
    """
    if not password:
        raise ValueError("Password must not be empty")
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """
    Verify a plaintext password against a stored hash.

    Args:
        plain_password: User-supplied password.
        password_hash: Stored password hash.

    Returns:
        True if the password matches, False otherwise.
    """
    if not password_hash:
        # If for any reason the stored hash is missing, fail closed.
        logger.warning("Attempt to verify password against empty hash")
        return False
    return pwd_context.verify(plain_password, password_hash)


# -----------------------------
# JWT utilities
# -----------------------------


def _get_jwt_settings() -> Tuple[str, str, int]:
    """
    Load JWT-related settings from configuration.

    Returns:
        A tuple of (secret_key, algorithm, access_token_expire_minutes).
    """
    settings = get_settings()
    return (
        settings.jwt_secret_key,
        settings.jwt_algorithm,
        settings.access_token_expire_minutes,
    )


def create_access_token(
    subject: Union[str, UUID],
    *,
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Create a signed JWT access token for the given subject.

    Args:
        subject: Unique identifier for the token subject (typically user ID).
        expires_delta: Optional custom expiration delta. If not provided,
                       default from settings is used.
        additional_claims: Optional extra claims to embed in the token payload.

    Returns:
        Encoded JWT token string.
    """
    secret_key, algorithm, default_expire_minutes = _get_jwt_settings()

    if expires_delta is None:
        expires_delta = timedelta(minutes=default_expire_minutes)

    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    to_encode: Dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    if additional_claims:
        # Avoid overriding reserved claims
        for k, v in additional_claims.items():
            if k in ("sub", "iat", "exp"):
                logger.warning("Ignoring attempt to override reserved JWT claim '%s'", k)
                continue
            to_encode[k] = v

    try:
        encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    except Exception:  # pragma: no cover - defensive
        logger.exception("Failed to encode JWT")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate access token",
        )

    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT, returning its payload.

    Args:
        token: Encoded JWT string.

    Returns:
        Decoded payload as a dictionary.

    Raises:
        HTTPException: If the token is invalid or expired.
    """
    secret_key, algorithm, _ = _get_jwt_settings()
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
    except JWTError as exc:
        logger.info("Failed to decode JWT: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Unexpected error decoding JWT")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        ) from exc

    return payload


def get_token_subject(payload: Dict[str, Any]) -> str:
    """
    Extract the subject (`sub`) from a decoded JWT payload.

    Args:
        payload: Decoded JWT payload.

    Returns:
        Subject value as a string.

    Raises:
        HTTPException: If subject is missing or invalid.
    """
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        logger.warning("JWT payload missing valid 'sub' claim")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    return sub


# -----------------------------
# Session / cookie helpers
# -----------------------------


def build_session_token_for_user(
    user_id: UUID,
    *,
    workspace_id: Optional[UUID] = None,
    global_role: Optional[str] = None,
) -> str:
    """
    Build a JWT session token for a given user and optional workspace context.

    Args:
        user_id: User's UUID.
        workspace_id: Optional active workspace ID.
        global_role: Optional global role (e.g. 'admin', 'user').

    Returns:
        Encoded JWT access token string.
    """
    claims: Dict[str, Any] = {}
    if workspace_id is not None:
        claims["workspace_id"] = str(workspace_id)
    if global_role is not None:
        claims["global_role"] = global_role

    return create_access_token(subject=user_id, additional_claims=claims)


def get_cookie_settings() -> Dict[str, Any]:
    """
    Return cookie configuration for setting auth cookies.

    This centralizes security-related flags for the auth cookie.

    Returns:
        Dict of cookie parameters suitable for `Response.set_cookie`.
    """
    settings = get_settings()
    # In production you should also consider `samesite="strict"` or "lax" depending on frontend
    return {
        "httponly": True,
        "secure": settings.cookies_secure,
        "samesite": settings.cookies_samesite,
        "max_age": settings.access_token_expire_minutes * 60,
        "path": "/",
    }


# -----------------------------
# CSRF helpers
# -----------------------------


def create_csrf_token() -> str:
    """
    Create a CSRF token.

    Uses JWT signing so the server can validate without server-side storage.

    Returns:
        Encoded CSRF token string.
    """
    # Shorter expiry for CSRF tokens
    expires = timedelta(minutes=60)
    return create_access_token("csrf", expires_delta=expires)


def validate_csrf_token(csrf_token: str) -> None:
    """
    Validate a CSRF token; raises HTTPException if invalid.

    Args:
        csrf_token: Encoded CSRF token string.

    Raises:
        HTTPException: If token is invalid or expired.
    """
    payload = decode_token(csrf_token)
    if payload.get("sub") != "csrf":
        logger.warning("Invalid CSRF token subject")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token",
        )


# -----------------------------
# API key hashing utilities
# -----------------------------


def hash_api_key(plaintext_key: str) -> str:
    """
    Hash an API key using the same secure hashing as passwords.

    The plaintext key is only shown once to the user; only the hash is stored.

    Args:
        plaintext_key: Raw API key.

    Returns:
        Hashed API key string.
    """
    if not plaintext_key:
        raise ValueError("API key must not be empty")
    return pwd_context.hash(plaintext_key)


def verify_api_key(plaintext_key: str, key_hash: str) -> bool:
    """
    Verify a plaintext API key against its stored hash.

    Args:
        plaintext_key: Raw API key provided by client.
        key_hash: Stored hash of the key.

    Returns:
        True if the key is valid, False otherwise.
    """
    if not key_hash:
        logger.warning("Attempt to verify API key against empty hash")
        return False
    return pwd_context.verify(plaintext_key, key_hash)