"""E2E tests for document processing pipeline."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatusEnum
from app.models.template import Template
from app.models.job import Job, JobStatus, JobType
from app.models.extractionresult import ExtractionResult


@pytest.mark.asyncio
async def test_complete_document_extraction_flow(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_workspace: Any,
    test_template: Template,
    sample_pdf_file: Path,
) -> None:
    """Test complete flow: upload document → create job → process → retrieve results."""
    # Upload document
    with open(sample_pdf_file, "rb") as f:
        files = {"file": ("test.pdf", f, "application/pdf")}
        data = {"template_id": str(test_template.id)}
        response = await authenticated_client.post(
            "/api/documents",
            files=files,
            data=data,
        )

    assert response.status_code in (200, 201)
    doc_data = response.json()
    document_id = doc_data["id"]
    assert doc_data["status"] == DocumentStatusEnum.PENDING

    # Verify document was created
    doc_stmt = select(Document).where(Document.id == document_id)
    doc_result = await db_session.execute(doc_stmt)
    document: Document | None = doc_result.scalar_one_or_none()
    assert document is not None
    assert document.workspace_id == test_workspace.id
    assert document.template_id == test_template.id

    # Verify extraction job was created
    job_stmt = select(Job).where(
        Job.type == JobType.DOCUMENT_EXTRACTION,
    ).order_by(Job.created_at.desc()).limit(1)
    job_result = await db_session.execute(job_stmt)
    job: Job | None = job_result.scalar_one_or_none()
    assert job is not None
    assert job.status in (JobStatus.QUEUED, JobStatus.PROCESSING)

    # Retrieve document details
    response = await authenticated_client.get(f"/api/documents/{document_id}")
    assert response.status_code == 200
    doc_data = response.json()
    assert doc_data["id"] == document_id


@pytest.mark.asyncio
async def test_template_creation_and_retrieval(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_workspace: Any,
    test_user: Any,
) -> None:
    """Test create extraction template with field schema."""
    payload: Dict[str, Any] = {
        "name": "Invoice Template",
        "description": "Template for extracting invoice data",
        "document_type": "invoice",
        "field_schema": {
            "vendor_name": {"type": "string", "required": True},
            "invoice_number": {"type": "string", "required": True},
            "total_amount": {"type": "number", "required": True},
            "date": {"type": "string", "required": False},
        },
        "default_export_format": "json",
    }

    response = await authenticated_client.post("/api/templates", json=payload)
    assert response.status_code in (200, 201)
    template_data = response.json()
    template_id = template_data["id"]

    assert template_data["name"] == payload["name"]
    assert template_data["field_schema"] == payload["field_schema"]

    # Retrieve template
    response = await authenticated_client.get(f"/api/templates/{template_id}")
    assert response.status_code == 200
    retrieved_data = response.json()
    assert retrieved_data["id"] == template_id
    assert retrieved_data["name"] == payload["name"]


@pytest.mark.asyncio
async def test_template_update(
    authenticated_client: AsyncClient,
    test_template: Template,
) -> None:
    """Test update existing template."""
    payload = {
        "name": "Updated Template Name",
        "description": "Updated description",
    }

    response = await authenticated_client.put(
        f"/api/templates/{test_template.id}",
        json=payload,
    )
    assert response.status_code == 200
    updated_data = response.json()
    assert updated_data["name"] == payload["name"]
    assert updated_data["description"] == payload["description"]


@pytest.mark.asyncio
async def test_template_test_extraction(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_template: Template,
    test_document: Document,
) -> None:
    """Test running test extraction on template."""
    payload = {
        "test_document_id": str(test_document.id),
    }

    response = await authenticated_client.post(
        f"/api/templates/{test_template.id}/test",
        json=payload,
    )
    # Test extraction might be async, so accept 200 or 202
    assert response.status_code in (200, 202)
    data = response.json()
    assert "message" in data
    assert "template_id" in data


@pytest.mark.asyncio
async def test_template_deletion(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_template: Template,
) -> None:
    """Test template deletion removes associated data appropriately."""
    template_id = test_template.id

    response = await authenticated_client.delete(f"/api/templates/{template_id}")
    assert response.status_code in (200, 204)

    # Verify template is deleted
    template_stmt = select(Template).where(Template.id == template_id)
    template_result = await db_session.execute(template_stmt)
    deleted_template = template_result.scalar_one_or_none()
    assert deleted_template is None


@pytest.mark.asyncio
async def test_document_retry_flow(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_document: Document,
    test_template: Template,
) -> None:
    """Test failed extraction can be retried."""
    # Set document to failed status
    test_document.status = DocumentStatusEnum.FAILED
    await db_session.commit()

    # Retry extraction
    payload = {"template_id": str(test_template.id)}
    response = await authenticated_client.post(
        f"/api/documents/{test_document.id}/retry",
        json=payload,
    )
    assert response.status_code in (200, 201)

    # Verify new job was created
    job_stmt = select(Job).where(
        Job.type == JobType.DOCUMENT_EXTRACTION,
    ).order_by(Job.created_at.desc()).limit(1)
    job_result = await db_session.execute(job_stmt)
    job: Job | None = job_result.scalar_one_or_none()
    assert job is not None


@pytest.mark.asyncio
async def test_export_json_format(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_document: Document,
) -> None:
    """Test export extraction results as JSON."""
    # Create a mock extraction result
    from app.models.extractionresult import ExtractionResult
    from datetime import datetime, timezone

    extraction_result = ExtractionResult(
        document_id=test_document.id,
        template_id=test_document.template_id,
        version=1,
        extracted_data={"test": "data"},
        confidence_score=0.95,
    )
    db_session.add(extraction_result)
    test_document.status = DocumentStatusEnum.COMPLETED
    await db_session.commit()

    # Request export
    response = await authenticated_client.get(
        f"/api/documents/{test_document.id}/export",
        params={"format": "json"},
    )
    # Export might return download URL or file directly
    assert response.status_code in (200, 302)


@pytest.mark.asyncio
async def test_export_csv_format(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_document: Document,
) -> None:
    """Test export as CSV format."""
    from app.models.extractionresult import ExtractionResult

    extraction_result = ExtractionResult(
        document_id=test_document.id,
        template_id=test_document.template_id,
        version=1,
        extracted_data={"field1": "value1", "field2": "value2"},
        confidence_score=0.95,
    )
    db_session.add(extraction_result)
    test_document.status = DocumentStatusEnum.COMPLETED
    await db_session.commit()

    response = await authenticated_client.get(
        f"/api/documents/{test_document.id}/export",
        params={"format": "csv"},
    )
    assert response.status_code in (200, 302)


@pytest.mark.asyncio
async def test_export_excel_format(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_document: Document,
) -> None:
    """Test export as Excel format."""
    from app.models.extractionresult import ExtractionResult

    extraction_result = ExtractionResult(
        document_id=test_document.id,
        template_id=test_document.template_id,
        version=1,
        extracted_data={"field1": "value1", "field2": "value2"},
        confidence_score=0.95,
    )
    db_session.add(extraction_result)
    test_document.status = DocumentStatusEnum.COMPLETED
    await db_session.commit()

    response = await authenticated_client.get(
        f"/api/documents/{test_document.id}/export",
        params={"format": "excel"},
    )
    assert response.status_code in (200, 302)

