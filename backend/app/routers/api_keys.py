"""API keys router endpoints."""

import logging
import secrets
import string
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import (
    SQLAlchemyError,
    IntegrityError,
    ProgrammingError,
    OperationalError,
)

from app.auth.dependencies import (
    get_current_user,
    get_current_workspace,
    get_current_workspace_member,
    get_password_hash,
)
from app.database import get_db
from app.models.apikey import ApiKey, ApiKeyStatusEnum
from app.models.subscription import Subscription, SubscriptionStatusEnum
from app.services.plan_service import PlanService

logger = logging.getLogger(__name__)

router = APIRouter()


class ApiKeyResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    prefix: str
    scopes: List[str]
    status: str
    expires_at: str | None
    last_used_at: str | None
    created_at: str

    class Config:
        from_attributes = True


class ApiKeyCreateRequest(BaseModel):
    name: str
    scopes: List[str]
    expires_at: Optional[datetime] = None


class ApiKeyCreateResponse(BaseModel):
    api_key: ApiKeyResponse
    plaintext_key: str


def generate_api_key(prefix: str = "dk_live") -> str:
    """
    Generate a secure API key in the format: <prefix>.<random_secret>
    
    The secret part is 32 bytes of random base64url-safe characters.
    """
    # Generate 32 bytes of random data, encode as base64url-safe string
    secret = secrets.token_urlsafe(32)
    return f"{prefix}_{secret}"


@router.get("", response_model=List[ApiKeyResponse])
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
) -> List[ApiKeyResponse]:
    """List API keys for the current workspace."""
    logger.info(f"Listing API keys for workspace: {current_workspace.id}")
    
    try:
        result = await db.execute(
            select(ApiKey)
            .where(ApiKey.workspace_id == current_workspace.id)
            .order_by(ApiKey.created_at.desc())
        )
        api_keys = result.scalars().all()
        
        return [
            ApiKeyResponse(
                id=str(ak.id),
                workspace_id=str(ak.workspace_id),
                name=ak.name,
                prefix=ak.prefix,
                scopes=ak.scopes,
                status=ak.status,
                expires_at=ak.expires_at.isoformat() if ak.expires_at else None,
                last_used_at=ak.last_used_at.isoformat() if ak.last_used_at else None,
                created_at=ak.created_at.isoformat(),
            )
            for ak in api_keys
        ]
    except ProgrammingError as e:
        logger.error(f"Database schema error listing API keys: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        logger.error(f"Database connection error listing API keys: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        logger.exception(f"Database error listing API keys: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list API keys",
        )
    except Exception as e:
        logger.exception(f"Unexpected error listing API keys: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.post("", response_model=ApiKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    request: ApiKeyCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_user = Depends(get_current_user),
    current_member = Depends(get_current_workspace_member),
) -> ApiKeyCreateResponse:
    """Create a new API key and return plaintext once."""
    logger.info(f"Creating API key '{request.name}' in workspace: {current_workspace.id}")
    
    try:
        # Get plan tier for the workspace (subscriptions are per-user, not per-workspace)
        plan_tier = "free"
        subscription_result = await db.execute(
            select(Subscription)
            .where(
                Subscription.user_id == current_user.id,
                Subscription.status.in_([SubscriptionStatusEnum.ACTIVE, SubscriptionStatusEnum.TRIALING]),
            )
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
        subscription = subscription_result.scalar_one_or_none()
        if subscription:
            plan_tier = subscription.plan_id.value if hasattr(subscription.plan_id, 'value') else str(subscription.plan_id).lower()
        
        # Count existing active API keys
        active_keys_result = await db.execute(
            select(ApiKey)
            .where(
                ApiKey.workspace_id == current_workspace.id,
                ApiKey.status == ApiKeyStatusEnum.ACTIVE,
            )
        )
        active_keys = active_keys_result.scalars().all()
        current_api_key_count = len(active_keys)
        
        # Check API key limit
        plan_service = PlanService()
        is_valid, error_msg = plan_service.check_api_key_limit(plan_tier, current_api_key_count)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_msg or "API key limit exceeded for your plan",
            )
        
        # Generate API key
        prefix = "dk_live"
        plaintext_key = generate_api_key(prefix)
        
        # Hash the full key for storage
        key_hash = get_password_hash(plaintext_key)
        
        # Extract prefix from generated key (first part before underscore)
        # Format: dk_live_<secret> -> prefix is "dk_live"
        key_prefix = plaintext_key.split("_", 1)[0] if "_" in plaintext_key else prefix
        
        # Ensure prefix is max 16 chars (as per model constraint)
        if len(key_prefix) > 16:
            key_prefix = key_prefix[:16]
        
        api_key = ApiKey(
            workspace_id=current_workspace.id,
            name=request.name,
            key_hash=key_hash,
            prefix=key_prefix,
            scopes=request.scopes,
            status="active",  # Use string directly to avoid SQLAlchemy enum serialization issues
            expires_at=request.expires_at,
        )
        
        db.add(api_key)
        await db.commit()
        await db.refresh(api_key)
        
        logger.info(f"API key created successfully: {api_key.id}")
        
        return ApiKeyCreateResponse(
            api_key=ApiKeyResponse(
                id=str(api_key.id),
                workspace_id=str(api_key.workspace_id),
                name=api_key.name,
                prefix=api_key.prefix,
                scopes=api_key.scopes,
                status=api_key.status,
                expires_at=api_key.expires_at.isoformat() if api_key.expires_at else None,
                last_used_at=api_key.last_used_at.isoformat() if api_key.last_used_at else None,
                created_at=api_key.created_at.isoformat(),
            ),
            plaintext_key=plaintext_key,
        )
    except IntegrityError as e:
        await db.rollback()
        logger.warning(f"Integrity error creating API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid API key data",
        )
    except ProgrammingError as e:
        await db.rollback()
        logger.error(f"Database schema error creating API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        await db.rollback()
        logger.error(f"Database connection error creating API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        await db.rollback()
        logger.exception(f"Database error creating API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create API key",
        )
    except Exception as e:
        await db.rollback()
        logger.exception(f"Unexpected error creating API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.post("/{api_key_id}/revoke", response_model=ApiKeyResponse)
async def revoke_api_key(
    api_key_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
) -> ApiKeyResponse:
    """Revoke an API key."""
    logger.info(f"Revoking API key: {api_key_id}")
    
    try:
        result = await db.execute(
            select(ApiKey).where(
                ApiKey.id == api_key_id,
                ApiKey.workspace_id == current_workspace.id,
            )
        )
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found",
            )
        
        api_key.status = "revoked"  # Use string directly to avoid SQLAlchemy enum serialization issues
        await db.commit()
        await db.refresh(api_key)
        
        logger.info(f"API key revoked successfully: {api_key_id}")
        
        return ApiKeyResponse(
            id=str(api_key.id),
            workspace_id=str(api_key.workspace_id),
            name=api_key.name,
            prefix=api_key.prefix,
            scopes=api_key.scopes,
            status=api_key.status.value,
            expires_at=api_key.expires_at.isoformat() if api_key.expires_at else None,
            last_used_at=api_key.last_used_at.isoformat() if api_key.last_used_at else None,
            created_at=api_key.created_at.isoformat(),
        )
    except HTTPException:
        raise
    except ProgrammingError as e:
        await db.rollback()
        logger.error(f"Database schema error revoking API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        await db.rollback()
        logger.error(f"Database connection error revoking API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        await db.rollback()
        logger.exception(f"Database error revoking API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke API key",
        )
    except Exception as e:
        await db.rollback()
        logger.exception(f"Unexpected error revoking API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )

