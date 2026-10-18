"""Template library router endpoints."""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
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
from app.models.subscription import Subscription, SubscriptionPlanEnum, SubscriptionStatusEnum
from app.models.template import Template
from app.models.template_library import TemplateLibrary, TemplateCategoryEnum
from app.services.authz_service import AuthzService
from app.services.logging_service import get_logger
from app.services.plan_service import PlanService
from app.services.template_library_service import TemplateLibraryService
from app.services.template_service import TemplateService

logger = get_logger(__name__)

router = APIRouter()


class LibraryTemplateResponse(BaseModel):
    id: str
    name: str
    description: str | None
    category: str
    document_type: str | None
    field_schema: Dict[str, Any]
    default_export_format: str
    preview_image_url: str | None
    tags: List[str] | None
    usage_count: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ImportLibraryTemplateRequest(BaseModel):
    name: str | None = None
    project_id: UUID | None = None


class ImportLibraryTemplateResponse(BaseModel):
    id: str
    workspace_id: str
    project_id: str | None
    name: str
    description: str | None
    document_type: str | None
    library_template_id: str | None
    created_at: str

    class Config:
        from_attributes = True


class CategoriesResponse(BaseModel):
    categories: Dict[str, int]


async def get_plan_tier(db: AsyncSession, workspace_id: UUID) -> str:
    """Get plan tier for workspace."""
    plan_mapping = {
        SubscriptionPlanEnum.STARTER: "starter",
        SubscriptionPlanEnum.PRO: "pro",
    }
    
    result = await db.execute(
        select(Subscription)
        .where(
            Subscription.workspace_id == workspace_id,
            Subscription.status.in_([SubscriptionStatusEnum.ACTIVE, SubscriptionStatusEnum.TRIALING]),
        )
        .order_by(Subscription.created_at.desc())
    )
    subscription = result.scalar_one_or_none()
    
    if subscription:
        return plan_mapping.get(subscription.plan_id, "free")
    return "free"


@router.get("", response_model=List[LibraryTemplateResponse])
async def list_library_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search by name or description"),
    db: AsyncSession = Depends(get_db),
) -> List[LibraryTemplateResponse]:
    """List all active library templates with optional filtering."""
    logger.info(f"Listing library templates: category={category}, search={search}")
    
    try:
        template_library_service = TemplateLibraryService()
        
        # Parse category enum if provided
        category_enum = None
        if category:
            try:
                category_enum = TemplateCategoryEnum(category)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid category: {category}. Must be one of: {', '.join([c.value for c in TemplateCategoryEnum])}",
                )
        
        library_templates = await template_library_service.get_library_templates(
            db,
            category=category_enum,
            search=search,
            is_active=True,
        )
        
        return [
            LibraryTemplateResponse(
                id=str(t.id),
                name=t.name,
                description=t.description,
                category=t.category.value,
                document_type=t.document_type,
                field_schema=t.field_schema,
                default_export_format=t.default_export_format.value,
                preview_image_url=t.preview_image_url,
                tags=t.tags,
                usage_count=t.usage_count,
                created_at=t.created_at.isoformat(),
                updated_at=t.updated_at.isoformat(),
            )
            for t in library_templates
        ]
    except HTTPException:
        raise
    except ProgrammingError as e:
        logger.error(f"Database schema error listing library templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        logger.error(f"Database connection error listing library templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        logger.error(f"Database error listing library templates: {e}", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list library templates",
        )
    except Exception as e:
        logger.error(f"Unexpected error listing library templates: {e}", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.get("/{library_template_id}", response_model=LibraryTemplateResponse)
async def get_library_template(
    library_template_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> LibraryTemplateResponse:
    """Get a library template by ID."""
    logger.info(f"Getting library template: {library_template_id}")
    
    try:
        template_library_service = TemplateLibraryService()
        library_template = await template_library_service.get_library_template_by_id(
            db, library_template_id
        )
        
        if not library_template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Library template not found",
            )
        
        return LibraryTemplateResponse(
            id=str(library_template.id),
            name=library_template.name,
            description=library_template.description,
            category=library_template.category.value,
            document_type=library_template.document_type,
            field_schema=library_template.field_schema,
            default_export_format=library_template.default_export_format.value,
            preview_image_url=library_template.preview_image_url,
            tags=library_template.tags,
            usage_count=library_template.usage_count,
            created_at=library_template.created_at.isoformat(),
            updated_at=library_template.updated_at.isoformat(),
        )
    except HTTPException:
        raise
    except ProgrammingError as e:
        logger.error(f"Database schema error getting library template: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        logger.error(f"Database connection error getting library template: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        logger.error(f"Database error getting library template: {e}", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve library template",
        )
    except Exception as e:
        logger.error(f"Unexpected error getting library template: {e}", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.post("/{library_template_id}/import", response_model=ImportLibraryTemplateResponse, status_code=status.HTTP_201_CREATED)
async def import_library_template(
    library_template_id: UUID,
    request: ImportLibraryTemplateRequest,
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_user = Depends(get_current_user),
    current_member = Depends(get_current_workspace_member),
) -> ImportLibraryTemplateResponse:
    """Import a library template into the current workspace."""
    logger.info(
        f"Importing library template: {library_template_id}, workspace={current_workspace.id}"
    )
    
    # Authorization check
    authz_service = AuthzService()
    if not authz_service.can_perform_action(current_member.role, "create_template"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to import templates",
        )
    
    # Get plan tier and check template limit
    plan_tier = await get_plan_tier(db, current_workspace.id)
    plan_service = PlanService()
    
    # Check template count limit
    template_count_result = await db.execute(
        select(func.count(Template.id)).where(
            Template.workspace_id == current_workspace.id
        )
    )
    template_count = template_count_result.scalar_one()
    
    is_valid, error_msg = plan_service.check_template_limit(plan_tier, template_count)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_msg,
        )
    
    # Validate project if provided
    if request.project_id:
        project_result = await db.execute(
            select(Project).where(
                Project.id == request.project_id,
                Project.workspace_id == current_workspace.id,
            )
        )
        project = project_result.scalar_one_or_none()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )
    
    try:
        template_library_service = TemplateLibraryService()
        
        template = await template_library_service.import_library_template(
            db,
            library_template_id,
            current_workspace.id,
            current_user.id,
            name_override=request.name,
            project_id=request.project_id,
        )
        
        await db.commit()
        
        logger.info(f"Library template imported successfully: template_id={template.id}")
        
        return ImportLibraryTemplateResponse(
            id=str(template.id),
            workspace_id=str(template.workspace_id),
            project_id=str(template.project_id) if template.project_id else None,
            name=template.name,
            description=template.description,
            document_type=template.document_type,
            library_template_id=str(template.library_template_id) if template.library_template_id else None,
            created_at=template.created_at.isoformat(),
        )
    except ValueError as e:
        await db.rollback()
        logger.warning(f"Value error importing library template: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except IntegrityError as e:
        await db.rollback()
        logger.warning(f"Integrity error importing library template: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid template data",
        )
    except ProgrammingError as e:
        await db.rollback()
        logger.error(f"Database schema error importing library template: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        await db.rollback()
        logger.error(f"Database connection error importing library template: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Database error importing library template: {e}", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to import library template",
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Unexpected error importing library template: {e}", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.get("/categories", response_model=CategoriesResponse)
async def get_categories(
    db: AsyncSession = Depends(get_db),
) -> CategoriesResponse:
    """Get category counts for library templates."""
    logger.info("Getting library template categories")
    
    try:
        template_library_service = TemplateLibraryService()
        categories = await template_library_service.get_categories(db)
        
        return CategoriesResponse(categories=categories)
    except ProgrammingError as e:
        logger.error(f"Database schema error getting categories: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        logger.error(f"Database connection error getting categories: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        logger.error(f"Database error getting categories: {e}", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve categories",
        )
    except Exception as e:
        logger.error(f"Unexpected error getting categories: {e}", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )

