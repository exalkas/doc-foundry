"""Projects router endpoints."""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
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
)
from app.database import get_db
from app.models.project import Project

logger = logging.getLogger(__name__)

router = APIRouter()


class ProjectResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: str | None
    created_by_user_id: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ProjectCreateRequest(BaseModel):
    name: str
    description: str | None = None


class ProjectUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class PaginatedProjectsResponse(BaseModel):
    projects: List[ProjectResponse]
    pagination: dict


@router.get("", response_model=PaginatedProjectsResponse)
async def list_projects(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by name or description"),
    sort_by: str = Query("created_at", description="Sort field (name, created_at, updated_at)"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
) -> PaginatedProjectsResponse:
    """List projects for the current workspace with pagination and filtering."""
    logger.info(f"Listing projects for workspace: {current_workspace.id}, page={page}, page_size={page_size}")
    
    try:
        # Build base query
        base_query = select(Project).where(Project.workspace_id == current_workspace.id)
        
        # Apply search filter
        if search:
            search_filter = or_(
                Project.name.ilike(f"%{search}%"),
                Project.description.ilike(f"%{search}%")
            )
            base_query = base_query.where(search_filter)
        
        # Get total count
        count_query = select(func.count(Project.id)).where(Project.workspace_id == current_workspace.id)
        if search:
            count_query = count_query.where(search_filter)
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Build query for results
        query = base_query
        
        # Apply sorting
        sort_column = getattr(Project, sort_by, Project.created_at)
        if sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        result = await db.execute(query)
        projects = result.scalars().all()
        
        # Calculate pagination metadata
        total_pages = (total + page_size - 1) // page_size if total > 0 else 1
        
        return PaginatedProjectsResponse(
            projects=[
                ProjectResponse(
                    id=str(p.id),
                    workspace_id=str(p.workspace_id),
                    name=p.name,
                    description=p.description,
                    created_by_user_id=str(p.created_by_user_id),
                    created_at=p.created_at.isoformat(),
                    updated_at=p.updated_at.isoformat(),
                )
                for p in projects
            ],
            pagination={
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
            }
        )
    except ProgrammingError as e:
        logger.error(f"Database schema error listing projects: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        logger.error(f"Database connection error listing projects: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        logger.exception(f"Database error listing projects: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list projects",
        )
    except Exception as e:
        logger.exception(f"Unexpected error listing projects: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    request: ProjectCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_user = Depends(get_current_user),
    current_member = Depends(get_current_workspace_member),
) -> ProjectResponse:
    """Create a new project."""
    logger.info(f"Creating project '{request.name}' in workspace: {current_workspace.id}")
    
    try:
        project = Project(
            workspace_id=current_workspace.id,
            name=request.name,
            description=request.description,
            created_by_user_id=current_user.id,
        )
        
        db.add(project)
        await db.commit()
        await db.refresh(project)
        
        logger.info(f"Project created successfully: {project.id}")
        return ProjectResponse(
            id=str(project.id),
            workspace_id=str(project.workspace_id),
            name=project.name,
            description=project.description,
            created_by_user_id=str(project.created_by_user_id),
            created_at=project.created_at.isoformat(),
            updated_at=project.updated_at.isoformat(),
        )
    except IntegrityError as e:
        await db.rollback()
        logger.warning(f"Integrity error creating project: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid project data",
        )
    except ProgrammingError as e:
        await db.rollback()
        logger.error(f"Database schema error creating project: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        await db.rollback()
        logger.error(f"Database connection error creating project: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        await db.rollback()
        logger.exception(f"Database error creating project: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create project",
        )
    except Exception as e:
        await db.rollback()
        logger.exception(f"Unexpected error creating project: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
) -> ProjectResponse:
    """Get a project by ID."""
    logger.info(f"Getting project: {project_id}")
    
    try:
        result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.workspace_id == current_workspace.id,
            )
        )
        project = result.scalar_one_or_none()
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )
        
        return ProjectResponse(
            id=str(project.id),
            workspace_id=str(project.workspace_id),
            name=project.name,
            description=project.description,
            created_by_user_id=str(project.created_by_user_id),
            created_at=project.created_at.isoformat(),
            updated_at=project.updated_at.isoformat(),
        )
    except HTTPException:
        raise
    except ProgrammingError as e:
        logger.error(f"Database schema error getting project: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        logger.error(f"Database connection error getting project: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        logger.exception(f"Database error getting project: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve project",
        )
    except Exception as e:
        logger.exception(f"Unexpected error getting project: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    request: ProjectUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
) -> ProjectResponse:
    """Update a project."""
    logger.info(f"Updating project: {project_id}")
    
    try:
        result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.workspace_id == current_workspace.id,
            )
        )
        project = result.scalar_one_or_none()
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )
        
        if request.name is not None:
            project.name = request.name
        if request.description is not None:
            project.description = request.description
        
        await db.commit()
        await db.refresh(project)
        
        logger.info(f"Project updated successfully: {project.id}")
        return ProjectResponse(
            id=str(project.id),
            workspace_id=str(project.workspace_id),
            name=project.name,
            description=project.description,
            created_by_user_id=str(project.created_by_user_id),
            created_at=project.created_at.isoformat(),
            updated_at=project.updated_at.isoformat(),
        )
    except HTTPException:
        raise
    except IntegrityError as e:
        await db.rollback()
        logger.warning(f"Integrity error updating project: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid project data",
        )
    except ProgrammingError as e:
        await db.rollback()
        logger.error(f"Database schema error updating project: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        await db.rollback()
        logger.error(f"Database connection error updating project: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        await db.rollback()
        logger.exception(f"Database error updating project: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update project",
        )
    except Exception as e:
        await db.rollback()
        logger.exception(f"Unexpected error updating project: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
) -> None:
    """Delete a project."""
    logger.info(f"Deleting project: {project_id}")
    
    try:
        result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.workspace_id == current_workspace.id,
            )
        )
        project = result.scalar_one_or_none()
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )
        
        await db.delete(project)
        await db.commit()
        
        logger.info(f"Project deleted successfully: {project_id}")
    except HTTPException:
        raise
    except ProgrammingError as e:
        await db.rollback()
        logger.error(f"Database schema error deleting project: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        await db.rollback()
        logger.error(f"Database connection error deleting project: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        await db.rollback()
        logger.exception(f"Database error deleting project: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete project",
        )
    except Exception as e:
        await db.rollback()
        logger.exception(f"Unexpected error deleting project: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )

