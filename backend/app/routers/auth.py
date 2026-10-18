"""Authentication router endpoints."""

import logging
from datetime import datetime, timezone
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from starlette.requests import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import (
    SQLAlchemyError,
    IntegrityError,
    ProgrammingError,
    OperationalError,
)

from app.auth.dependencies import (
    create_access_token,
    get_current_user,
    get_current_workspace,
    get_password_hash,
    verify_password,
    TokenType,
)
from app.models.user import GlobalUserRole
from app.auth.schemas import (
    LoginRequest,
    LoginResponse,
    MeResponse,
    RegisterRequest,
    RegisterResponse,
    SwitchWorkspaceRequest,
    SwitchWorkspaceResponse,
    UserResponse,
    WorkspaceResponse,
)
from app.config import settings
from app.database import get_db
from app.models.user import User, GlobalUserRole
from app.models.workspace import Workspace, WorkspaceStatus
from app.models.workspacemember import WorkspaceMember, WorkspaceMemberRole, WorkspaceMemberStatus
from app.services.brute_force_protection import get_brute_force_protection
from app.auth.csrf import generate_csrf_token, set_csrf_token_in_session, require_csrf_token

logger = logging.getLogger(__name__)

router = APIRouter()

# Rate limit string for auth endpoints
AUTH_RATE_LIMIT = f"{settings.RATE_LIMIT_AUTH_PER_MINUTE}/minute"


def _get_cookie_settings() -> dict:
    """Get cookie configuration for auth cookies."""
    return {
        "httponly": True,
        "secure": settings.cookies_secure,
        "samesite": settings.cookies_samesite,
        "max_age": settings.access_token_expire_minutes * 60,
        "path": "/",
    }


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    response: Response,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    """Register a new user and create their initial workspace."""
    logger.info(f"Registration attempt for email: {request.email}")
    
    try:
        # Check if user already exists
        try:
            existing_user_result = await db.execute(
                select(User).where(User.email == request.email)
            )
            existing_user = existing_user_result.scalar_one_or_none()
        except ProgrammingError as e:
            logger.error(f"Database schema error during user lookup: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not properly initialized. Please run migrations.",
            )
        except OperationalError as e:
            logger.error(f"Database connection error during user lookup: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection failed. Please try again later.",
            )
        except SQLAlchemyError as e:
            logger.exception(f"Unexpected database error during user lookup: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while processing your request.",
            )
        
        if existing_user:
            logger.warning(f"Registration attempt with existing email: {request.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        # Create user
        try:
            password_hash = get_password_hash(request.password)
            user = User(
                email=request.email,
                password_hash=password_hash,
                full_name=request.full_name,
                is_email_verified=False,
            )
            db.add(user)
            await db.flush()  # Flush to get user.id
            logger.debug(f"User created with ID: {user.id}")
        except IntegrityError as e:
            logger.error(f"Integrity error creating user: {e}")
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user data provided.",
            )
        except SQLAlchemyError as e:
            logger.exception(f"Database error creating user: {e}")
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user account.",
            )

        # Create workspace
        try:
            workspace = Workspace(
                name=request.workspace_name,
                owner_user_id=user.id,
                status=WorkspaceStatus.TRIAL,
            )
            db.add(workspace)
            await db.flush()  # Flush to get workspace.id
            logger.debug(f"Workspace created with ID: {workspace.id}")
        except SQLAlchemyError as e:
            logger.exception(f"Database error creating workspace: {e}")
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create workspace.",
            )

        # Create workspace membership
        try:
            member = WorkspaceMember(
                workspace_id=workspace.id,
                user_id=user.id,
                role=WorkspaceMemberRole.OWNER,
                status=WorkspaceMemberStatus.ACTIVE,
                joined_at=datetime.now(timezone.utc),
            )
            db.add(member)
            await db.commit()
            logger.info(f"User {user.id} registered successfully with workspace {workspace.id}")
        except IntegrityError as e:
            logger.error(f"Integrity error creating workspace membership: {e}")
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to complete registration.",
            )
        except SQLAlchemyError as e:
            logger.exception(f"Database error creating workspace membership: {e}")
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to complete registration.",
            )

        # Create JWT token
        try:
            token_data = {
                "sub": str(user.id),
                "workspace_id": str(workspace.id),
                "global_role": user.global_role.value,
            }
            token = create_access_token(token_data, token_type=TokenType.SESSION)
        except Exception as e:
            logger.exception(f"Error creating access token: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate authentication token.",
            )

        # Build response
        response_data = RegisterResponse(
            token=token,
            user=UserResponse(
                id=str(user.id),
                email=user.email,
                full_name=user.full_name,
                is_email_verified=user.is_email_verified,
                global_role=user.global_role.value,
            ),
            workspace=WorkspaceResponse(
                id=str(workspace.id),
                name=workspace.name,
                status=workspace.status.value,
                owner_user_id=str(workspace.owner_user_id),
            ),
        )

        # Clear brute force attempts on successful registration
        client_ip = http_request.client.host if http_request.client else "unknown"
        brute_force = get_brute_force_protection()
        brute_force.clear_attempts(client_ip, "ip")
        brute_force.clear_attempts(request.email, "email")
        
        # Check for affiliate cookie and create attribution
        import os
        affiliate_slug = http_request.cookies.get(os.getenv("AFFILIATE_COOKIE_NAME", "aff_id"))
        if affiliate_slug:
            try:
                from app.services.attribution_service import AttributionService
                affiliate = await AttributionService.get_affiliate_from_cookie(db, affiliate_slug)
                if affiliate:
                    await AttributionService.attribute_customer(
                        db=db,
                        customer_id=user.id,
                        affiliate_id=affiliate.id,
                        attribution_source="link",
                    )
                    logger.info(f"Attributed new user {user.id} to affiliate {affiliate.id}")
            except Exception as e:
                logger.warning(f"Failed to attribute user to affiliate: {e}")
                # Don't fail registration if attribution fails
        
        # Set cookie in response
        response.set_cookie(
            key=settings.auth_cookie_name,
            value=token,
            **_get_cookie_settings(),
        )

        return response_data
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Catch any other unexpected errors
        logger.exception(f"Unexpected error during registration: {e}")
        try:
            await db.rollback()
        except Exception:
            pass  # Ignore rollback errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during registration.",
        )


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    response: Response,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Login with email and password."""
    logger.info(f"Login attempt for email: {request.email}")
    
    # Get client IP for brute force protection
    client_ip = http_request.client.host if http_request.client else "unknown"
    
    # Check brute force protection
    brute_force = get_brute_force_protection()
    
    # Check IP-based lockout
    is_locked_ip, remaining_seconds_ip = brute_force.is_locked_out(client_ip, "ip")
    if is_locked_ip:
        logger.warning(f"Login blocked: IP {client_ip} is locked out for {remaining_seconds_ip} seconds")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Please try again in {remaining_seconds_ip} seconds.",
            headers={"Retry-After": str(remaining_seconds_ip)},
        )
    
    # Check email-based lockout
    is_locked_email, remaining_seconds_email = brute_force.is_locked_out(request.email, "email")
    if is_locked_email:
        logger.warning(f"Login blocked: Email {request.email} is locked out for {remaining_seconds_email} seconds")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Please try again in {remaining_seconds_email} seconds.",
            headers={"Retry-After": str(remaining_seconds_email)},
        )
    
    try:
        # Find user
        try:
            user_result = await db.execute(
                select(User).where(User.email == request.email)
            )
            user = user_result.scalar_one_or_none()
        except ProgrammingError as e:
            logger.error(f"Database schema error during login: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not properly initialized. Please run migrations.",
            )
        except OperationalError as e:
            logger.error(f"Database connection error during login: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection failed. Please try again later.",
            )
        except SQLAlchemyError as e:
            logger.exception(f"Unexpected database error during login: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while processing your request.",
            )
        
        if not user:
            # Don't leak whether email exists
            logger.warning(f"Login attempt with non-existent email: {request.email}")
            # Record failed attempt for both IP and email
            brute_force.record_failed_attempt(client_ip, "ip")
            brute_force.record_failed_attempt(request.email, "email")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        # Verify password
        if not verify_password(request.password, user.password_hash):
            # Record failed attempt
            is_locked_ip, _ = brute_force.record_failed_attempt(client_ip, "ip")
            is_locked_email, remaining = brute_force.record_failed_attempt(request.email, "email")
            
            if is_locked_ip or is_locked_email:
                logger.warning(f"Login failed: Account locked after too many attempts")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many failed login attempts. Please try again in {remaining} seconds.",
                    headers={"Retry-After": str(remaining)} if remaining else {},
                )
            logger.warning(f"Invalid password for user: {request.email}")
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

        # Get user's workspaces
        try:
            memberships_result = await db.execute(
                select(WorkspaceMember)
                .where(WorkspaceMember.user_id == user.id)
                .where(WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE)
            )
            memberships = list(memberships_result.scalars().all())
        except SQLAlchemyError as e:
            logger.exception(f"Database error fetching workspaces: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve user workspaces.",
            )

        # Admin users don't require workspace memberships
        if not memberships and user.global_role.value != "admin":
            logger.warning(f"User {user.id} has no active workspace memberships")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not a member of any workspace",
            )

        # Get workspace details
        workspaces = []
        current_workspace = None
        if memberships:
            try:
                workspace_ids = [m.workspace_id for m in memberships]
                workspaces_result = await db.execute(
                    select(Workspace).where(Workspace.id.in_(workspace_ids))
                )
                workspaces = list(workspaces_result.scalars().all())
            except SQLAlchemyError as e:
                logger.exception(f"Database error fetching workspace details: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to retrieve workspace details.",
                )

            # Determine current workspace (use first active membership)
            current_workspace = workspaces[0] if workspaces else None

        # Create JWT token with current workspace (admin users may not have workspace)
        try:
            token_data = {
                "sub": str(user.id),
                "workspace_id": str(current_workspace.id) if current_workspace else None,
                "global_role": user.global_role.value,
            }
            token = create_access_token(token_data, token_type=TokenType.SESSION)
        except Exception as e:
            logger.exception(f"Error creating access token: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate authentication token.",
            )

        # Build response
        response_data = LoginResponse(
            token=token,
            user=UserResponse(
                id=str(user.id),
                email=user.email,
                full_name=user.full_name,
                is_email_verified=user.is_email_verified,
                global_role=user.global_role.value,
            ),
            workspaces=[
                WorkspaceResponse(
                    id=str(ws.id),
                    name=ws.name,
                    status=ws.status.value,
                    owner_user_id=str(ws.owner_user_id),
                )
                for ws in workspaces
            ],
            current_workspace=WorkspaceResponse(
                id=str(current_workspace.id),
                name=current_workspace.name,
                status=current_workspace.status.value,
                owner_user_id=str(current_workspace.owner_user_id),
            )
            if current_workspace
            else None,
        )

        # Set cookie in response
        response.set_cookie(
            key=settings.auth_cookie_name,
            value=token,
            **_get_cookie_settings(),
        )

        logger.info(f"User {user.id} logged in successfully")
        return response_data
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Catch any other unexpected errors
        logger.exception(f"Unexpected error during login: {e}")
        try:
            await db.rollback()
        except Exception:
            pass  # Ignore rollback errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during login.",
        )


@router.get("/csrf-token")
async def get_csrf_token(request: Request) -> dict:
    """Get CSRF token for the current session.
    
    This endpoint should be called by the frontend to obtain a CSRF token
    that must be included in subsequent state-changing requests (POST, PUT, DELETE, PATCH).
    """
    token = generate_csrf_token()
    set_csrf_token_in_session(request, token)
    return {"csrf_token": token}


@router.get("/me", response_model=MeResponse)
async def me(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    """Get current user info, workspaces, and current workspace."""
    logger.debug(f"Fetching user info for user ID: {current_user.id}")
    
    try:
        # Get all user's workspaces
        try:
            memberships_result = await db.execute(
                select(WorkspaceMember)
                .where(WorkspaceMember.user_id == current_user.id)
                .where(WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE)
            )
            memberships = list(memberships_result.scalars().all())
        except SQLAlchemyError as e:
            logger.exception(f"Database error fetching workspace memberships: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve workspace memberships.",
            )

        workspace_ids = [m.workspace_id for m in memberships]
        if workspace_ids:
            try:
                workspaces_result = await db.execute(
                    select(Workspace).where(Workspace.id.in_(workspace_ids))
                )
                workspaces = list(workspaces_result.scalars().all())
            except SQLAlchemyError as e:
                logger.exception(f"Database error fetching workspace details: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to retrieve workspace details.",
                )
        else:
            workspaces = []

        # Get current workspace - use first workspace from memberships, or try to get from JWT/header
        current_workspace = None
        if workspaces:
            # Try to get workspace from JWT token or header
            token_workspace_id = getattr(request.state, "token_payload", {}).get("workspace_id")
            header_workspace_id = request.headers.get("X-Workspace-Id")
            
            # Find workspace by ID if specified
            selected_workspace = None
            if token_workspace_id:
                selected_workspace = next((ws for ws in workspaces if str(ws.id) == str(token_workspace_id)), None)
            if not selected_workspace and header_workspace_id:
                selected_workspace = next((ws for ws in workspaces if str(ws.id) == str(header_workspace_id)), None)
            
            # Fallback to first workspace
            if not selected_workspace:
                selected_workspace = workspaces[0]
            
            current_workspace = selected_workspace

        return MeResponse(
            user=UserResponse(
                id=str(current_user.id),
                email=current_user.email,
                full_name=current_user.full_name,
                is_email_verified=current_user.is_email_verified,
                global_role=current_user.global_role.value,
            ),
            workspaces=[
                WorkspaceResponse(
                    id=str(ws.id),
                    name=ws.name,
                    status=ws.status.value,
                    owner_user_id=str(ws.owner_user_id),
                )
                for ws in workspaces
            ],
            current_workspace=WorkspaceResponse(
                id=str(current_workspace.id),
                name=current_workspace.name,
                status=current_workspace.status.value,
                owner_user_id=str(current_workspace.owner_user_id),
            )
            if current_workspace
            else None,
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Catch any other unexpected errors
        logger.exception(f"Unexpected error fetching user info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching user information.",
        )


@router.post("/switch-workspace", response_model=SwitchWorkspaceResponse)
async def switch_workspace(
    request: SwitchWorkspaceRequest,
    http_request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SwitchWorkspaceResponse:
    """Switch the current workspace for the authenticated user."""
    # Validate CSRF token
    require_csrf_token(http_request)
    logger.info(f"Workspace switch request for user {current_user.id} to workspace {request.workspace_id}")
    
    try:
        # Verify user is a member of the requested workspace
        try:
            membership_result = await db.execute(
                select(WorkspaceMember)
                .where(WorkspaceMember.workspace_id == request.workspace_id)
                .where(WorkspaceMember.user_id == current_user.id)
                .where(WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE)
            )
            membership = membership_result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.exception(f"Database error checking workspace membership: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to verify workspace membership.",
            )

        if not membership:
            logger.warning(
                f"User {current_user.id} attempted to switch to workspace {request.workspace_id} "
                "but is not a member"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not a member of this workspace",
            )

        # Get workspace
        try:
            workspace_result = await db.execute(
                select(Workspace).where(Workspace.id == request.workspace_id)
            )
            workspace = workspace_result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.exception(f"Database error fetching workspace: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve workspace information.",
            )

        if not workspace:
            logger.warning(f"Workspace {request.workspace_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )

        # Create new token with updated workspace_id
        try:
            token_data = {
                "sub": str(current_user.id),
                "workspace_id": str(workspace.id),
                "global_role": current_user.global_role.value,
            }
            token = create_access_token(token_data, token_type=TokenType.SESSION)
        except Exception as e:
            logger.exception(f"Error creating access token: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate authentication token.",
            )

        # Build response
        response_data = SwitchWorkspaceResponse(
            current_workspace=WorkspaceResponse(
                id=str(workspace.id),
                name=workspace.name,
                status=workspace.status.value,
                owner_user_id=str(workspace.owner_user_id),
            ),
        )

        # Set cookie in response
        response.set_cookie(
            key=settings.auth_cookie_name,
            value=token,
            **_get_cookie_settings(),
        )

        logger.info(f"User {current_user.id} switched to workspace {workspace.id}")
        return response_data
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Catch any other unexpected errors
        logger.exception(f"Unexpected error during workspace switch: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while switching workspace.",
        )

