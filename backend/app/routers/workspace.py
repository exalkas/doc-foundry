"""Workspace router endpoints."""

import io
import logging
import os
import uuid
from pathlib import Path
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from PIL import Image
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func
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
    require_workspace_role,
)
from app.config import settings
from app.core.storage import StorageService
from app.database import get_db
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceStatus
from app.models.workspacemember import WorkspaceMember, WorkspaceMemberRole, WorkspaceMemberStatus
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

router = APIRouter()


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    primary_color: str | None
    logo_url: str | None
    custom_domain: str | None
    status: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class CreateWorkspaceRequest(BaseModel):
    name: str
    primary_color: str | None = None


class WorkspaceUpdateRequest(BaseModel):
    name: str | None = None
    custom_domain: str | None = None
    primary_color: str | None = None


class WorkspaceMemberResponse(BaseModel):
    id: str
    user_id: str
    workspace_id: str
    role: str
    status: str
    invited_at: str
    joined_at: str | None
    user: dict  # User info

    class Config:
        from_attributes = True


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: str


class UpdateMemberRoleRequest(BaseModel):
    role: str


class OnboardingStatusResponse(BaseModel):
    completed: bool


class CompleteOnboardingResponse(BaseModel):
    success: bool
    message: str


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    request: CreateWorkspaceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkspaceResponse:
    """Create a new workspace for the current user."""
    logger.info(f"Creating workspace '{request.name}' for user: {current_user.id}")
    
    try:
        # Validate primary color if provided
        if request.primary_color:
            import re
            color_pattern = re.compile(r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$')
            if not color_pattern.match(request.primary_color):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid color format. Must be a valid hex color (e.g., #2563EB)",
                )
        
        # Create workspace
        workspace = Workspace(
            name=request.name,
            owner_user_id=current_user.id,
            status=WorkspaceStatus.TRIAL,
            primary_color=request.primary_color,
        )
        db.add(workspace)
        await db.flush()  # Flush to get workspace.id
        
        # Create workspace membership
        member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=current_user.id,
            role=WorkspaceMemberRole.OWNER,
            status=WorkspaceMemberStatus.ACTIVE,
            joined_at=datetime.now(timezone.utc),
        )
        db.add(member)
        await db.commit()
        await db.refresh(workspace)
        
        logger.info(f"Workspace created successfully: {workspace.id}")
        return WorkspaceResponse(
            id=str(workspace.id),
            name=workspace.name,
            primary_color=workspace.primary_color,
            logo_url=workspace.logo_url,
            custom_domain=workspace.custom_domain,
            status=workspace.status.value,
            created_at=workspace.created_at.isoformat(),
            updated_at=workspace.updated_at.isoformat(),
        )
    except IntegrityError as e:
        await db.rollback()
        logger.warning(f"Integrity error creating workspace: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workspace data",
        )
    except SQLAlchemyError as e:
        await db.rollback()
        logger.exception(f"Database error creating workspace: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create workspace",
        )
    except Exception as e:
        await db.rollback()
        logger.exception(f"Unexpected error creating workspace: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.get("", response_model=List[WorkspaceResponse])
async def list_workspaces(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[WorkspaceResponse]:
    """List all workspaces the current user belongs to."""
    logger.info(f"Listing workspaces for user: {current_user.id}")
    
    try:
        # Get all workspaces user belongs to via WorkspaceMember
        result = await db.execute(
            select(Workspace)
            .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
            .where(WorkspaceMember.user_id == current_user.id)
            .order_by(Workspace.created_at.desc())
        )
        workspaces = result.scalars().all()
        
        return [
            WorkspaceResponse(
                id=str(ws.id),
                name=ws.name,
                primary_color=ws.primary_color,
                logo_url=ws.logo_url,
                custom_domain=ws.custom_domain,
                status=ws.status.value,
                created_at=ws.created_at.isoformat(),
                updated_at=ws.updated_at.isoformat(),
            )
            for ws in workspaces
        ]
    except Exception as e:
        logger.exception(f"Error listing workspaces: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list workspaces",
        )


@router.get("/current", response_model=WorkspaceResponse)
async def get_current_workspace_endpoint(
    current_workspace: Workspace = Depends(get_current_workspace),
) -> WorkspaceResponse:
    """Get the current workspace details."""
    logger.info(f"Getting current workspace: {current_workspace.id}")
    try:
        return WorkspaceResponse(
            id=str(current_workspace.id),
            name=current_workspace.name,
            primary_color=current_workspace.primary_color,
            logo_url=current_workspace.logo_url,
            custom_domain=current_workspace.custom_domain,
            status=current_workspace.status.value,
            created_at=current_workspace.created_at.isoformat(),
            updated_at=current_workspace.updated_at.isoformat(),
        )
    except Exception as e:
        logger.exception(f"Error getting current workspace: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve workspace",
        )


@router.patch("/current", response_model=WorkspaceResponse)
async def update_current_workspace(
    request: WorkspaceUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_workspace: Workspace = Depends(get_current_workspace),
    current_member: WorkspaceMember = Depends(require_workspace_role("owner")),
) -> WorkspaceResponse:
    """Update the current workspace (owner only)."""
    logger.info(f"Updating workspace: {current_workspace.id}")
    
    try:
        if request.name is not None:
            current_workspace.name = request.name
        if request.custom_domain is not None:
            current_workspace.custom_domain = request.custom_domain
        if request.primary_color is not None:
            # Validate hex color format
            import re
            color_pattern = re.compile(r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$')
            if not color_pattern.match(request.primary_color):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid color format. Must be a valid hex color (e.g., #2563EB)",
                )
            current_workspace.primary_color = request.primary_color
        
        await db.commit()
        await db.refresh(current_workspace)
        
        logger.info(f"Workspace updated successfully: {current_workspace.id}")
        return WorkspaceResponse(
            id=str(current_workspace.id),
            name=current_workspace.name,
            primary_color=current_workspace.primary_color,
            logo_url=current_workspace.logo_url,
            custom_domain=current_workspace.custom_domain,
            status=current_workspace.status.value,
            created_at=current_workspace.created_at.isoformat(),
            updated_at=current_workspace.updated_at.isoformat(),
        )
    except IntegrityError as e:
        await db.rollback()
        logger.warning(f"Integrity error updating workspace: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workspace data",
        )
    except ProgrammingError as e:
        await db.rollback()
        logger.error(f"Database schema error updating workspace: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        await db.rollback()
        logger.error(f"Database connection error updating workspace: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        await db.rollback()
        logger.exception(f"Database error updating workspace: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update workspace",
        )
    except Exception as e:
        await db.rollback()
        logger.exception(f"Unexpected error updating workspace: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.get("/current/members", response_model=List[WorkspaceMemberResponse])
async def list_workspace_members(
    db: AsyncSession = Depends(get_db),
    current_workspace: Workspace = Depends(get_current_workspace),
    current_member: WorkspaceMember = Depends(get_current_workspace_member),
) -> List[WorkspaceMemberResponse]:
    """List all members of the current workspace."""
    logger.info(f"Listing members for workspace: {current_workspace.id}")
    
    try:
        result = await db.execute(
            select(WorkspaceMember)
            .where(WorkspaceMember.workspace_id == current_workspace.id)
            .order_by(WorkspaceMember.created_at)
        )
        members = result.scalars().all()
        
        # Load user relationships
        member_responses = []
        for member in members:
            # Ensure user is loaded
            if not hasattr(member, 'user') or member.user is None:
                user_result = await db.execute(
                    select(User).where(User.id == member.user_id)
                )
                member.user = user_result.scalar_one_or_none()
            
            if member.user:
                member_responses.append(WorkspaceMemberResponse(
                    id=str(member.id),
                    user_id=str(member.user_id),
                    workspace_id=str(member.workspace_id),
                    role=member.role.value,
                    status=member.status.value,
                    invited_at=member.invited_at.isoformat(),
                    joined_at=member.joined_at.isoformat() if member.joined_at else None,
                    user={
                        "id": str(member.user.id),
                        "email": member.user.email,
                        "full_name": member.user.full_name,
                    },
                ))
        
        logger.info(f"Found {len(member_responses)} members")
        return member_responses
    except ProgrammingError as e:
        logger.error(f"Database schema error listing members: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        logger.error(f"Database connection error listing members: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        logger.exception(f"Database error listing members: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list members",
        )
    except Exception as e:
        logger.exception(f"Unexpected error listing members: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.post("/current/invite", response_model=WorkspaceMemberResponse, status_code=status.HTTP_201_CREATED)
async def invite_member(
    request: InviteMemberRequest,
    db: AsyncSession = Depends(get_db),
    current_workspace: Workspace = Depends(get_current_workspace),
    current_member: WorkspaceMember = Depends(require_workspace_role("owner", "member")),
) -> WorkspaceMemberResponse:
    """Invite a user to the workspace by email."""
    logger.info(f"Inviting {request.email} to workspace: {current_workspace.id}")
    
    try:
        # Find user by email
        user_result = await db.execute(
            select(User).where(User.email == request.email)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        
        # Check if already a member
        existing_result = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == current_workspace.id,
                WorkspaceMember.user_id == user.id,
            )
        )
        existing = existing_result.scalar_one_or_none()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already a member of this workspace",
            )
        
        # Validate role
        try:
            role = WorkspaceMemberRole(request.role)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {request.role}",
            )
        
        # Create membership
        member = WorkspaceMember(
            workspace_id=current_workspace.id,
            user_id=user.id,
            role=role,
            status=WorkspaceMemberStatus.ACTIVE,
        )
        
        db.add(member)
        await db.commit()
        await db.refresh(member)
        
        logger.info(f"Member invited successfully: {member.id}")
        return WorkspaceMemberResponse(
            id=str(member.id),
            user_id=str(member.user_id),
            workspace_id=str(member.workspace_id),
            role=member.role.value,
            status=member.status.value,
            invited_at=member.invited_at.isoformat(),
            joined_at=member.joined_at.isoformat() if member.joined_at else None,
            user={
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
            },
        )
    except HTTPException:
        raise
    except IntegrityError as e:
        await db.rollback()
        logger.warning(f"Integrity error inviting member: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid member data",
        )
    except ProgrammingError as e:
        await db.rollback()
        logger.error(f"Database schema error inviting member: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        await db.rollback()
        logger.error(f"Database connection error inviting member: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        await db.rollback()
        logger.exception(f"Database error inviting member: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to invite member",
        )
    except Exception as e:
        await db.rollback()
        logger.exception(f"Unexpected error inviting member: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.patch("/current/members/{member_id}", response_model=WorkspaceMemberResponse)
async def update_member_role(
    member_id: UUID,
    request: UpdateMemberRoleRequest,
    db: AsyncSession = Depends(get_db),
    current_workspace: Workspace = Depends(get_current_workspace),
    current_member: WorkspaceMember = Depends(require_workspace_role("owner")),
) -> WorkspaceMemberResponse:
    """Update a member's role (owner only)."""
    logger.info(f"Updating member {member_id} role in workspace: {current_workspace.id}")
    
    try:
        # Find member
        result = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.id == member_id,
                WorkspaceMember.workspace_id == current_workspace.id,
            )
        )
        member = result.scalar_one_or_none()
        
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found",
            )
        
        # Validate role
        try:
            new_role = WorkspaceMemberRole(request.role)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {request.role}",
            )
        
        member.role = new_role
        await db.commit()
        await db.refresh(member)
        
        # Load user
        user_result = await db.execute(
            select(User).where(User.id == member.user_id)
        )
        user = user_result.scalar_one()
        
        logger.info(f"Member role updated successfully: {member.id}")
        return WorkspaceMemberResponse(
            id=str(member.id),
            user_id=str(member.user_id),
            workspace_id=str(member.workspace_id),
            role=member.role.value,
            status=member.status.value,
            invited_at=member.invited_at.isoformat(),
            joined_at=member.joined_at.isoformat() if member.joined_at else None,
            user={
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
            },
        )
    except HTTPException:
        raise
    except ProgrammingError as e:
        await db.rollback()
        logger.error(f"Database schema error updating member: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        await db.rollback()
        logger.error(f"Database connection error updating member: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        await db.rollback()
        logger.exception(f"Database error updating member: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update member",
        )
    except Exception as e:
        await db.rollback()
        logger.exception(f"Unexpected error updating member: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.delete("/current/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    member_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_workspace: Workspace = Depends(get_current_workspace),
    current_member: WorkspaceMember = Depends(require_workspace_role("owner")),
) -> None:
    """Remove a member from the workspace (owner only)."""
    logger.info(f"Removing member {member_id} from workspace: {current_workspace.id}")
    
    try:
        # Find member
        result = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.id == member_id,
                WorkspaceMember.workspace_id == current_workspace.id,
            )
        )
        member = result.scalar_one_or_none()
        
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found",
            )
        
        # Prevent removing the workspace owner
        if member.role == WorkspaceMemberRole.OWNER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove workspace owner",
            )
        
        await db.delete(member)
        await db.commit()
        
        logger.info(f"Member removed successfully: {member_id}")
    except HTTPException:
        raise
    except ProgrammingError as e:
        await db.rollback()
        logger.error(f"Database schema error removing member: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        await db.rollback()
        logger.error(f"Database connection error removing member: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        await db.rollback()
        logger.exception(f"Database error removing member: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove member",
        )
    except Exception as e:
        await db.rollback()
        logger.exception(f"Unexpected error removing member: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.get("/onboarding-status", response_model=OnboardingStatusResponse)
async def get_onboarding_status(
    current_workspace: Workspace = Depends(get_current_workspace),
    current_member: WorkspaceMember = Depends(get_current_workspace_member),
) -> OnboardingStatusResponse:
    """Get the onboarding completion status for the current workspace."""
    logger.info(f"Getting onboarding status for workspace: {current_workspace.id}")
    try:
        return OnboardingStatusResponse(
            completed=current_workspace.onboarding_completed
        )
    except Exception as e:
        logger.exception(f"Error getting onboarding status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve onboarding status",
        )


@router.post("/complete-onboarding", response_model=CompleteOnboardingResponse)
async def complete_onboarding(
    db: AsyncSession = Depends(get_db),
    current_workspace: Workspace = Depends(get_current_workspace),
    current_member: WorkspaceMember = Depends(require_workspace_role("owner", "member")),
) -> CompleteOnboardingResponse:
    """Mark onboarding as completed for the current workspace."""
    logger.info(f"Completing onboarding for workspace: {current_workspace.id}")
    
    try:
        current_workspace.onboarding_completed = True
        await db.commit()
        await db.refresh(current_workspace)
        
        logger.info(f"Onboarding completed successfully for workspace: {current_workspace.id}")
        return CompleteOnboardingResponse(
            success=True,
            message="Onboarding completed successfully"
        )
    except SQLAlchemyError as e:
        await db.rollback()
        logger.exception(f"Database error completing onboarding: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete onboarding",
        )
    except Exception as e:
        await db.rollback()
        logger.exception(f"Unexpected error completing onboarding: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    workspace_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_member: WorkspaceMember = Depends(require_workspace_role("owner")),
) -> None:
    """Delete a workspace (owner only)."""
    logger.info(f"Deleting workspace {workspace_id} by user {current_user.id}")
    
    try:
        # Find workspace
        workspace_result = await db.execute(
            select(Workspace).where(Workspace.id == workspace_id)
        )
        workspace = workspace_result.scalar_one_or_none()
        
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )
        
        # Verify user is owner
        if workspace.owner_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only workspace owner can delete the workspace",
            )
        
        # Check if workspace has many documents (safety check)
        from app.models.document import Document
        doc_count_result = await db.execute(
            select(func.count(Document.id)).where(
                Document.workspace_id == workspace_id
            )
        )
        doc_count = doc_count_result.scalar_one()
        
        if doc_count > 100:
            logger.warning(
                f"Workspace {workspace_id} has {doc_count} documents. "
                "Consider archiving instead of deleting."
            )
            # Still allow deletion, but log warning
        
        # Delete workspace (cascade will handle related records)
        await db.delete(workspace)
        await db.commit()
        
        logger.info(f"Workspace {workspace_id} deleted successfully")
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await db.rollback()
        logger.exception(f"Database error deleting workspace: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete workspace",
        )
    except Exception as e:
        await db.rollback()
        logger.exception(f"Unexpected error deleting workspace: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.post("/current/upload-logo", response_model=WorkspaceResponse)
async def upload_logo(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_workspace: Workspace = Depends(get_current_workspace),
    current_member: WorkspaceMember = Depends(require_workspace_role("owner")),
) -> WorkspaceResponse:
    """Upload a logo for the current workspace (owner only)."""
    logger.info(f"Uploading logo for workspace: {current_workspace.id}")
    
    # Validate file type
    allowed_types = {"image/png", "image/jpeg", "image/jpg", "image/svg+xml", "image/gif", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)}",
        )
    
    # Validate file size (max 5MB)
    max_size = 5 * 1024 * 1024  # 5MB
    file_content = await file.read()
    if len(file_content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds maximum allowed size of 5MB",
        )
    
    try:
        # Validate image if it's not SVG
        if file.content_type != "image/svg+xml":
            try:
                image = Image.open(io.BytesIO(file_content))
                image.verify()
                # Reset file pointer for saving
                file.file.seek(0)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid image file: {str(e)}",
                )
        
        # Generate unique filename
        file_ext = Path(file.filename or "logo").suffix or ".png"
        logo_filename = f"logo_{current_workspace.id}_{uuid.uuid4().hex[:8]}{file_ext}"
        
        # Store logo in workspace-specific directory
        storage = StorageService(settings.STORAGE_ROOT)
        logo_path = f"workspaces/{current_workspace.id}/logos/{logo_filename}"
        
        # Save file
        await storage.upload(logo_path, file_content)
        
        # Generate URL (for local storage, use a path that can be served)
        # In production, this would be a CDN URL or public storage URL
        logo_url = f"/api/storage/{logo_path}"
        
        # Delete old logo if exists
        if current_workspace.logo_url:
            try:
                old_path = current_workspace.logo_url.replace("/api/storage/", "")
                await storage.delete(old_path)
            except Exception as e:
                logger.warning(f"Failed to delete old logo: {e}")
        
        # Update workspace
        current_workspace.logo_url = logo_url
        await db.commit()
        await db.refresh(current_workspace)
        
        logger.info(f"Logo uploaded successfully for workspace: {current_workspace.id}")
        return WorkspaceResponse(
            id=str(current_workspace.id),
            name=current_workspace.name,
            primary_color=current_workspace.primary_color,
            logo_url=current_workspace.logo_url,
            custom_domain=current_workspace.custom_domain,
            status=current_workspace.status.value,
            created_at=current_workspace.created_at.isoformat(),
            updated_at=current_workspace.updated_at.isoformat(),
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.exception(f"Error uploading logo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload logo",
        )

