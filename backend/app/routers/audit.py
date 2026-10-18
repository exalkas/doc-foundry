"""Audit logs router endpoints."""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, and_, or_
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
from app.models.auditlog import AuditLog

logger = logging.getLogger(__name__)

router = APIRouter()


class AuditLogResponse(BaseModel):
    id: str
    workspace_id: str | None
    user_id: str | None
    actor_type: str
    event_type: str
    description: str
    metadata: dict | None
    created_at: str

    class Config:
        from_attributes = True


@router.get("", response_model=List[AuditLogResponse])
async def list_audit_logs(
    user_id: Optional[UUID] = Query(None),
    event_type: Optional[str] = Query(None),
    from_date: Optional[datetime] = Query(None, alias="from"),
    to_date: Optional[datetime] = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
) -> List[AuditLogResponse]:
    """List audit logs for the current workspace with filtering."""
    logger.info(f"Listing audit logs for workspace: {current_workspace.id}")
    
    try:
        # Build query - scope to current workspace
        query = select(AuditLog).where(
            AuditLog.workspace_id == current_workspace.id
        )
        
        # Apply filters
        if user_id:
            query = query.where(AuditLog.user_id == user_id)
        
        if event_type:
            query = query.where(AuditLog.event_type == event_type)
        
        if from_date:
            query = query.where(AuditLog.created_at >= from_date)
        
        if to_date:
            query = query.where(AuditLog.created_at <= to_date)
        
        # Order by created_at descending
        query = query.order_by(AuditLog.created_at.desc())
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        result = await db.execute(query)
        logs = result.scalars().all()
        
        return [
            AuditLogResponse(
                id=str(log.id),
                workspace_id=str(log.workspace_id) if log.workspace_id else None,
                user_id=str(log.user_id) if log.user_id else None,
                actor_type=log.actor_type.value,
                event_type=log.event_type,
                description=log.description,
                metadata=log.event_metadata,
                created_at=log.created_at.isoformat(),
            )
            for log in logs
        ]
    except ProgrammingError as e:
        logger.error(f"Database schema error listing audit logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        logger.error(f"Database connection error listing audit logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        logger.exception(f"Database error listing audit logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list audit logs",
        )
    except Exception as e:
        logger.exception(f"Unexpected error listing audit logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )

