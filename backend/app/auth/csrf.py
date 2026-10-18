"""CSRF protection utilities for FastAPI."""

import logging
import secrets
from typing import Optional

from fastapi import Request, HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)


def generate_csrf_token() -> str:
    """Generate a secure CSRF token.
    
    Returns:
        A cryptographically secure random token string
    """
    return secrets.token_urlsafe(32)


def get_csrf_token_from_session(request: Request) -> Optional[str]:
    """Get CSRF token from session.
    
    Args:
        request: FastAPI request object
    
    Returns:
        CSRF token string or None if not found
    """
    return request.session.get("csrf_token")


def set_csrf_token_in_session(request: Request, token: str) -> None:
    """Set CSRF token in session.
    
    Args:
        request: FastAPI request object
        token: CSRF token to store
    """
    request.session["csrf_token"] = token


def validate_csrf_token(request: Request, token: Optional[str] = None) -> bool:
    """Validate CSRF token from request.
    
    Checks the token from:
    1. X-CSRF-Token header (preferred)
    2. X-CSRFToken header (alternative)
    3. csrf_token form field (for form submissions)
    
    Args:
        request: FastAPI request object
        token: Optional token to validate (if not provided, extracts from request)
    
    Returns:
        True if token is valid, False otherwise
    """
    if not token:
        # Try to get token from headers
        token = request.headers.get("X-CSRF-Token") or request.headers.get("X-CSRFToken")
        
        # If not in headers, try form data (for form submissions)
        if not token and hasattr(request, "form"):
            try:
                form_data = request.form()
                token = form_data.get("csrf_token")
            except Exception:
                pass
    
    if not token:
        logger.warning("CSRF token not found in request")
        return False
    
    # Get token from session
    session_token = get_csrf_token_from_session(request)
    
    if not session_token:
        logger.warning("CSRF token not found in session")
        return False
    
    # Compare tokens using constant-time comparison
    if not secrets.compare_digest(token, session_token):
        logger.warning("CSRF token mismatch")
        return False
    
    return True


def require_csrf_token(request: Request) -> None:
    """Require valid CSRF token or raise HTTPException.
    
    Args:
        request: FastAPI request object
    
    Raises:
        HTTPException: If CSRF token is missing or invalid
    """
    # Skip CSRF check for safe methods (GET, HEAD, OPTIONS)
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    
    if not validate_csrf_token(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing CSRF token",
        )

