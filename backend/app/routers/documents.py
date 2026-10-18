"""Documents router endpoints."""

import json
import logging
import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from uuid import UUID

import pypdf
from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel
from PIL import Image
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload
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
from app.config import settings
from app.core.storage import StorageService
from app.database import get_db
from app.models.document import Document, DocumentStatusEnum, DocumentSourceEnum
from app.models.extractionresult import ExtractionResult
from app.models.job import Job, JobStatus
from app.models.project import Project
from app.models.template import Template
from app.models.subscription import Subscription, SubscriptionPlanEnum, SubscriptionStatusEnum
from app.services.authz_service import AuthzService
from app.services.export_service import ExportService
from app.services.file_validation_service import FileValidationService
from app.services.job_queue_service import JobQueueService, QuotaExceededError
from app.services.logging_service import get_logger, set_correlation_id, ErrorCategory
from app.services.plan_service import PlanService
from app.services.template_matcher_service import TemplateMatcherService
from app.services.ai_template_service import AITemplateService, AITemplateGenerationError
from app.services.template_service import TemplateService
from app.models.template import Template, ExportFormatEnum

logger = get_logger(__name__)

router = APIRouter()


class DocumentResponse(BaseModel):
    id: str
    workspace_id: str
    project_id: str | None
    template_id: str | None
    file_name: str
    file_type: str
    storage_path: str
    pages: int | None
    status: str
    uploaded_by_user_id: str
    source: str
    last_error: str | None
    raw_ocr_text: str | None = None
    raw_ocr_metadata: dict | None = None
    ocr_language: str | None = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class DocumentRetryRequest(BaseModel):
    template_id: Optional[str] = None


class DocumentRetryResponse(BaseModel):
    document: DocumentResponse


class DocumentExtractRequest(BaseModel):
    template_id: Optional[str] = None
    auto_match: bool = False
    create_template_with_ai: bool = False
    field_hints: Optional[Dict[str, Any]] = None


class GenerateTemplateRequest(BaseModel):
    export_format: Optional[str] = "json"
    template_name: Optional[str] = None
    description: Optional[str] = None


class PaginationMeta(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int


class PaginatedDocumentsResponse(BaseModel):
    documents: List[DocumentResponse]
    pagination: PaginationMeta


class ExportResponse(BaseModel):
    download_url: str
    expires_at: str
    path: str


class ExtractionResultResponse(BaseModel):
    id: str
    document_id: str
    template_id: str
    workspace_id: str
    extracted_json: Dict[str, Any]
    version: int
    metadata: Optional[Dict[str, Any]] = None
    created_at: str


class ExtractionLogResponse(BaseModel):
    id: str
    document_id: str
    level: str
    message: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: str


class DocumentDetailResponse(BaseModel):
    document: DocumentResponse
    extraction_result: Optional[ExtractionResultResponse] = None
    logs: List[ExtractionLogResponse] = []


async def get_plan_tier(db: AsyncSession, user_id: UUID) -> str:
    """Get plan tier for user (subscriptions are per-user, not per-workspace)."""
    # Map subscription plan to plan tier
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


@router.get("", response_model=PaginatedDocumentsResponse)
async def list_documents(
    project_id: Optional[UUID] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: Optional[int] = Query(1, ge=1),
    page_size: Optional[int] = Query(20, ge=1, le=100),
    sort: Optional[str] = Query("created_at"),
    order: Optional[str] = Query("desc"),
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
) -> PaginatedDocumentsResponse:
    """List documents for the current workspace with pagination and filters."""
    logger.info(f"Listing documents for workspace: {current_workspace.id}")
    
    try:
        # Base query - exclude soft-deleted documents
        base_query = select(Document).where(
            Document.workspace_id == current_workspace.id,
            Document.deleted_at.is_(None)
        )
        
        # Apply filters
        if project_id:
            base_query = base_query.where(Document.project_id == project_id)
        
        if status_filter:
            try:
                # Normalize to lowercase to match enum values
                status_normalized = status_filter.lower()
                # Map to enum - use the enum member directly to ensure proper type binding
                if status_normalized == "completed":
                    status_enum = DocumentStatusEnum.COMPLETED
                elif status_normalized == "pending":
                    status_enum = DocumentStatusEnum.PENDING
                elif status_normalized == "processing":
                    status_enum = DocumentStatusEnum.PROCESSING
                elif status_normalized == "scanned":
                    status_enum = DocumentStatusEnum.SCANNED
                elif status_normalized == "failed":
                    status_enum = DocumentStatusEnum.FAILED
                else:
                    raise ValueError(f"Invalid status: {status_filter}")
                base_query = base_query.where(Document.status == status_enum)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status_filter}. Valid values are: pending, processing, scanned, completed, failed",
                )
        
        # File name search (case-insensitive partial match)
        if search:
            base_query = base_query.where(Document.file_name.ilike(f"%{search}%"))
        
        # Date range filters
        if date_from:
            base_query = base_query.where(Document.created_at >= date_from)
        if date_to:
            # Add one day to include the entire end date
            date_to_end = date_to.replace(hour=23, minute=59, second=59, microsecond=999999)
            base_query = base_query.where(Document.created_at <= date_to_end)
        
        # Get total count for pagination
        # Create a count query from the same base query
        count_query = select(func.count(Document.id)).where(
            Document.workspace_id == current_workspace.id
        )
        
        if project_id:
            count_query = count_query.where(Document.project_id == project_id)
        
        if status_filter:
            try:
                status_normalized = status_filter.lower()
                # Map to enum - use the enum member directly to ensure proper type binding
                if status_normalized == "completed":
                    status_enum = DocumentStatusEnum.COMPLETED
                elif status_normalized == "pending":
                    status_enum = DocumentStatusEnum.PENDING
                elif status_normalized == "processing":
                    status_enum = DocumentStatusEnum.PROCESSING
                elif status_normalized == "scanned":
                    status_enum = DocumentStatusEnum.SCANNED
                elif status_normalized == "failed":
                    status_enum = DocumentStatusEnum.FAILED
                else:
                    status_enum = None
                if status_enum:
                    count_query = count_query.where(Document.status == status_enum)
            except ValueError:
                pass  # Already validated above
        
        if search:
            count_query = count_query.where(Document.file_name.ilike(f"%{search}%"))
        
        if date_from:
            count_query = count_query.where(Document.created_at >= date_from)
        if date_to:
            date_to_end = date_to.replace(hour=23, minute=59, second=59, microsecond=999999)
            count_query = count_query.where(Document.created_at <= date_to_end)
        
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()
        
        # Sorting
        if sort == "created_at":
            if order == "asc":
                base_query = base_query.order_by(Document.created_at.asc())
            else:
                base_query = base_query.order_by(Document.created_at.desc())
        elif sort == "updated_at":
            if order == "asc":
                base_query = base_query.order_by(Document.updated_at.asc())
            else:
                base_query = base_query.order_by(Document.updated_at.desc())
        
        # Pagination
        offset = (page - 1) * page_size
        base_query = base_query.limit(page_size).offset(offset)
        
        # Execute query
        result = await db.execute(base_query)
        documents = result.scalars().all()
        
        # Get document IDs to check for extraction results
        document_ids = [d.id for d in documents]
        
        # Check which documents have extraction results (batch query for efficiency)
        has_extraction_results = set()
        if document_ids:
            extraction_check_result = await db.execute(
                select(ExtractionResult.document_id)
                .where(ExtractionResult.document_id.in_(document_ids))
                .distinct()
            )
            has_extraction_results = {str(row[0]) for row in extraction_check_result.all()}
        
        # Calculate total pages
        total_pages = (total + page_size - 1) // page_size if total > 0 else 1
        
        def derive_status(doc: Document) -> str:
            """Derive correct status based on document state and extraction results."""
            doc_id_str = str(doc.id)
            # If document has extraction results, it's truly completed
            if doc_id_str in has_extraction_results:
                return DocumentStatusEnum.COMPLETED.value
            # If status is COMPLETED but no extraction results, it should be SCANNED
            if doc.status == DocumentStatusEnum.COMPLETED:
                return DocumentStatusEnum.SCANNED.value
            # Otherwise return the actual status
            return doc.status.value
        
        return PaginatedDocumentsResponse(
            documents=[
                DocumentResponse(
                    id=str(d.id),
                    workspace_id=str(d.workspace_id),
                    project_id=str(d.project_id) if d.project_id else None,
                    template_id=str(d.template_id) if d.template_id else None,
                    file_name=d.file_name,
                    file_type=d.file_type,
                    storage_path=d.storage_path,
                    pages=d.pages,
                    status=derive_status(d),
                    uploaded_by_user_id=str(d.uploaded_by_user_id),
                    source=d.source.value,
                    last_error=d.last_error,
                    raw_ocr_text=d.raw_ocr_text,
                    raw_ocr_metadata=d.raw_ocr_metadata,
                    ocr_language=d.ocr_language,
                    created_at=d.created_at.isoformat(),
                    updated_at=d.updated_at.isoformat(),
                )
                for d in documents
            ],
            pagination=PaginationMeta(
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
            ),
        )
    except HTTPException:
        raise
    except ProgrammingError as e:
        logger.error(f"Database schema error listing documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        logger.error(f"Database connection error listing documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        logger.error(
            f"Database error listing documents: {e}",
            error_category=ErrorCategory.SYSTEM_ERROR,
            exc_info=e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list documents",
        )
    except Exception as e:
        logger.error(
            f"Unexpected error listing documents: {e}",
            error_category=ErrorCategory.SYSTEM_ERROR,
            exc_info=e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    project_id: Optional[UUID] = Form(None),
    template_id: Optional[UUID] = Form(None),
    priority: Optional[bool] = Form(False),
    ocr_language: Optional[str] = Form("eng"),
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_user = Depends(get_current_user),
    current_member = Depends(get_current_workspace_member),
) -> DocumentResponse:
    """Upload a new document with plan limit checks and file validation."""
    correlation_id = set_correlation_id()
    logger.info(
        "Uploading document",
        extra={
            "filename": file.filename,
            "workspace_id": str(current_workspace.id),
            "correlation_id": correlation_id,
        },
    )
    
    # Authorization check
    authz_service = AuthzService()
    if not authz_service.can_perform_action(current_member.role, "upload_document"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to upload documents",
        )
    
    # Get plan tier (subscriptions are per-user)
    plan_tier = await get_plan_tier(db, current_user.id)
    plan_service = PlanService()
    file_validation_service = FileValidationService(plan_service)
    storage_service = StorageService(settings.STORAGE_ROOT)
    job_queue_service = JobQueueService()
    
    # Validate priority feature is enabled for plan
    if priority and not plan_service.check_feature_enabled(plan_tier, "priority_queue"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Priority queue is only available on Pro and Enterprise plans",
        )
    
    try:
        # Validate project_id if provided
        if project_id:
            project_result = await db.execute(
                select(Project).where(
                    Project.id == project_id,
                    Project.workspace_id == current_workspace.id,
                )
            )
            project = project_result.scalar_one_or_none()
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )
        
        # Read file content
        content = await file.read()
        file_size_mb = len(content) / (1024 * 1024)
        
        # Check file size limit
        is_valid, error_msg = plan_service.check_file_size_limit(plan_tier, file_size_mb)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg,
            )
        
        # Save to temporary file for validation
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename or "")[1]) as tmp_file:
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
            if file.filename:
                ext = os.path.splitext(file.filename)[1].lower()
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
        storage_path = f"{current_workspace.id}/{project_id if project_id else 'default'}/{doc_id}/{file.filename or f'document_{doc_id}'}"
        
        # Upload to storage
        await storage_service.upload(storage_path, content)
        
        # Determine file type
        file_type = file.content_type or "application/octet-stream"
        if file.filename:
            ext = os.path.splitext(file.filename)[1].lower()
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
            workspace_id=current_workspace.id,
            project_id=project_id,
            template_id=template_id,
            file_name=file.filename or f"document_{doc_id}",
            file_type=file_type,
            storage_path=storage_path,
            pages=pages,
            status=DocumentStatusEnum.PENDING,
            uploaded_by_user_id=current_user.id,
            source=DocumentSourceEnum.UI,
            ocr_language=ocr_language or "eng",
        )
        
        db.add(document)
        await db.flush()
        
        # Enqueue extraction job with idempotency
        try:
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
            period_end = subscription.current_period_end if subscription else datetime.now(timezone.utc).replace(day=1) + timedelta(days=32)
            
            await job_queue_service.enqueue_extraction_job(
                db,
                document.id,
                current_workspace.id,
                template_id,
                plan_tier,
                period_start,
                period_end,
                check_quota=True,
            )
            # Update document status to queued after job is enqueued
            document.status = DocumentStatusEnum.PENDING
            document.updated_at = datetime.now(timezone.utc)
        except QuotaExceededError as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=str(e),
            )
        
        await db.commit()
        await db.refresh(document)
        
        logger.info(
            "Document uploaded successfully",
            extra={
                "document_id": str(document.id),
                "workspace_id": str(current_workspace.id),
                "correlation_id": correlation_id,
            },
        )
        
        return DocumentResponse(
            id=str(document.id),
            workspace_id=str(document.workspace_id),
            project_id=str(document.project_id) if document.project_id else None,
            template_id=str(document.template_id) if document.template_id else None,
            file_name=document.file_name,
            file_type=document.file_type,
            storage_path=document.storage_path,
            pages=document.pages,
            status=document.status.value,
            uploaded_by_user_id=str(document.uploaded_by_user_id),
            source=document.source.value,
            last_error=document.last_error,
            raw_ocr_text=document.raw_ocr_text,
            raw_ocr_metadata=document.raw_ocr_metadata,
            ocr_language=document.ocr_language,
            created_at=document.created_at.isoformat(),
            updated_at=document.updated_at.isoformat(),
        )
    except HTTPException:
        raise
    except IntegrityError as e:
        await db.rollback()
        logger.warning(f"Integrity error uploading document: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document data",
        )
    except ProgrammingError as e:
        await db.rollback()
        logger.error(f"Database schema error uploading document: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        await db.rollback()
        logger.error(f"Database connection error uploading document: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(
            f"Database error uploading document: {e}",
            error_category=ErrorCategory.SYSTEM_ERROR,
            exc_info=e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload document",
        )
    except Exception as e:
        await db.rollback()
        logger.error(
            f"Unexpected error uploading document: {e}",
            error_category=ErrorCategory.SYSTEM_ERROR,
            exc_info=e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
):
    """Get a document by ID with extraction results and logs."""
    import time
    start_time = time.time()
    logger.info(f"[GET_DOCUMENT] Starting request for document: {document_id}, workspace: {current_workspace.id}")
    
    try:
        # Use noload to prevent loading relationships that could cause recursion
        query_start = time.time()
        result = await db.execute(
            select(Document)
            .options(
                noload(Document.workspace),
                noload(Document.project),
                noload(Document.template),
                noload(Document.uploaded_by),
                noload(Document.extraction_results),
                noload(Document.extraction_logs),
            )
            .where(
                Document.id == document_id,
                Document.workspace_id == current_workspace.id,
            )
        )
        document = result.scalar_one_or_none()
        query_time = (time.time() - query_start) * 1000
        logger.info(f"[GET_DOCUMENT] Document query completed in {query_time:.2f}ms, found: {document is not None}")
        
        if not document:
            # Check if document exists but belongs to a different workspace (for debugging)
            check_start = time.time()
            check_result = await db.execute(
                select(Document).where(Document.id == document_id)
            )
            check_doc = check_result.scalar_one_or_none()
            check_time = (time.time() - check_start) * 1000
            
            if check_doc:
                logger.warning(
                    f"[GET_DOCUMENT] Document {document_id} exists but belongs to workspace {check_doc.workspace_id}, "
                    f"not current workspace {current_workspace.id} (check took {check_time:.2f}ms)"
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Document not found in current workspace",
                )
            else:
                logger.warning(
                    f"[GET_DOCUMENT] Document {document_id} does not exist in database (check took {check_time:.2f}ms)"
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Document not found",
                )
        
        # Detach from session to prevent any lazy loading during serialization
        db.expunge(document)
        
        # Get latest extraction result
        extraction_result = None
        extraction_query_start = time.time()
        extraction_result_query = await db.execute(
            select(ExtractionResult)
            .where(
                ExtractionResult.document_id == document_id,
                ExtractionResult.workspace_id == current_workspace.id,
            )
            .order_by(ExtractionResult.version.desc())
            .limit(1)
        )
        extraction_result_obj = extraction_result_query.scalar_one_or_none()
        extraction_query_time = (time.time() - extraction_query_start) * 1000
        logger.info(f"[GET_DOCUMENT] Extraction result query completed in {extraction_query_time:.2f}ms, found: {extraction_result_obj is not None}")
        if extraction_result_obj:
            # Ensure extracted_json is a plain dict (optimize for large JSON)
            extracted_json = extraction_result_obj.extracted_json
            if extracted_json:
                try:
                    # Only serialize if reasonably sized (avoid expensive operations on huge JSON)
                    json_str = str(extracted_json)
                    if len(json_str) < 50000:  # Only serialize if under 50KB
                        extracted_json = json.loads(json.dumps(extracted_json))
                    # Otherwise use as-is (should already be a dict/list)
                except (TypeError, ValueError):
                    # If serialization fails, use as-is
                    pass
            
            extraction_result = ExtractionResultResponse(
                id=str(extraction_result_obj.id),
                document_id=str(extraction_result_obj.document_id),
                template_id=str(extraction_result_obj.template_id),
                workspace_id=str(extraction_result_obj.workspace_id),
                extracted_json=extracted_json or {},
                version=extraction_result_obj.version,
                metadata=extraction_result_obj.extraction_metadata,
                created_at=extraction_result_obj.created_at.isoformat(),
            )
        
        # Get extraction logs (limit to 50 for performance, can be increased if needed)
        from app.models.extractionlog import ExtractionLog
        logs_query_start = time.time()
        logs_query = await db.execute(
            select(ExtractionLog)
            .where(ExtractionLog.document_id == document_id)
            .order_by(ExtractionLog.created_at.desc())
            .limit(50)  # Reduced from 100 for better performance
        )
        logs_objs = logs_query.scalars().all()
        logs_query_time = (time.time() - logs_query_start) * 1000
        logger.info(f"[GET_DOCUMENT] Logs query completed in {logs_query_time:.2f}ms, found {len(logs_objs)} logs")
        logs = []
        for log in logs_objs:
            # Use event_metadata (the actual attribute name, not metadata which is SQLAlchemy MetaData)
            log_metadata = log.event_metadata
            # Only serialize if metadata exists and is not too large
            if log_metadata:
                try:
                    # Check size before expensive serialization
                    metadata_str = str(log_metadata)
                    if len(metadata_str) < 10000:  # Only serialize if reasonably small
                        log_metadata = json.loads(json.dumps(log_metadata))
                    else:
                        # For large metadata, use as-is (should already be a dict)
                        log_metadata = dict(log_metadata) if hasattr(log_metadata, '__iter__') else log_metadata
                except (TypeError, ValueError):
                    # If serialization fails, use as-is
                    log_metadata = dict(log_metadata) if hasattr(log_metadata, '__iter__') else log_metadata
            else:
                log_metadata = None
            
            logs.append(ExtractionLogResponse(
                id=str(log.id),
                document_id=str(log.document_id),
                level=log.level.value,
                message=log.message,
                metadata=log_metadata,
                created_at=log.created_at.isoformat(),
            ))
        
        # Ensure raw_ocr_metadata is a plain dict to avoid serialization issues
        raw_ocr_metadata = None
        if document.raw_ocr_metadata:
            try:
                # Create a clean copy to avoid any SQLAlchemy proxy issues
                raw_ocr_metadata = json.loads(json.dumps(document.raw_ocr_metadata))
            except (TypeError, ValueError):
                # Fallback to direct assignment if JSON serialization fails
                raw_ocr_metadata = document.raw_ocr_metadata
        
        # Derive correct status based on extraction results
        derived_status = document.status.value
        if extraction_result_obj:
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
        
        response_start = time.time()
        response = DocumentDetailResponse(
            document=DocumentResponse(
                id=str(document.id),
                workspace_id=str(document.workspace_id),
                project_id=str(document.project_id) if document.project_id else None,
                template_id=str(document.template_id) if document.template_id else None,
                file_name=document.file_name,
                file_type=document.file_type,
                storage_path=document.storage_path,
                pages=document.pages,
                status=derived_status,
                uploaded_by_user_id=str(document.uploaded_by_user_id),
                source=document.source.value,
                last_error=document.last_error,
                raw_ocr_text=document.raw_ocr_text,
                raw_ocr_metadata=raw_ocr_metadata,
                ocr_language=document.ocr_language,
                created_at=document.created_at.isoformat(),
                updated_at=document.updated_at.isoformat(),
            ),
            extraction_result=extraction_result,
            logs=logs,
        )
        response_time = (time.time() - response_start) * 1000
        total_time = (time.time() - start_time) * 1000
        logger.info(f"[GET_DOCUMENT] Response serialization took {response_time:.2f}ms, total request time: {total_time:.2f}ms for document: {document_id}")
        return response
    except HTTPException:
        total_time = (time.time() - start_time) * 1000
        logger.warning(f"[GET_DOCUMENT] HTTPException after {total_time:.2f}ms for document: {document_id}")
        raise
    except ProgrammingError as e:
        total_time = (time.time() - start_time) * 1000
        logger.error(f"[GET_DOCUMENT] Database schema error after {total_time:.2f}ms getting document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        total_time = (time.time() - start_time) * 1000
        logger.error(f"[GET_DOCUMENT] Database connection error after {total_time:.2f}ms getting document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        total_time = (time.time() - start_time) * 1000
        logger.error(
            f"[GET_DOCUMENT] Database error after {total_time:.2f}ms getting document {document_id}: {e}",
            error_category=ErrorCategory.SYSTEM_ERROR,
            exc_info=e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document",
        )
    except Exception as e:
        total_time = (time.time() - start_time) * 1000
        logger.error(
            f"[GET_DOCUMENT] Unexpected error after {total_time:.2f}ms getting document {document_id}: {e}",
            error_category=ErrorCategory.SYSTEM_ERROR,
            exc_info=e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.get("/{document_id}/status", response_model=DocumentResponse)
async def get_document_status(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
):
    """Get minimal document status (lightweight endpoint for polling)."""
    import time
    start_time = time.time()
    logger.info(f"[GET_DOCUMENT_STATUS] Starting lightweight status check for document: {document_id}")
    
    try:
        # Only fetch the document, no extraction results or logs
        result = await db.execute(
            select(Document)
            .options(
                noload(Document.workspace),
                noload(Document.project),
                noload(Document.template),
                noload(Document.uploaded_by),
                noload(Document.extraction_results),
                noload(Document.extraction_logs),
            )
            .where(
                Document.id == document_id,
                Document.workspace_id == current_workspace.id,
                Document.deleted_at.is_(None),
            )
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )
        
        # Check if document has extraction results to derive correct status
        has_extraction = await db.execute(
            select(func.count(ExtractionResult.id))
            .where(ExtractionResult.document_id == document_id)
        )
        has_extraction_count = has_extraction.scalar_one() or 0
        
        # Derive correct status
        derived_status = document.status.value
        if has_extraction_count > 0:
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
        
        total_time = (time.time() - start_time) * 1000
        logger.info(f"[GET_DOCUMENT_STATUS] Status check completed in {total_time:.2f}ms for document: {document_id}, status: {derived_status}")
        
        return DocumentResponse(
            id=str(document.id),
            workspace_id=str(document.workspace_id),
            project_id=str(document.project_id) if document.project_id else None,
            template_id=str(document.template_id) if document.template_id else None,
            file_name=document.file_name,
            file_type=document.file_type,
            storage_path=document.storage_path,
            pages=document.pages,
            status=derived_status,
            uploaded_by_user_id=str(document.uploaded_by_user_id),
            source=document.source.value,
            last_error=document.last_error,
            raw_ocr_text=None,  # Omit for lightweight response
            raw_ocr_metadata=None,  # Omit for lightweight response
            ocr_language=document.ocr_language,
            created_at=document.created_at.isoformat(),
            updated_at=document.updated_at.isoformat(),
        )
    except HTTPException:
        raise
    except Exception as e:
        total_time = (time.time() - start_time) * 1000
        logger.error(f"[GET_DOCUMENT_STATUS] Error after {total_time:.2f}ms: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document status",
        )


@router.get("/{document_id}/ocr-blocks")
async def get_ocr_blocks(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
):
    """Get OCR blocks with bounding boxes for a document."""
    logger.info(f"Getting OCR blocks for document: {document_id}")
    
    try:
        result = await db.execute(
            select(Document).where(
                Document.id == document_id,
                Document.workspace_id == current_workspace.id,
            )
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )
        
        # Extract blocks from OCR metadata
        # Blocks can be at the top level or nested in ocr_metadata
        blocks = []
        if document.raw_ocr_metadata:
            # Log metadata structure for debugging
            logger.debug(
                f"raw_ocr_metadata keys for document {document_id}: {list(document.raw_ocr_metadata.keys()) if isinstance(document.raw_ocr_metadata, dict) else 'not a dict'}"
            )
            
            # Try top-level blocks first (Google Vision format)
            blocks = document.raw_ocr_metadata.get("blocks", [])
            
            # If no blocks at top level, try nested in ocr_metadata
            if not blocks and "ocr_metadata" in document.raw_ocr_metadata:
                ocr_meta = document.raw_ocr_metadata.get("ocr_metadata", {})
                if isinstance(ocr_meta, dict):
                    blocks = ocr_meta.get("blocks", [])
        
        logger.info(
            f"Retrieved {len(blocks)} OCR blocks for document {document_id}. "
            f"Has raw_ocr_metadata: {bool(document.raw_ocr_metadata)}, "
            f"Has raw_ocr_text: {bool(document.raw_ocr_text)}"
        )
        
        return {
            "document_id": str(document.id),
            "blocks": blocks,
            "page_count": document.pages or 1,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error getting OCR blocks: {e}",
            error_category=ErrorCategory.SYSTEM_ERROR,
            exc_info=e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve OCR blocks",
        )


@router.post("/{document_id}/retry-with-ai")
async def retry_with_ai(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
):
    """Retry extraction using AI LLM for low accuracy documents."""
    logger.info(f"Retrying extraction with AI for document: {document_id}")
    
    # Get plan tier (subscriptions are per-user)
    plan_tier = await get_plan_tier(db, current_member.user_id)
    plan_service = PlanService()
    
    # Check if AI extraction is enabled for the plan
    if not plan_service.check_ai_extraction_enabled(plan_tier):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI extraction is not available on your current plan. Please upgrade to Starter or higher.",
        )
    
    try:
        result = await db.execute(
            select(Document).where(
                Document.id == document_id,
                Document.workspace_id == current_workspace.id,
            )
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )
        
        # Check if document has low confidence
        confidence = document.raw_ocr_metadata.get("confidence", 1.0) if document.raw_ocr_metadata else 1.0
        if confidence >= 0.8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document confidence is already high. AI retry is only available for low accuracy documents.",
            )
        
        # Enqueue AI extraction job
        from app.services.job_queue_service import JobQueueService
        from app.models.subscription import Subscription, SubscriptionStatusEnum
        from datetime import timedelta
        
        job_queue_service = JobQueueService()
        subscription_result = await db.execute(
            select(Subscription)
            .where(
                Subscription.user_id == current_member.user_id,
                Subscription.status.in_([SubscriptionStatusEnum.ACTIVE, SubscriptionStatusEnum.TRIALING]),
            )
            .order_by(Subscription.created_at.desc())
        )
        subscription = subscription_result.scalar_one_or_none()
        
        period_start = subscription.current_period_start if subscription else datetime.now(timezone.utc)
        period_end = subscription.current_period_end if subscription else datetime.now(timezone.utc) + timedelta(days=30)
        
        # Create AI extraction job (with special flag)
        job = await job_queue_service.enqueue_extraction_job(
            db,
            document.id,
            current_workspace.id,
            document.template_id,
            plan_tier,
            period_start,
            period_end,
            check_quota=True,
        )
        
        # Update document status
        document.status = DocumentStatusEnum.PENDING
        document.updated_at = datetime.now(timezone.utc)
        await db.commit()
        
        return {
            "document_id": str(document.id),
            "job_id": str(job.id),
            "status": "queued",
            "message": "AI extraction job enqueued",
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(
            f"Error retrying with AI: {e}",
            error_category=ErrorCategory.SYSTEM_ERROR,
            exc_info=e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enqueue AI extraction",
        )


@router.post("/{document_id}/generate-template")
async def generate_template_from_document(
    document_id: UUID,
    request: GenerateTemplateRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_user = Depends(get_current_user),
    current_member = Depends(get_current_workspace_member),
):
    """Generate a template from document OCR output using AI."""
    correlation_id = set_correlation_id()
    logger.info(
        f"Generating template from document: {document_id}",
        extra={
            "document_id": str(document_id),
            "workspace_id": str(current_workspace.id),
            "correlation_id": correlation_id,
        },
    )

    # Check feature flag
    if not settings.ENABLE_AI_TEMPLATE_GENERATION:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI template generation is disabled",
        )

    # Authorization check
    authz_service = AuthzService()
    if not authz_service.can_perform_action(current_member.role, "create_template"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create templates",
        )

    try:
        # Get document
        result = await db.execute(
            select(Document).where(
                Document.id == document_id,
                Document.workspace_id == current_workspace.id,
            )
        )
        document = result.scalar_one_or_none()

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )

        # Check if document has OCR text
        if not document.raw_ocr_text or not document.raw_ocr_text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document has no OCR text. Please ensure the document has been processed.",
            )

        # Check if template already exists
        if document.template_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document already has a template assigned. Remove the template first to generate a new one.",
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

        # Validate export format
        export_format_str = (request.export_format or "json").lower()
        try:
            export_format = ExportFormatEnum(export_format_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid export format: {request.export_format}. Must be one of: json, csv, excel",
            )

        # Enqueue template generation job instead of running synchronously
        job_queue_service = JobQueueService()
        job = await job_queue_service.enqueue_template_generation_job(
            session=db,
            document_id=document_id,
            workspace_id=current_workspace.id,
            user_id=current_user.id,
            export_format=export_format_str,
            template_name=request.template_name,
            description=request.description,
            plan_tier=plan_tier,
        )

        await db.commit()

        logger.info(f"Template generation job enqueued: {job.id}")

        # Return job response
        class JobResponse(BaseModel):
            job_id: str
            status: str
            message: str

        return JobResponse(
            job_id=str(job.id),
            status=job.status.value,
            message="Template generation job has been queued. You will be notified when it completes.",
        )

    except HTTPException:
        raise
    except IntegrityError as e:
        await db.rollback()
        logger.warning(f"Integrity error generating template: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create template due to data conflict",
        )
    except ProgrammingError as e:
        await db.rollback()
        logger.error(f"Database schema error generating template: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        await db.rollback()
        logger.error(f"Database connection error generating template: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(
            f"Database error generating template: {e}",
            error_category=ErrorCategory.SYSTEM_ERROR,
            exc_info=e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create template",
        )
    except Exception as e:
        await db.rollback()
        logger.error(
            f"Unexpected error generating template: {e}",
            error_category=ErrorCategory.SYSTEM_ERROR,
            exc_info=e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while generating template",
        )


@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
):
    """Get job status by ID."""
    result = await db.execute(
        select(Job).where(Job.id == job_id)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    # Verify workspace ownership
    if job.payload and job.payload.get("workspace_id") != str(current_workspace.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    class JobStatusResponse(BaseModel):
        job_id: str
        status: str
        type: str
        attempts: int
        max_attempts: int
        last_error: str | None
        created_at: str
        updated_at: str
        template_id: str | None = None

        class Config:
            from_attributes = True

    template_id = None
    if job.status == JobStatus.SUCCEEDED and job.payload:
        template_id = job.payload.get("template_id")

    return JobStatusResponse(
        job_id=str(job.id),
        status=job.status.value,
        type=job.type.value,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        last_error=job.last_error,
        created_at=job.created_at.isoformat(),
        updated_at=job.updated_at.isoformat(),
        template_id=template_id,
    )


@router.post("/{document_id}/extract")
async def extract_document(
    document_id: UUID,
    request: DocumentExtractRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
):
    """Run extraction on a document with various options."""
    logger.info(f"Extracting document: {document_id}")
    
    authz_service = AuthzService()
    job_queue_service = JobQueueService()
    template_matcher = TemplateMatcherService()
    plan_tier = await get_plan_tier(db, current_member.user_id)
    plan_service = PlanService()
    
    try:
        result = await db.execute(
            select(Document).where(
                Document.id == document_id,
                Document.workspace_id == current_workspace.id,
            )
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )
        
        # Authorization check
        await authz_service.assert_resource_ownership(
            db, current_member.user_id, current_workspace.id, document.workspace_id
        )
        
        template_id = None
        
        # Handle auto-match
        if request.auto_match:
            matched_template, best_score = await template_matcher.auto_match_template(
                db, document_id, current_workspace.id
            )
            if matched_template:
                template_id = matched_template.id
                document.template_id = template_id
            else:
                # Provide more informative error message
                if best_score > 0:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"No matching template found. Best match score: {best_score:.1%} (minimum required: 30%). Please select a template manually or create a new template.",
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="No templates available for auto-matching. Please create a template first or select one manually.",
                    )
        # Handle AI template creation
        elif request.create_template_with_ai:
            # Check if AI feature is enabled
            if plan_tier not in ["pro", "enterprise"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="AI template creation is only available on Pro and Enterprise plans",
                )
            
            # Check if feature flag is enabled
            if not settings.ENABLE_AI_TEMPLATE_GENERATION:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="AI template generation is disabled",
                )
            
            # Check if document has OCR text
            if not document.raw_ocr_text or not document.raw_ocr_text.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Document has no OCR text. Please ensure the document has been processed first.",
                )
            
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
            
            # Get OCR blocks if available
            ocr_blocks = None
            if document.raw_ocr_metadata and "blocks" in document.raw_ocr_metadata:
                ocr_blocks = document.raw_ocr_metadata["blocks"]
            
            # Generate template using AI
            ai_service = AITemplateService()
            try:
                export_format = request.export_format or "json"
                field_schema = await ai_service.generate_template_from_ocr(
                    ocr_text=document.raw_ocr_text,
                    ocr_blocks=ocr_blocks,
                    export_format=export_format,
                    document_type_hint=document.file_name,
                )
            except AITemplateGenerationError as e:
                logger.error(f"AI template generation failed: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to generate template: {str(e)}",
                )
            
            # Validate generated schema
            template_service = TemplateService()
            is_valid, errors = template_service.validate_field_schema(field_schema)
            if not is_valid:
                logger.error(f"Generated schema validation failed: {errors}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Generated template schema is invalid: {', '.join(errors)}",
                )
            
            # Add metadata to field_schema indicating this is AI-generated
            if isinstance(field_schema, dict):
                if "_metadata" not in field_schema:
                    field_schema["_metadata"] = {}
                field_schema["_metadata"]["ai_generated"] = True
                field_schema["_metadata"]["generated_at"] = datetime.now(timezone.utc).isoformat()
            
            # Generate template name
            template_name = f"AI Template from {document.file_name}"
            if len(template_name) > 255:
                template_name = template_name[:252] + "..."
            
            # Determine export format enum
            try:
                export_format_enum = ExportFormatEnum(export_format.lower())
            except ValueError:
                export_format_enum = ExportFormatEnum.JSON
            
            # Create template
            template = Template(
                workspace_id=current_workspace.id,
                project_id=document.project_id,
                name=template_name,
                description=f"Auto-generated template from document: {document.file_name}",
                document_type=None,
                field_schema=field_schema,
                default_export_format=export_format_enum,
                created_by_user_id=current_member.user_id,
            )
            
            db.add(template)
            await db.flush()
            
            # Assign template to document
            template_id = template.id
            document.template_id = template_id
            
            logger.info(
                f"Created AI template {template_id} for document {document_id}",
                extra={
                    "template_id": str(template_id),
                    "document_id": str(document_id),
                    "workspace_id": str(current_workspace.id),
                },
            )
        # Use provided template_id
        elif request.template_id:
            template_uuid = UUID(request.template_id)
            template_result = await db.execute(
                select(Template).where(
                    Template.id == template_uuid,
                    Template.workspace_id == current_workspace.id,
                )
            )
            template = template_result.scalar_one_or_none()
            if not template:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Template not found",
                )
            template_id = template_uuid
            document.template_id = template_id
        
        # Enqueue extraction job (subscriptions are per-user)
        subscription_result = await db.execute(
            select(Subscription)
            .where(
                Subscription.user_id == current_member.user_id,
                Subscription.status.in_([SubscriptionStatusEnum.ACTIVE, SubscriptionStatusEnum.TRIALING]),
            )
            .order_by(Subscription.created_at.desc())
        )
        subscription = subscription_result.scalar_one_or_none()
        
        period_start = subscription.current_period_start if subscription else datetime.now(timezone.utc)
        period_end = subscription.current_period_end if subscription else datetime.now(timezone.utc) + timedelta(days=30)
        
        job = await job_queue_service.enqueue_extraction_job(
            db,
            document.id,
            current_workspace.id,
            template_id,
            plan_tier,
            period_start,
            period_end,
            check_quota=True,
        )
        
        document.status = DocumentStatusEnum.PENDING
        document.updated_at = datetime.now(timezone.utc)
        await db.commit()
        
        return {
            "document_id": str(document.id),
            "job_id": str(job.id),
            "template_id": str(template_id) if template_id else None,
            "status": "queued",
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(
            f"Error extracting document: {e}",
            error_category=ErrorCategory.SYSTEM_ERROR,
            exc_info=e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enqueue extraction",
        )


@router.patch("/{document_id}/extraction-result")
async def update_extraction_result(
    document_id: UUID,
    extracted_json: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
):
    """Manually update extraction result fields."""
    logger.info(f"Updating extraction result for document: {document_id}")
    
    authz_service = AuthzService()
    
    try:
        result = await db.execute(
            select(Document).where(
                Document.id == document_id,
                Document.workspace_id == current_workspace.id,
            )
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )
        
        if not document.template_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document has no template assigned",
            )
        
        # Authorization check
        await authz_service.assert_resource_ownership(
            db, current_member.user_id, current_workspace.id, document.workspace_id
        )
        
        # Get latest extraction result to determine next version
        latest_result_query = await db.execute(
            select(ExtractionResult)
            .where(
                ExtractionResult.document_id == document_id,
                ExtractionResult.workspace_id == current_workspace.id,
            )
            .order_by(ExtractionResult.version.desc())
            .limit(1)
        )
        latest_result = latest_result_query.scalar_one_or_none()
        
        next_version = (latest_result.version + 1) if latest_result else 1
        
        # Create new extraction result version
        new_result = ExtractionResult(
            document_id=document.id,
            template_id=document.template_id,
            workspace_id=current_workspace.id,
            extracted_json=extracted_json,
            version=next_version,
        )
        db.add(new_result)
        
        # Log manual correction
        from app.models.extractionlog import ExtractionLog, ExtractionLogLevel
        log = ExtractionLog(
            document_id=document.id,
            level=ExtractionLogLevel.INFO,
            message=f"Manual field correction applied (version {next_version})",
            metadata={"edited_by": str(current_member.user_id), "version": next_version},
        )
        db.add(log)
        
        await db.commit()
        await db.refresh(new_result)
        
        return {
            "id": str(new_result.id),
            "document_id": str(new_result.document_id),
            "template_id": str(new_result.template_id),
            "extracted_json": new_result.extracted_json,
            "version": new_result.version,
            "created_at": new_result.created_at.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(
            f"Error updating extraction result: {e}",
            error_category=ErrorCategory.SYSTEM_ERROR,
            exc_info=e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update extraction result",
        )


@router.post("/{document_id}/retry", response_model=DocumentRetryResponse)
async def retry_document_extraction(
    document_id: UUID,
    request: Optional[DocumentRetryRequest] = Body(None),
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
) -> DocumentRetryResponse:
    """Retry extraction for a document. Optionally set template_id."""
    logger.info(f"Retrying extraction for document: {document_id}")
    
    authz_service = AuthzService()
    job_queue_service = JobQueueService()
    
    try:
        result = await db.execute(
            select(Document).where(
                Document.id == document_id,
                Document.workspace_id == current_workspace.id,
            )
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )
        
        # Authorization check
        await authz_service.assert_resource_ownership(
            db, current_member.user_id, current_workspace.id, document.workspace_id
        )
        
        # Update template_id if provided
        if request and request.template_id:
            template_uuid = UUID(request.template_id)
            # Verify template exists and belongs to workspace
            template_result = await db.execute(
                select(Template).where(
                    Template.id == template_uuid,
                    Template.workspace_id == current_workspace.id,
                )
            )
            template = template_result.scalar_one_or_none()
            if not template:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Template not found",
                )
            document.template_id = template_uuid
        elif document.template_id:
            # Verify existing template_id still exists before retrying
            template_result = await db.execute(
                select(Template).where(
                    Template.id == document.template_id,
                    Template.workspace_id == current_workspace.id,
                )
            )
            template = template_result.scalar_one_or_none()
            if not template:
                # Template was deleted, clear it so OCR-only extraction can proceed
                logger.warning(
                    f"Template {document.template_id} not found for document {document_id}, clearing template_id for retry"
                )
                document.template_id = None
        
        # Get plan tier
        plan_tier = await get_plan_tier(db, current_workspace.id)
        
        # Get subscription for period dates
        subscription_result = await db.execute(
            select(Subscription)
            .where(
                Subscription.workspace_id == current_workspace.id,
                Subscription.status.in_([SubscriptionStatusEnum.ACTIVE, SubscriptionStatusEnum.TRIALING]),
            )
            .order_by(Subscription.created_at.desc())
        )
        subscription = subscription_result.scalar_one_or_none()
        
        period_start = subscription.current_period_start if subscription else datetime.now(timezone.utc)
        period_end = subscription.current_period_end if subscription else datetime.now(timezone.utc).replace(day=1) + timedelta(days=32)
        
        # Reset status and enqueue new job
        document.status = DocumentStatusEnum.PENDING
        document.last_error = None
        
        try:
            await job_queue_service.enqueue_extraction_job(
                db,
                document.id,
                current_workspace.id,
                document.template_id,
                plan_tier,
                period_start,
                period_end,
                check_quota=True,
            )
        except QuotaExceededError as e:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=str(e),
            )
        
        await db.commit()
        await db.refresh(document)
        
        logger.info(f"Document extraction retry initiated: {document.id}")
        return DocumentRetryResponse(
            document=DocumentResponse(
                id=str(document.id),
                workspace_id=str(document.workspace_id),
                project_id=str(document.project_id) if document.project_id else None,
                template_id=str(document.template_id) if document.template_id else None,
                file_name=document.file_name,
                file_type=document.file_type,
                storage_path=document.storage_path,
                pages=document.pages,
                status=document.status.value,
                uploaded_by_user_id=str(document.uploaded_by_user_id),
                source=document.source.value,
                last_error=document.last_error,
                raw_ocr_text=document.raw_ocr_text,
                raw_ocr_metadata=document.raw_ocr_metadata,
                ocr_language=document.ocr_language,
                created_at=document.created_at.isoformat(),
                updated_at=document.updated_at.isoformat(),
            )
        )
    except HTTPException:
        raise
    except ProgrammingError as e:
        await db.rollback()
        logger.error(f"Database schema error retrying document: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        await db.rollback()
        logger.error(f"Database connection error retrying document: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(
            f"Database error retrying document: {e}",
            error_category=ErrorCategory.SYSTEM_ERROR,
            exc_info=e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retry document extraction",
        )
    except Exception as e:
        await db.rollback()
        logger.error(
            f"Unexpected error retrying document: {e}",
            error_category=ErrorCategory.SYSTEM_ERROR,
            exc_info=e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.get("/{document_id}/export", response_model=ExportResponse)
async def export_document(
    document_id: UUID,
    format: str = Query("json", regex="^(json|csv|excel)$"),
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
) -> ExportResponse:
    """Export extraction results for a document."""
    logger.info(f"Exporting document {document_id} as {format}")
    
    authz_service = AuthzService()
    export_service = ExportService()
    
    try:
        result = await db.execute(
            select(Document).where(
                Document.id == document_id,
                Document.workspace_id == current_workspace.id,
            )
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )
        
        # Authorization check
        await authz_service.assert_resource_ownership(
            db, current_member.user_id, current_workspace.id, document.workspace_id
        )
        
        # Get latest extraction result (matching what's shown in the UI)
        results_query = await db.execute(
            select(ExtractionResult).where(
                ExtractionResult.document_id == document_id,
                ExtractionResult.workspace_id == current_workspace.id,
            )
            .order_by(ExtractionResult.version.desc())
            .limit(1)
        )
        extraction_result = results_query.scalar_one_or_none()
        
        if not extraction_result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No extraction results found for this document",
            )
        
        # Convert to dict format (single result, matching UI display)
        results_data = [
            {
                "document_id": str(extraction_result.document_id),
                "template_id": str(extraction_result.template_id),
                "version": extraction_result.version,
                "created_at": extraction_result.created_at.isoformat(),
                "extracted_json": extraction_result.extracted_json,
            }
        ]
        
        # Generate export
        if format == "json":
            export_path = await export_service.export_to_json(
                results_data, current_workspace.id
            )
        elif format == "csv":
            export_path = await export_service.export_to_csv(
                results_data, current_workspace.id
            )
        else:  # excel
            export_path = await export_service.export_to_excel(
                results_data, current_workspace.id
            )
        
        # Generate signed URL
        signed_url_info = export_service.generate_signed_url(export_path)
        
        return ExportResponse(
            download_url=signed_url_info["download_url"],
            expires_at=signed_url_info["expires_at"],
            path=signed_url_info["path"],
        )
    except HTTPException:
        raise
    except ProgrammingError as e:
        logger.error(f"Database schema error exporting document: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        logger.error(f"Database connection error exporting document: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        logger.error(
            f"Database error exporting document: {e}",
            error_category=ErrorCategory.SYSTEM_ERROR,
            exc_info=e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export document",
        )
    except Exception as e:
        logger.error(
            f"Unexpected error exporting document: {e}",
            error_category=ErrorCategory.SYSTEM_ERROR,
            exc_info=e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )


@router.get("/{document_id}/file")
async def get_document_file(
    document_id: UUID,
    page: Optional[int] = Query(None, description="Page number for PDFs (1-indexed)"),
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
):
    """Get the original document file or a specific page image for PDFs."""
    from fastapi.responses import FileResponse, Response
    from pdf2image import convert_from_path
    import io
    
    logger.info(f"Serving file for document {document_id}, page={page}")
    
    authz_service = AuthzService()
    storage_service = StorageService(settings.STORAGE_ROOT)
    
    try:
        result = await db.execute(
            select(Document).where(
                Document.id == document_id,
                Document.workspace_id == current_workspace.id,
            )
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )
        
        # Authorization check
        await authz_service.assert_resource_ownership(
            db, current_member.user_id, current_workspace.id, document.workspace_id
        )
        
        # Resolve file path
        file_path = storage_service.resolve_path(document.storage_path)
        
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found in storage",
            )
        
        # If page is specified and it's a PDF, return that page as an image
        if page is not None and document.file_type == "application/pdf":
            try:
                # Convert PDF page to image
                kwargs = {"dpi": 300, "first_page": page, "last_page": page}
                if settings.POPPLER_PATH:
                    kwargs["poppler_path"] = settings.POPPLER_PATH
                
                images = convert_from_path(file_path, **kwargs)
                if not images:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Page {page} not found in PDF",
                    )
                
                # Convert PIL Image to bytes
                img = images[0]
                img_bytes = io.BytesIO()
                img.save(img_bytes, format="PNG")
                img_bytes.seek(0)
                
                return Response(
                    content=img_bytes.read(),
                    media_type="image/png",
                    headers={
                        "Content-Disposition": f'inline; filename="page_{page}.png"'
                    },
                )
            except Exception as e:
                logger.error(f"Error converting PDF page to image: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to convert PDF page: {str(e)}",
                )
        
        # Otherwise, return the original file
        return FileResponse(
            path=file_path,
            filename=document.file_name,
            media_type=document.file_type or "application/octet-stream",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error serving document file: {e}",
            error_category=ErrorCategory.SYSTEM_ERROR,
            exc_info=e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to serve document file",
        )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
):
    """Soft delete a document (preserves scanned data and extraction results)."""
    logger.info(f"Soft deleting document: {document_id}")
    
    authz_service = AuthzService()
    
    try:
        result = await db.execute(
            select(Document).where(
                Document.id == document_id,
                Document.workspace_id == current_workspace.id,
                Document.deleted_at.is_(None),  # Only allow deleting non-deleted documents
            )
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found or already deleted",
            )
        
        # Authorization check
        await authz_service.assert_resource_ownership(
            db, current_member.user_id, current_workspace.id, document.workspace_id
        )
        
        if not authz_service.can_perform_action(current_member.role, "delete_document"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to delete documents",
            )
        
        # Soft delete: set deleted_at timestamp
        # This preserves all data: OCR text, metadata, extraction results, logs
        document.deleted_at = datetime.now(timezone.utc)
        document.updated_at = datetime.now(timezone.utc)
        
        await db.commit()
        
        logger.info(
            f"Document soft deleted: {document_id}",
            extra={
                "document_id": str(document_id),
                "workspace_id": str(current_workspace.id),
            },
        )
        
        return None
    except HTTPException:
        raise
    except ProgrammingError as e:
        await db.rollback()
        logger.error(f"Database schema error deleting document: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not properly initialized",
        )
    except OperationalError as e:
        await db.rollback()
        logger.error(f"Database connection error deleting document: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Database error deleting document: {e}", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document",
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Unexpected error deleting document: {e}", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred",
        )

