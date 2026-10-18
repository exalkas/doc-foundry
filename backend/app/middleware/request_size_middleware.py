"""Request size limiting middleware for FastAPI."""

import logging
from typing import Callable

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logger = logging.getLogger(__name__)


class RequestSizeMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce maximum request body and headers size."""

    async def dispatch(self, request: Request, call_next: Callable):
        """Check request size before processing."""
        # Check headers size
        headers_size = sum(len(k) + len(v) for k, v in request.headers.items())
        max_headers_size_bytes = settings.MAX_HEADERS_SIZE_KB * 1024
        
        if headers_size > max_headers_size_bytes:
            logger.warning(
                f"Request headers too large: {headers_size} bytes (max: {max_headers_size_bytes})"
            )
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Request headers too large. Maximum size: {settings.MAX_HEADERS_SIZE_KB}KB",
            )
        
        # Check body size (for requests with body)
        if request.method in ("POST", "PUT", "PATCH"):
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    body_size = int(content_length)
                    max_body_size_bytes = settings.MAX_REQUEST_BODY_SIZE_MB * 1024 * 1024
                    
                    if body_size > max_body_size_bytes:
                        logger.warning(
                            f"Request body too large: {body_size} bytes (max: {max_body_size_bytes})"
                        )
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"Request body too large. Maximum size: {settings.MAX_REQUEST_BODY_SIZE_MB}MB",
                        )
                except ValueError:
                    # Invalid content-length header, let it through (will fail later)
                    pass
        
        response = await call_next(request)
        return response

