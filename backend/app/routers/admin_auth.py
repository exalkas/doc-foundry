"""Admin authentication router endpoints.

Separate from main auth to avoid workspace context conflicts.
Admin users don't need workspace context - they're global platform admins.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.auth.dependencies import (
    get_current_admin_user,
    create_access_token,
    verify_password,
    TokenType,
)
from app.config import settings
from app.database import get_db
from app.models.user import User, GlobalUserRole
from app.services.brute_force_protection import get_brute_force_protection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])

# Admin-specific cookie name to avoid conflicts with main app
ADMIN_COOKIE_NAME = "admin_session"


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str


class AdminUserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    is_email_verified: bool
    global_role: str

    class Config:
        from_attributes = True


class AdminLoginResponse(BaseModel):
    token: str
    user: AdminUserResponse


class AdminMeResponse(BaseModel):
    user: AdminUserResponse


def _get_admin_cookie_settings() -> dict:
    """Get cookie settings for admin sessions."""
    return {
        "httponly": True,
        "secure": settings.cookies_secure,
        "samesite": settings.cookies_samesite,
        "max_age": settings.auth_access_token_expire_seconds,
        "path": "/",
    }


@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(
    request: AdminLoginRequest,
    response: Response,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
) -> AdminLoginResponse:
    """Admin login endpoint - does NOT require workspace context."""
    logger.info(f"Admin login attempt for email: {request.email}")

    # Get client IP for brute force protection
    client_ip = http_request.client.host if http_request.client else "unknown"

    # Check brute force protection
    brute_force = get_brute_force_protection()

    # Check IP-based lockout
    is_locked_ip, remaining_seconds_ip = brute_force.is_locked_out(client_ip, "ip")
    if is_locked_ip:
        logger.warning(
            f"Admin login blocked: IP {client_ip} is locked out for {remaining_seconds_ip} seconds"
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Please try again in {remaining_seconds_ip} seconds.",
            headers={"Retry-After": str(remaining_seconds_ip)},
        )

    # Check email-based lockout
    is_locked_email, remaining_seconds_email = brute_force.is_locked_out(
        request.email, "email"
    )
    if is_locked_email:
        logger.warning(
            f"Admin login blocked: Email {request.email} is locked out for {remaining_seconds_email} seconds"
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Please try again in {remaining_seconds_email} seconds.",
            headers={"Retry-After": str(remaining_seconds_email)},
        )

    try:
        # Find user by email
        result = await db.execute(select(User).where(User.email == request.email))
        user: Optional[User] = result.scalar_one_or_none()

        if not user:
            # Record failed attempt
            brute_force.record_failed_attempt(client_ip, "ip")
            brute_force.record_failed_attempt(request.email, "email")
            logger.warning(f"Admin login failed: User not found for email: {request.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        # Verify user is admin
        if user.global_role != GlobalUserRole.ADMIN:
            brute_force.record_failed_attempt(client_ip, "ip")
            brute_force.record_failed_attempt(request.email, "email")
            logger.warning(
                f"Admin login failed: User {user.id} is not an admin (role: {user.global_role.value})"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required",
            )

        # Verify password
        if not verify_password(request.password, user.password_hash):
            brute_force.record_failed_attempt(client_ip, "ip")
            brute_force.record_failed_attempt(request.email, "email")
            logger.warning(f"Admin login failed: Invalid password for user: {request.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        # Update last login
        try:
            user.last_login_at = datetime.now(timezone.utc)
            await db.commit()
        except SQLAlchemyError as e:
            logger.warning(f"Failed to update last login time: {e}")
            await db.rollback()
            # Don't fail login if last_login update fails

        # Create JWT token WITHOUT workspace_id (admin doesn't need workspace context)
        try:
            token_data = {
                "sub": str(user.id),
                "workspace_id": None,  # Admin doesn't need workspace
                "global_role": user.global_role.value,
                "is_admin": True,  # Flag to identify admin sessions
            }
            token = create_access_token(token_data, token_type=TokenType.SESSION)
        except Exception as e:
            logger.exception(f"Error creating admin access token: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate authentication token.",
            )

        # Build response
        response_data = AdminLoginResponse(
            token=token,
            user=AdminUserResponse(
                id=str(user.id),
                email=user.email,
                full_name=user.full_name,
                is_email_verified=user.is_email_verified,
                global_role=user.global_role.value,
            ),
        )

        # Set admin-specific cookie
        response.set_cookie(
            key=ADMIN_COOKIE_NAME,
            value=token,
            **_get_admin_cookie_settings(),
        )

        # Clear brute force attempts on successful login
        brute_force.clear_attempts(client_ip, "ip")
        brute_force.clear_attempts(request.email, "email")

        logger.info(f"Admin user {user.id} logged in successfully")
        return response_data

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Catch any other unexpected errors
        logger.exception(f"Unexpected error during admin login: {e}")
        try:
            await db.rollback()
        except Exception:
            pass  # Ignore rollback errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during login.",
        )


@router.post("/logout")
async def admin_logout(response: Response) -> dict:
    """Admin logout endpoint."""
    # Clear admin cookie
    response.delete_cookie(
        key=ADMIN_COOKIE_NAME,
        path="/",
        samesite=settings.cookies_samesite,
        secure=settings.cookies_secure,
    )
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=AdminMeResponse)
async def admin_me(
    current_user: User = Depends(get_current_admin_user),
) -> AdminMeResponse:
    """Get current admin user info - does NOT require workspace context."""
    return AdminMeResponse(
        user=AdminUserResponse(
            id=str(current_user.id),
            email=current_user.email,
            full_name=current_user.full_name,
            is_email_verified=current_user.is_email_verified,
            global_role=current_user.global_role.value,
        ),
    )

