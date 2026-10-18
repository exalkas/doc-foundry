"""Notifications router endpoints."""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import (
    SQLAlchemyError,
    ProgrammingError,
    OperationalError,
)

from app.auth.dependencies import (
    get_current_user,
    get_current_workspace,
    get_current_workspace_member,
)
from app.database import get_db
from app.models.notification import Notification, NotificationChannel

logger = logging.getLogger(__name__)

router = APIRouter()


class NotificationResponse(BaseModel):
    id: str
    user_id: str
    workspace_id: str | None
    channel: str
    event_type: str
    payload: dict
    read_at: str | None
    created_at: str

    class Config:
        from_attributes = True


@router.get("", response_model=List[NotificationResponse])
async def list_notifications(
    unread_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_user = Depends(get_current_user),
    current_member = Depends(get_current_workspace_member),
) -> List[NotificationResponse]:
    """List notifications for the current user, optionally filtered to unread only."""
    logger.info(f"Listing notifications for user: {current_user.id}")
    
    try:
        query = select(Notification).where(Notification.user_id == current_user.id)
        
        # Filter by workspace if in workspace context
        if current_workspace:
            query = query.where(
                (Notification.workspace_id == current_workspace.id) | 
                (Notification.workspace_id.is_(None))
            )
        
        # Filter unread only if requested
        if unread_only:
            query = query.where(Notification.read_at.is_(None))
        
        query = query.order_by(Notification.created_at.desc())
        
        result = await db.execute(query)
        notifications = result.scalars().all()
        
        return [
            NotificationResponse(
                id=str(n.id),
                user_id=str(n.user_id),
                workspace_id=str(n.workspace_id) if n.workspace_id else None,
                channel=n.channel.value,
                event_type=n.event_type,
                payload=n.payload,
                read_at=n.read_at.isoformat() if n.read_at else None,
                created_at=n.created_at.isoformat(),
            )
            for n in notifications
        ]
    except ProgrammingError as e:
        logger.error(f"Database schema error listing notifications: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        logger.error(f"Database connection error listing notifications: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        logger.exception(f"Database error listing notifications: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list notifications",
        )
    except Exception as e:
        logger.exception(f"Unexpected error listing notifications: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_notification_read(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    current_member = Depends(get_current_workspace_member),
) -> None:
    """Mark a notification as read."""
    logger.info(f"Marking notification as read: {notification_id}")
    
    try:
        result = await db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == current_user.id,
            )
        )
        notification = result.scalar_one_or_none()
        
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found",
            )
        
        if notification.read_at is None:
            notification.mark_read()
            await db.commit()
            logger.info(f"Notification marked as read: {notification_id}")
    except HTTPException:
        raise
    except ProgrammingError as e:
        await db.rollback()
        logger.error(f"Database schema error marking notification read: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        await db.rollback()
        logger.error(f"Database connection error marking notification read: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        await db.rollback()
        logger.exception(f"Database error marking notification read: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark notification as read",
        )
    except Exception as e:
        await db.rollback()
        logger.exception(f"Unexpected error marking notification read: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )

