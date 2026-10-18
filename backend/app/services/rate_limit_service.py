"""Rate limiting service using slowapi with Redis or in-memory storage."""

import logging
from typing import Optional
from uuid import UUID

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
except ImportError:
    Limiter = None
    _rate_limit_exceeded_handler = None
    get_remote_address = None
    RateLimitExceeded = None
    SlowAPIMiddleware = None

try:
    import redis
    from redis import Redis
except ImportError:
    redis = None
    Redis = None

from app.config import settings

logger = logging.getLogger(__name__)


def get_limiter_key_func(request) -> str:
    """Get rate limit key based on authentication status.
    
    Priority:
    1. User ID (if authenticated)
    2. API Key ID (if API key authenticated)
    3. IP address (if unauthenticated)
    """
    # Try to get user ID from request state (set by auth dependencies)
    if hasattr(request.state, "user_id"):
        user_id = request.state.user_id
        if user_id:
            return f"user:{user_id}"
    
    # Try to get API key ID from request state
    if hasattr(request.state, "api_key_id"):
        api_key_id = request.state.api_key_id
        if api_key_id:
            return f"api_key:{api_key_id}"
    
    # Fall back to IP address
    if get_remote_address:
        return f"ip:{get_remote_address(request)}"
    
    # Last resort: use a default key
    return "default"


def create_limiter() -> Optional[Limiter]:
    """Create and configure slowapi Limiter instance.
    
    Returns:
        Configured Limiter instance or None if slowapi not available
    """
    if not Limiter:
        logger.warning("slowapi not installed, rate limiting disabled")
        return None
    
    if not settings.RATE_LIMIT_ENABLED:
        logger.info("Rate limiting disabled via configuration")
        return None
    
    # Configure storage backend
    if settings.RATE_LIMIT_STORAGE_URL:
        try:
            # Use Redis for distributed rate limiting
            redis_client = redis.from_url(
                settings.RATE_LIMIT_STORAGE_URL,
                decode_responses=True
            )
            # Test connection
            redis_client.ping()
            logger.info("Using Redis for rate limiting storage")
            storage_uri = settings.RATE_LIMIT_STORAGE_URL
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}, falling back to in-memory storage")
            storage_uri = "memory://"
    else:
        # Use in-memory storage (single instance only)
        logger.info("Using in-memory storage for rate limiting (single instance only)")
        storage_uri = "memory://"
    
    # Create limiter with key function
    limiter = Limiter(
        key_func=get_limiter_key_func,
        storage_uri=storage_uri,
        default_limits=[f"{settings.RATE_LIMIT_DEFAULT_PER_MINUTE}/minute"],
        headers_enabled=True,
    )
    
    return limiter


def get_rate_limit_for_endpoint(endpoint_path: str) -> Optional[str]:
    """Get rate limit string for a specific endpoint.
    
    Args:
        endpoint_path: The API endpoint path (e.g., "/api/auth/login")
    
    Returns:
        Rate limit string (e.g., "5/minute") or None for default
    """
    # Auth endpoints - stricter limits
    if "/auth/login" in endpoint_path or "/auth/register" in endpoint_path:
        return f"{settings.RATE_LIMIT_AUTH_PER_MINUTE}/minute"
    
    # File upload endpoints - stricter limits
    if "/documents" in endpoint_path and "upload" in endpoint_path.lower():
        return f"{settings.RATE_LIMIT_FILE_UPLOAD_PER_MINUTE}/minute"
    
    # API key endpoints - higher limits
    if endpoint_path.startswith("/api/v1"):
        return f"{settings.RATE_LIMIT_API_KEY_PER_MINUTE}/minute"
    
    # Default limit
    return f"{settings.RATE_LIMIT_DEFAULT_PER_MINUTE}/minute"


# Global limiter instance (initialized on first import)
_limiter: Optional[Limiter] = None


def get_limiter() -> Optional[Limiter]:
    """Get the global limiter instance, creating it if necessary."""
    global _limiter
    if _limiter is None:
        _limiter = create_limiter()
    return _limiter

