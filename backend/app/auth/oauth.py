import logging
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

import httpx
from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel, BaseSettings, HttpUrl

from app.auth.utils import create_session_token
from app.config import get_settings
from app.database import get_db_session
from app.models.user import AuthProvider, GlobalRole, User
from app.models.workspace import Workspace
from app.models.workspacemember import WorkspaceMember, WorkspaceMemberRole, WorkspaceMemberStatus

logger = logging.getLogger(__name__)


class OAuthSettings(BaseSettings):
    """Settings specific to OAuth flows (currently Google)."""

    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_redirect_uri: Optional[HttpUrl] = None
    frontend_app_base_url: Optional[HttpUrl] = None

    class Config:
        env_prefix = "OAUTH_"
        case_sensitive = False


def get_oauth_settings() -> OAuthSettings:
    """Dependency to load OAuth-related settings."""
    return OAuthSettings()


class GoogleUserInfo(BaseModel):
    """Subset of Google user info used by the app."""

    sub: str
    email: str
    email_verified: bool
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    picture: Optional[HttpUrl] = None


async def exchange_google_code_for_tokens(
    code: str,
    oauth_settings: OAuthSettings,
) -> Dict[str, Any]:
    """
    Exchange an authorization code for Google OAuth tokens.

    Raises:
        HTTPException: If the exchange fails or Google returns an error.
    """
    if not oauth_settings.google_client_id or not oauth_settings.google_client_secret or not oauth_settings.google_redirect_uri:
        logger.error("Google OAuth settings are not fully configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OAuth provider not configured",
        )

    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": oauth_settings.google_client_id,
        "client_secret": oauth_settings.google_client_secret,
        "redirect_uri": str(oauth_settings.google_redirect_uri),
        "grant_type": "authorization_code",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(token_url, data=data)
    except httpx.RequestError as exc:
        logger.exception("Error while requesting Google token endpoint: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to contact OAuth provider",
        )

    if resp.status_code != 200:
        logger.warning(
            "Google token endpoint returned non-200 status: %s body=%s",
            resp.status_code,
            resp.text,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid authorization code",
        )

    token_data = resp.json()
    if "access_token" not in token_data:
        logger.error("Google token response missing access_token: %s", token_data)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to obtain access token from provider",
        )

    return token_data


async def fetch_google_userinfo(access_token: str) -> GoogleUserInfo:
    """
    Fetch the current user's profile from Google using the access token.

    Raises:
        HTTPException: If Google userinfo endpoint fails or returns invalid data.
    """
    userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"

    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(userinfo_url, headers=headers)
    except httpx.RequestError as exc:
        logger.exception("Error while requesting Google userinfo: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to contact OAuth provider",
        )

    if resp.status_code != 200:
        logger.warning(
            "Google userinfo endpoint returned non-200 status: %s body=%s",
            resp.status_code,
            resp.text,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to fetch user profile from provider",
        )

    try:
        data = resp.json()
        userinfo = GoogleUserInfo(**data)
    except Exception as exc:
        logger.exception("Failed to parse Google userinfo: %s body=%s", exc, resp.text)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user profile data from provider",
        )

    return userinfo


async def get_or_create_user_from_google(
    userinfo: GoogleUserInfo,
    db=Depends(get_db_session),
) -> Tuple[User, Workspace]:
    """
    Find existing user by email or create a new user and default workspace.

    Returns:
        (user, current_workspace)
    """
    from sqlalchemy import select

    # Normalize email
    email = userinfo.email.strip().lower()

    result = await db.execute(select(User).where(User.email == email))
    user: Optional[User] = result.scalar_one_or_none()

    if user:
        # Existing user: update verification and last_login
        user.is_email_verified = userinfo.email_verified or user.is_email_verified
        user.auth_provider = AuthProvider.GOOGLE
        await db.flush()
        # Try to find a workspace where they are a member (owner/member/readonly)
        ws_result = await db.execute(
            select(Workspace)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(
                WorkspaceMember.user_id == user.id,
                WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
            )
            .order_by(Workspace.created_at.asc())
        )
        workspace = ws_result.scalars().first()
        # If no workspace membership found, do not auto-create for existing users.
        # Caller can handle workspace selection/creation.
        return user, workspace  # type: ignore[return-value]

    # New user signup via Google
    user = User(
        email=email,
        password_hash="",  # no local password
        full_name=userinfo.name or f"{userinfo.given_name or ''} {userinfo.family_name or ''}".strip() or None,
        is_email_verified=userinfo.email_verified,
        auth_provider=AuthProvider.GOOGLE,
        global_role=GlobalRole.USER,
    )
    db.add(user)
    await db.flush()

    # Create a default workspace for the new user
    workspace_name = user.full_name or "My Workspace"
    workspace = Workspace(
        name=workspace_name,
        owner_user_id=user.id,
    )
    db.add(workspace)
    await db.flush()

    # Create membership linking user to workspace as owner
    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user.id,
        role=WorkspaceMemberRole.OWNER,
        status=WorkspaceMemberStatus.ACTIVE,
    )
    db.add(member)
    await db.flush()

    return user, workspace


async def handle_google_oauth_callback(
    request: Request,
    code: Optional[str],
    state: Optional[str],
    oauth_settings: OAuthSettings = Depends(get_oauth_settings),
    settings=Depends(get_settings),
    db=Depends(get_db_session),
) -> Dict[str, Any]:
    """
    Handle the Google OAuth callback:

    1. Exchange code for tokens.
    2. Fetch user profile.
    3. Upsert user + workspace/membership.
    4. Issue a session JWT and return data for frontend.

    This is designed to be used from within a FastAPI route.
    """
    if not code:
        logger.warning("Google OAuth callback missing 'code' parameter, state=%s", state)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing authorization code",
        )

    token_data = await exchange_google_code_for_tokens(code, oauth_settings)
    access_token = token_data.get("access_token")
    id_token = token_data.get("id_token")  # not strictly needed here but may be useful.

    userinfo = await fetch_google_userinfo(access_token)

    # Upsert user + workspace
    user, workspace = await get_or_create_user_from_google(userinfo, db=db)

    # Persist DB changes
    await db.commit()

    # Create session token (JWT) with workspace context
    session_id = str(uuid4())
    token = create_session_token(
        user_id=str(user.id),
        workspace_id=str(workspace.id) if workspace else None,
        session_id=session_id,
        settings=settings,
    )

    # The frontend is expected to receive this token (e.g. via JSON) and set
    # it in a secure HTTP-only cookie. Alternatively, a dedicated endpoint
    # can wrap this logic and set cookies directly.
    response_payload: Dict[str, Any] = {
        "token": token,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "is_email_verified": user.is_email_verified,
            "auth_provider": user.auth_provider.value
            if hasattr(user.auth_provider, "value")
            else str(user.auth_provider),
            "global_role": user.global_role.value
            if hasattr(user.global_role, "value")
            else str(user.global_role),
        },
        "current_workspace": {
            "id": str(workspace.id),
            "name": workspace.name,
            "status": workspace.status.value
            if hasattr(workspace.status, "value")
            else str(workspace.status),
        }
        if workspace
        else None,
    }

    logger.info(
        "User logged in via Google OAuth",
        extra={
            "user_id": str(user.id),
            "workspace_id": str(workspace.id) if workspace else None,
            "oauth_provider": "google",
        },
    )

    return response_payload