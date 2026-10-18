"""Templates router endpoints."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
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
from app.models.subscription import Subscription, SubscriptionPlanEnum, SubscriptionStatusEnum
from app.models.template import Template, ExportFormatEnum
from app.models.document import Document
from app.models.extractionresult import ExtractionResult
from app.services.authz_service import AuthzService
from app.services.job_queue_service import JobQueueService
from app.services.logging_service import get_logger, set_correlation_id
from app.services.plan_service import PlanService
from app.services.template_service import TemplateService, TemplateValidationError
from app.services.extraction_service import ExtractionService

logger = get_logger(__name__)

router = APIRouter()


class TemplateResponse(BaseModel):
    id: str
    workspace_id: str
    project_id: str | None
    name: str
    description: str | None
    document_type: str | None
    field_schema: Dict[str, Any]
    default_export_format: str
    created_by_user_id: str
    last_run_at: str | None
    success_count: int
    failure_count: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class TemplateCreateRequest(BaseModel):
    name: str
    description: str | None = None
    document_type: str | None = None
    field_schema: Dict[str, Any]
    default_export_format: str
    project_id: UUID | None = None


class TemplateUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    document_type: str | None = None
    field_schema: Dict[str, Any] | None = None
    default_export_format: str | None = None
    project_id: UUID | None = None


class TemplateTestRequest(BaseModel):
    test_document_id: UUID


class TemplateTestResponse(BaseModel):
    message: str
    template_id: str
    document_id: str
    job_id: str | None = None


class PaginatedTemplatesResponse(BaseModel):
    templates: List[TemplateResponse]
    pagination: dict


async def get_plan_tier(db: AsyncSession, user_id: UUID) -> str:
    """Get plan tier for user (subscriptions are per-user, not per-workspace)."""
    plan_mapping = {
        SubscriptionPlanEnum.STARTER: "starter",
        SubscriptionPlanEnum.PRO: "pro",
    }
    
    result = await db.execute(
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.status.in_([SubscriptionStatusEnum.ACTIVE, SubscriptionStatusEnum.TRIALING]),
        )
        .order_by(Subscription.created_at.desc())
    )
    subscription = result.scalar_one_or_none()
    
    if subscription:
        return plan_mapping.get(subscription.plan_id, "free")
    return "free"


@router.get("", response_model=PaginatedTemplatesResponse)
async def list_templates(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    project_id: Optional[UUID] = Query(None, description="Filter by project ID"),
    search: Optional[str] = Query(None, description="Search by name or description"),
    sort_by: str = Query("created_at", description="Sort field (name, created_at, updated_at, document_type)"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
) -> PaginatedTemplatesResponse:
    """List templates for the current workspace with pagination and filtering."""
    logger.info(f"Listing templates for workspace: {current_workspace.id}, page={page}, page_size={page_size}")
    
    try:
        # Build base query
        base_query = select(Template).where(Template.workspace_id == current_workspace.id)
        
        # Apply project filter
        if project_id:
            base_query = base_query.where(Template.project_id == project_id)
        
        # Apply search filter
        if search:
            search_filter = or_(
                Template.name.ilike(f"%{search}%"),
                Template.description.ilike(f"%{search}%")
            )
            base_query = base_query.where(search_filter)
        
        # Get total count
        count_query = select(func.count(Template.id)).where(Template.workspace_id == current_workspace.id)
        if project_id:
            count_query = count_query.where(Template.project_id == project_id)
        if search:
            count_query = count_query.where(search_filter)
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Build query for results
        query = base_query
        
        # Apply sorting
        sort_column = getattr(Template, sort_by, Template.created_at)
        if sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        result = await db.execute(query)
        templates = result.scalars().all()
        
        # Calculate pagination metadata
        total_pages = (total + page_size - 1) // page_size if total > 0 else 1
        
        return PaginatedTemplatesResponse(
            templates=[
                TemplateResponse(
                    id=str(t.id),
                    workspace_id=str(t.workspace_id),
                    project_id=str(t.project_id) if t.project_id else None,
                    name=t.name,
                    description=t.description,
                    document_type=t.document_type,
                    field_schema=t.field_schema,
                    default_export_format=t.default_export_format.value,
                    created_by_user_id=str(t.created_by_user_id),
                    last_run_at=t.last_run_at.isoformat() if t.last_run_at else None,
                    success_count=t.success_count,
                    failure_count=t.failure_count,
                    created_at=t.created_at.isoformat(),
                    updated_at=t.updated_at.isoformat(),
                )
                for t in templates
            ],
            pagination={
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
            }
        )
    except ProgrammingError as e:
        logger.error(f"Database schema error listing templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        logger.error(f"Database connection error listing templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        logger.error(f"Database error listing templates: {e}", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list templates",
        )
    except Exception as e:
        logger.error(f"Unexpected error listing templates: {e}", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    request: TemplateCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_user = Depends(get_current_user),
    current_member = Depends(get_current_workspace_member),
) -> TemplateResponse:
    """Create a new template with validation and plan limit checks."""
    correlation_id = set_correlation_id()
    logger.info(
        "Creating template",
        extra={
            "name": request.name,
            "workspace_id": str(current_workspace.id),
            "correlation_id": correlation_id,
        },
    )
    
    # Authorization check
    authz_service = AuthzService()
    if not authz_service.can_perform_action(current_member.role, "create_template"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create templates",
        )
    
    # Get plan tier and check template limit (subscriptions are per-user)
    plan_tier = await get_plan_tier(db, current_user.id)
    plan_service = PlanService()
    template_service = TemplateService()
    
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
    
    try:
        # Validate field schema
        is_valid, errors = template_service.validate_field_schema(request.field_schema)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid field schema: {', '.join(errors)}",
            )
        
        # Validate export format (case-insensitive)
        export_format_str = request.default_export_format.lower()
        try:
            export_format = ExportFormatEnum(export_format_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid export format: {request.default_export_format}. Must be one of: json, csv, excel",
            )
        
        template = Template(
            workspace_id=current_workspace.id,
            project_id=request.project_id,
            name=request.name,
            description=request.description,
            document_type=request.document_type,
            field_schema=request.field_schema,
            default_export_format=export_format,
            created_by_user_id=current_user.id,
        )
        
        db.add(template)
        await db.commit()
        await db.refresh(template)
        
        logger.info(f"Template created successfully: {template.id}")
        return TemplateResponse(
            id=str(template.id),
            workspace_id=str(template.workspace_id),
            project_id=str(template.project_id) if template.project_id else None,
            name=template.name,
            description=template.description,
            document_type=template.document_type,
            field_schema=template.field_schema,
            default_export_format=template.default_export_format.value,
            created_by_user_id=str(template.created_by_user_id),
            last_run_at=template.last_run_at.isoformat() if template.last_run_at else None,
            success_count=template.success_count,
            failure_count=template.failure_count,
            created_at=template.created_at.isoformat(),
            updated_at=template.updated_at.isoformat(),
        )
    except HTTPException:
        raise
    except IntegrityError as e:
        await db.rollback()
        logger.warning(f"Integrity error creating template: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid template data",
        )
    except ProgrammingError as e:
        await db.rollback()
        logger.error(f"Database schema error creating template: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        await db.rollback()
        logger.error(f"Database connection error creating template: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Database error creating template: {e}", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create template",
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Unexpected error creating template: {e}", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
) -> TemplateResponse:
    """Get a template by ID."""
    logger.info(f"Getting template: {template_id}")
    
    try:
        result = await db.execute(
            select(Template).where(
                Template.id == template_id,
                Template.workspace_id == current_workspace.id,
            )
        )
        template = result.scalar_one_or_none()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found",
            )
        
        return TemplateResponse(
            id=str(template.id),
            workspace_id=str(template.workspace_id),
            project_id=str(template.project_id) if template.project_id else None,
            name=template.name,
            description=template.description,
            document_type=template.document_type,
            field_schema=template.field_schema,
            default_export_format=template.default_export_format.value,
            created_by_user_id=str(template.created_by_user_id),
            last_run_at=template.last_run_at.isoformat() if template.last_run_at else None,
            success_count=template.success_count,
            failure_count=template.failure_count,
            created_at=template.created_at.isoformat(),
            updated_at=template.updated_at.isoformat(),
        )
    except HTTPException:
        raise
    except ProgrammingError as e:
        logger.error(f"Database schema error getting template: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        logger.error(f"Database connection error getting template: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        logger.error(f"Database error getting template: {e}", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve template",
        )
    except Exception as e:
        logger.error(f"Unexpected error getting template: {e}", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: UUID,
    request: TemplateUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
) -> TemplateResponse:
    """Update a template with versioning support."""
    logger.info(f"Updating template: {template_id}")
    
    authz_service = AuthzService()
    template_service = TemplateService()
    
    try:
        result = await db.execute(
            select(Template).where(
                Template.id == template_id,
                Template.workspace_id == current_workspace.id,
            )
        )
        template = result.scalar_one_or_none()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found",
            )
        
        # Authorization check
        await authz_service.assert_resource_ownership(
            db, current_member.user_id, current_workspace.id, template.workspace_id
        )
        
        if not authz_service.can_perform_action(current_member.role, "create_template"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to update templates",
            )
        
        # Update project_id if provided
        # Frontend always sends project_id (either UUID or null), so we handle both cases
        # Use model_dump(exclude_unset=True) to check if field was actually set
        request_dict = request.model_dump(exclude_unset=True)
        if 'project_id' in request_dict:
            if request.project_id:
                # Validate project belongs to workspace
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
                template.project_id = request.project_id
            else:
                # Explicitly set to None - unassign template from project
                template.project_id = None
        
        # Update fields
        if request.name is not None:
            template.name = request.name
        if request.description is not None:
            template.description = request.description
        if request.document_type is not None:
            template.document_type = request.document_type
        
        # Validate and update field_schema (creates new version)
        if request.field_schema is not None:
            is_valid, errors = template_service.validate_field_schema(request.field_schema)
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid field schema: {', '.join(errors)}",
                )
            
            # Create new version
            await template_service.create_template_version(
                db, template_id, request.field_schema, current_member.user_id
            )
            template.field_schema = request.field_schema
        
        if request.default_export_format is not None:
            try:
                export_format_str = request.default_export_format.lower()
                template.default_export_format = ExportFormatEnum(export_format_str)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid export format: {request.default_export_format}. Must be one of: json, csv, excel",
                )
        
        await db.commit()
        await db.refresh(template)
        
        logger.info(f"Template updated successfully: {template.id}")
        return TemplateResponse(
            id=str(template.id),
            workspace_id=str(template.workspace_id),
            project_id=str(template.project_id) if template.project_id else None,
            name=template.name,
            description=template.description,
            document_type=template.document_type,
            field_schema=template.field_schema,
            default_export_format=template.default_export_format.value,
            created_by_user_id=str(template.created_by_user_id),
            last_run_at=template.last_run_at.isoformat() if template.last_run_at else None,
            success_count=template.success_count,
            failure_count=template.failure_count,
            created_at=template.created_at.isoformat(),
            updated_at=template.updated_at.isoformat(),
        )
    except HTTPException:
        raise
    except IntegrityError as e:
        await db.rollback()
        logger.warning(f"Integrity error updating template: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid template data",
        )
    except ProgrammingError as e:
        await db.rollback()
        logger.error(f"Database schema error updating template: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        await db.rollback()
        logger.error(f"Database connection error updating template: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Database error updating template: {e}", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update template",
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Unexpected error updating template: {e}", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: UUID,
    archive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
) -> None:
    """Delete or archive a template."""
    logger.info(f"Deleting template: {template_id}, archive={archive}")
    
    authz_service = AuthzService()
    template_service = TemplateService()
    
    try:
        result = await db.execute(
            select(Template).where(
                Template.id == template_id,
                Template.workspace_id == current_workspace.id,
            )
        )
        template = result.scalar_one_or_none()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found",
            )
        
        # Authorization check
        await authz_service.assert_resource_ownership(
            db, current_member.user_id, current_workspace.id, template.workspace_id
        )
        
        if not authz_service.can_perform_action(current_member.role, "delete_template"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to delete templates",
            )
        
        # Check if template can be safely deleted
        can_delete, warnings = await template_service.can_delete_template(db, template_id)
        
        if archive:
            # Archive instead of delete
            await template_service.archive_template(db, template_id)
            await db.commit()
            logger.info(f"Template archived successfully: {template_id}")
        else:
            if not can_delete and warnings:
                # Return warnings but allow deletion
                logger.warning(f"Deleting template with warnings: {warnings}")
            
            await db.delete(template)
            await db.commit()
            logger.info(f"Template deleted successfully: {template_id}")
    except HTTPException:
        raise
    except ProgrammingError as e:
        await db.rollback()
        logger.error(f"Database schema error deleting template: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        await db.rollback()
        logger.error(f"Database connection error deleting template: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Database error deleting template: {e}", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete template",
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Unexpected error deleting template: {e}", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.post("/{template_id}/test", status_code=status.HTTP_202_ACCEPTED, response_model=TemplateTestResponse)
async def test_template(
    template_id: UUID,
    request: TemplateTestRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
) -> TemplateTestResponse:
    """Test a template extraction on a test document."""
    logger.info(f"Testing template {template_id} on document {request.test_document_id}")
    
    authz_service = AuthzService()
    job_queue_service = JobQueueService()
    
    try:
        # Verify template exists and belongs to workspace
        template_result = await db.execute(
            select(Template).where(
                Template.id == template_id,
                Template.workspace_id == current_workspace.id,
            )
        )
        template = template_result.scalar_one_or_none()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found",
            )
        
        # Authorization check
        await authz_service.assert_resource_ownership(
            db, current_member.user_id, current_workspace.id, template.workspace_id
        )
        
        # Verify document exists and belongs to workspace
        from app.models.document import Document
        doc_result = await db.execute(
            select(Document).where(
                Document.id == request.test_document_id,
                Document.workspace_id == current_workspace.id,
            )
        )
        document = doc_result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Test document not found",
            )
        
        # Get plan tier (subscriptions are per-user, not per-workspace)
        plan_tier = await get_plan_tier(db, current_user.id)
        
        # Get subscription for period dates (subscriptions are per-user)
        subscription_result = await db.execute(
            select(Subscription)
            .where(
                Subscription.user_id == current_user.id,
                Subscription.status.in_([SubscriptionStatusEnum.ACTIVE, SubscriptionStatusEnum.TRIALING]),
            )
            .order_by(Subscription.created_at.desc())
        )
        subscription = subscription_result.scalar_one_or_none()
        
        period_start = subscription.current_period_start if subscription else datetime.now(timezone.utc)
        period_end = subscription.current_period_end if subscription else (datetime.now(timezone.utc).replace(day=1) + timedelta(days=32))
        
        # Enqueue extraction job for test document
        job = await job_queue_service.enqueue_extraction_job(
            db,
            document.id,
            current_workspace.id,
            template_id,
            plan_tier,
            period_start,
            period_end,
            check_quota=False,  # Test extractions don't count against quota
            is_test=True,  # Mark as test so document status isn't changed
        )
        
        await db.commit()
        
        logger.info(
            "Test extraction job enqueued",
            extra={
                "template_id": str(template_id),
                "document_id": str(request.test_document_id),
                "job_id": str(job.id),
            },
        )
        
        return TemplateTestResponse(
            message="Test extraction job enqueued",
            template_id=str(template_id),
            document_id=str(request.test_document_id),
            job_id=str(job.id),
        )
    except HTTPException:
        raise
    except ProgrammingError as e:
        logger.error(f"Database schema error testing template: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        logger.error(f"Database connection error testing template: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        logger.error(f"Database error testing template: {e}", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to test template",
        )
    except Exception as e:
        logger.error(f"Unexpected error testing template: {e}", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


class OCRBlockResponse(BaseModel):
    text: str
    bbox: List[float]  # [x, y, width, height] normalized 0-1
    bbox_pixels: List[int]  # [x, y, width, height] in pixels
    confidence: float
    page: int


class OCRDataResponse(BaseModel):
    blocks: List[OCRBlockResponse]
    page_count: int
    image_dimensions: Optional[Dict[str, int]] = None


@router.get(
    "/{template_id}/ocr-data",
    response_model=OCRDataResponse,
    status_code=status.HTTP_200_OK,
    summary="Get OCR data for a document",
    description="Retrieve OCR blocks with bounding boxes for a processed document. Used by visual template editor.",
)
async def get_template_ocr_data(
    template_id: UUID,
    document_id: UUID = Query(..., description="Document ID to get OCR data for"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    current_workspace=Depends(get_current_workspace),
    current_member=Depends(get_current_workspace_member),
):
    """Get OCR blocks with bounding boxes for a document."""
    try:
        set_correlation_id()
        
        # Verify template exists and user has access
        template_result = await db.execute(
            select(Template).where(
                Template.id == template_id,
                Template.workspace_id == current_workspace.id,
            )
        )
        template = template_result.scalar_one_or_none()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found",
            )
        
        # Authorization check
        authz_service = AuthzService()
        await authz_service.assert_resource_ownership(
            db, current_member.user_id, current_workspace.id, template.workspace_id
        )
        
        # Verify document exists and belongs to workspace
        doc_result = await db.execute(
            select(Document).where(
                Document.id == document_id,
                Document.workspace_id == current_workspace.id,
            )
        )
        document = doc_result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )
        
        # Get latest extraction result for this document
        extraction_result_query = await db.execute(
            select(ExtractionResult)
            .where(
                ExtractionResult.document_id == document_id,
                ExtractionResult.workspace_id == current_workspace.id,
            )
            .order_by(ExtractionResult.version.desc())
            .limit(1)
        )
        extraction_result = extraction_result_query.scalar_one_or_none()
        
        if not extraction_result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document has not been processed yet. Please process the document first.",
            )
        
        # Extract OCR blocks from metadata
        metadata = extraction_result.extraction_metadata or {}
        ocr_metadata = metadata.get("ocr_metadata", {})
        blocks_data = ocr_metadata.get("blocks", [])
        
        if not blocks_data:
            # If blocks not in metadata, try to extract them from the document
            # This requires re-running OCR, which is expensive, so we'll return empty
            logger.warning(
                f"OCR blocks not found in metadata for document {document_id}. "
                "Document may need to be reprocessed."
            )
            return OCRDataResponse(
                blocks=[],
                page_count=document.pages or 1,
                image_dimensions=None,
            )
        
        # Convert blocks to response format
        blocks = [
            OCRBlockResponse(
                text=block.get("text", ""),
                bbox=block.get("bbox", [0, 0, 0, 0]),
                bbox_pixels=block.get("bbox_pixels", [0, 0, 0, 0]),
                confidence=block.get("confidence", 0.0),
                page=block.get("page", 1),
            )
            for block in blocks_data
        ]
        
        # Get image dimensions if available
        image_dimensions = None
        if "dimensions" in ocr_metadata:
            dims = ocr_metadata["dimensions"]
            if isinstance(dims, (list, tuple)) and len(dims) >= 2:
                image_dimensions = {"width": dims[0], "height": dims[1]}
        
        return OCRDataResponse(
            blocks=blocks,
            page_count=document.pages or 1,
            image_dimensions=image_dimensions,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving OCR data: {e}", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve OCR data",
        )

