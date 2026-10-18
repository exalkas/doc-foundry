"""Public API router endpoints (API key authenticated)."""

import logging
import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import UUID

import pypdf
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import (
    SQLAlchemyError,
    IntegrityError,
    ProgrammingError,
    OperationalError,
)

from app.auth.dependencies import (
    get_current_api_key,
    get_current_workspace_for_api_key,
    require_api_key_scopes,
)
from app.config import settings
from app.core.storage import StorageService
from app.database import get_db
from app.models.document import Document, DocumentStatusEnum, DocumentSourceEnum
from app.models.extractionresult import ExtractionResult
from app.models.subscription import Subscription, SubscriptionPlanEnum, SubscriptionStatusEnum
from app.models.template import Template
from app.models.workspacemember import WorkspaceMember, WorkspaceMemberRole, WorkspaceMemberStatus
from app.services.file_validation_service import FileValidationService
from app.services.job_queue_service import JobQueueService, QuotaExceededError
from app.services.logging_service import get_logger, set_correlation_id
from app.services.plan_service import PlanService

logger = get_logger(__name__)

router = APIRouter()


class ExtractDocumentResponse(BaseModel):
    document_id: UUID
    status: str


class DocumentStatusResponse(BaseModel):
    document_id: UUID
    status: str
    result: Optional[Dict[str, Any]] = None


async def get_plan_tier(db: AsyncSession, workspace_id: UUID) -> str:
    """Get plan tier for workspace (subscriptions are per-user, get from workspace owner)."""
    from app.models.workspace import Workspace
    
    plan_mapping = {
        SubscriptionPlanEnum.STARTER: "starter",
        SubscriptionPlanEnum.PRO: "pro",
    }
    
    # Get workspace to find owner user_id
    workspace_result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    workspace = workspace_result.scalar_one_or_none()
    
    if not workspace:
        return "free"
    
    result = await db.execute(
        select(Subscription)
        .where(
            Subscription.user_id == workspace.owner_user_id,
            Subscription.status.in_([SubscriptionStatusEnum.ACTIVE, SubscriptionStatusEnum.TRIALING]),
        )
        .order_by(Subscription.created_at.desc())
    )
    subscription = result.scalar_one_or_none()
    
    if subscription:
        return plan_mapping.get(subscription.plan_id, "free")
    return "free"


@router.post("/documents:extract", response_model=ExtractDocumentResponse, status_code=status.HTTP_202_ACCEPTED)
async def extract_document_via_api_key(
    template_id: UUID = Form(...),
    callback_url: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    api_key = Depends(require_api_key_scopes(["documents:write"])),
    workspace = Depends(get_current_workspace_for_api_key),
) -> ExtractDocumentResponse:
    """Extract document using API key authentication with full service integration."""
    correlation_id = set_correlation_id()
    logger.info(
        "API key document extraction request",
        extra={
            "workspace_id": str(workspace.id),
            "template_id": str(template_id),
            "correlation_id": correlation_id,
        },
    )
    
    # Get plan tier
    plan_tier = await get_plan_tier(db, workspace.id)
    plan_service = PlanService()
    file_validation_service = FileValidationService(plan_service)
    storage_service = StorageService(settings.STORAGE_ROOT)
    job_queue_service = JobQueueService()
    
    try:
        # Verify template exists and belongs to workspace
        template_result = await db.execute(
            select(Template).where(
                Template.id == template_id,
                Template.workspace_id == workspace.id,
            )
        )
        template = template_result.scalar_one_or_none()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found",
            )
        
        # Find a workspace owner to use as uploaded_by_user_id (API keys don't have a user)
        owner_result = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace.id,
                WorkspaceMember.role == WorkspaceMemberRole.OWNER,
                WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
            ).limit(1)
        )
        owner_member = owner_result.scalar_one_or_none()
        
        if not owner_member:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No workspace owner found",
            )
        
        # Read uploaded file
        content = await file.read()
        file_name = file.filename or "uploaded_file"
        file_size_mb = len(content) / (1024 * 1024)
        
        # Check file size limit
        is_valid, error_msg = plan_service.check_file_size_limit(plan_tier, file_size_mb)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg,
            )
        
        # Save to temporary file for validation
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as tmp_file:
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        try:
            # Validate file
            is_valid, error_msg = file_validation_service.validate_file(
                tmp_path, plan_tier, file.content_type
            )
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_msg or "File validation failed",
                )
            
            # Count pages
            pages = None
            if file_name:
                ext = os.path.splitext(file_name)[1].lower()
                if ext == ".pdf":
                    try:
                        reader = pypdf.PdfReader(tmp_path)
                        pages = len(reader.pages)
                    except Exception:
                        pages = 1  # Default if can't read
                elif ext in {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".gif"}:
                    try:
                        with Image.open(tmp_path) as img:
                            pages = 1
                    except Exception:
                        pages = 1
            
            # Check page limit
            if pages:
                is_valid, error_msg = plan_service.check_pages_limit(plan_tier, pages)
                if not is_valid:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=error_msg,
                    )
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        
        # Generate storage path
        doc_id = uuid.uuid4()
        storage_path = f"{workspace.id}/default/{doc_id}/{file_name}"
        
        # Upload to storage
        await storage_service.upload(storage_path, content)
        
        # Determine file type
        file_type = file.content_type or "application/octet-stream"
        if file_name:
            ext = os.path.splitext(file_name)[1].lower()
            type_map = {
                ".pdf": "application/pdf",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".tiff": "image/tiff",
                ".tif": "image/tiff",
            }
            file_type = type_map.get(ext, file_type)
        
        # Create document record
        document = Document(
            id=doc_id,
            workspace_id=workspace.id,
            template_id=template_id,
            file_name=file_name,
            file_type=file_type,
            storage_path=storage_path,
            pages=pages,
            status=DocumentStatusEnum.PENDING,
            uploaded_by_user_id=owner_member.user_id,
            source=DocumentSourceEnum.API,
            callback_url=callback_url,
        )
        
        db.add(document)
        await db.flush()
        
        # Enqueue extraction job with idempotency
        try:
            # Get subscription for period dates (subscriptions are per-user, get from workspace owner)
            subscription_result = await db.execute(
                select(Subscription)
                .where(
                    Subscription.user_id == workspace.owner_user_id,
                    Subscription.status.in_([SubscriptionStatusEnum.ACTIVE, SubscriptionStatusEnum.TRIALING]),
                )
                .order_by(Subscription.created_at.desc())
            )
            subscription = subscription_result.scalar_one_or_none()
            
            period_start = subscription.current_period_start if subscription else datetime.now(timezone.utc)
            period_end = subscription.current_period_end if subscription else (datetime.now(timezone.utc).replace(day=1) + timedelta(days=32))
            
            await job_queue_service.enqueue_extraction_job(
                db,
                document.id,
                workspace.id,
                template_id,
                plan_tier,
                period_start,
                period_end,
                check_quota=True,
            )
        except QuotaExceededError as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=str(e),
            )
        
        await db.commit()
        await db.refresh(document)
        
        logger.info(
            "Document created for extraction via API",
            extra={
                "document_id": str(document.id),
                "workspace_id": str(workspace.id),
                "correlation_id": correlation_id,
            },
        )
        
        return ExtractDocumentResponse(
            document_id=document.id,
            status=document.status.value,
        )
    except HTTPException:
        raise
    except IntegrityError as e:
        await db.rollback()
        logger.warning(f"Integrity error creating document: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document data",
        )
    except ProgrammingError as e:
        await db.rollback()
        logger.error(f"Database schema error extracting document: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        await db.rollback()
        logger.error(f"Database connection error extracting document: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        await db.rollback()
        logger.exception(f"Database error extracting document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to extract document",
        )
    except Exception as e:
        await db.rollback()
        logger.exception(f"Unexpected error extracting document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.get("/documents/{document_id}", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    api_key = Depends(require_api_key_scopes(["documents:read"])),
    workspace = Depends(get_current_workspace_for_api_key),
) -> DocumentStatusResponse:
    """Get document status and extraction result."""
    logger.info(f"API key document status request: {document_id}")
    
    try:
        # Verify document exists and belongs to workspace
        document_result = await db.execute(
            select(Document).where(
                Document.id == document_id,
                Document.workspace_id == workspace.id,
            )
        )
        document = document_result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )
        
        # Get latest extraction result if available
        result_data: Optional[Dict[str, Any]] = None
        extraction_result = await db.execute(
            select(ExtractionResult)
            .where(ExtractionResult.document_id == document_id)
            .order_by(ExtractionResult.created_at.desc())
            .limit(1)
        )
        result = extraction_result.scalar_one_or_none()
        if result:
            result_data = result.extracted_json
        
        # Derive correct status based on extraction results
        derived_status = document.status.value
        if result:
            # Has extraction results, so it's truly completed
            if document.status == DocumentStatusEnum.SCANNED:
                derived_status = DocumentStatusEnum.COMPLETED.value
            else:
                derived_status = document.status.value
        else:
            # No extraction results - if status is COMPLETED, it should be SCANNED
            if document.status == DocumentStatusEnum.COMPLETED:
                derived_status = DocumentStatusEnum.SCANNED.value
            else:
                derived_status = document.status.value
        
        return DocumentStatusResponse(
            document_id=document.id,
            status=derived_status,
            result=result_data,
        )
    except HTTPException:
        raise
    except ProgrammingError as e:
        logger.error(f"Database schema error getting document status: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        logger.error(f"Database connection error getting document status: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        logger.exception(f"Database error getting document status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get document status",
        )
    except Exception as e:
        logger.exception(f"Unexpected error getting document status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )

