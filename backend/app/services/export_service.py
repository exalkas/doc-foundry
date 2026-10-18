"""Export service for generating JSON/CSV/Excel exports from extraction results."""

import csv
import io
import json
import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

import openpyxl
from openpyxl import Workbook
from openpyxl.styles import Font

from app.config import settings
from app.core.storage import StorageService

logger = logging.getLogger(__name__)


class ExportError(Exception):
    """Base exception for export errors."""

    pass


class ExportService:
    """Service for generating exports from extraction results."""

    # Export expiration (24 hours)
    EXPORT_EXPIRATION_HOURS = 24

    def __init__(self, storage_service: Optional[StorageService] = None):
        """Initialize export service.

        Args:
            storage_service: Storage service instance
        """
        self.storage = storage_service or StorageService(settings.STORAGE_ROOT)
        self.exports_base = Path(settings.STORAGE_ROOT) / "exports"

    async def export_to_json(
        self,
        extraction_results: List[Dict[str, Any]],
        workspace_id: UUID,
    ) -> str:
        """Export extraction results to JSON format.

        Args:
            extraction_results: List of extraction result dictionaries
            workspace_id: Workspace ID

        Returns:
            Storage path to exported file
        """
        export_data = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "workspace_id": str(workspace_id),
            "count": len(extraction_results),
            "results": extraction_results,
        }

        json_content = json.dumps(export_data, indent=2, default=str)

        # Generate unique filename
        export_id = uuid.uuid4()
        filename = f"export_{export_id}.json"
        export_path = f"{workspace_id}/exports/{filename}"

        # Save to storage
        await self.storage.upload(export_path, json_content.encode("utf-8"))

        logger.info(
            "Exported %d results to JSON: %s",
            len(extraction_results),
            export_path,
        )

        return export_path

    async def export_to_csv(
        self,
        extraction_results: List[Dict[str, Any]],
        workspace_id: UUID,
    ) -> str:
        """Export extraction results to CSV format.

        Args:
            extraction_results: List of extraction result dictionaries
            workspace_id: Workspace ID

        Returns:
            Storage path to exported file
        """
        if not extraction_results:
            raise ExportError("No extraction results to export")

        # Collect all unique field names
        all_fields = set()
        for result in extraction_results:
            extracted_json = result.get("extracted_json", {})
            if isinstance(extracted_json, dict):
                all_fields.update(extracted_json.keys())

        field_names = sorted(list(all_fields))

        # Create CSV content
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=["document_id", "template_id", "version", "created_at"] + field_names,
        )
        writer.writeheader()

        for result in extraction_results:
            row = {
                "document_id": result.get("document_id", ""),
                "template_id": result.get("template_id", ""),
                "version": result.get("version", ""),
                "created_at": result.get("created_at", ""),
            }
            extracted_json = result.get("extracted_json", {})
            if isinstance(extracted_json, dict):
                row.update(extracted_json)
            writer.writerow(row)

        csv_content = output.getvalue().encode("utf-8")

        # Generate unique filename
        export_id = uuid.uuid4()
        filename = f"export_{export_id}.csv"
        export_path = f"{workspace_id}/exports/{filename}"

        # Save to storage
        await self.storage.upload(export_path, csv_content)

        logger.info(
            "Exported %d results to CSV: %s",
            len(extraction_results),
            export_path,
        )

        return export_path

    async def export_to_excel(
        self,
        extraction_results: List[Dict[str, Any]],
        workspace_id: UUID,
    ) -> str:
        """Export extraction results to Excel format.

        Args:
            extraction_results: List of extraction result dictionaries
            workspace_id: Workspace ID

        Returns:
            Storage path to exported file
        """
        if not extraction_results:
            raise ExportError("No extraction results to export")

        # Create workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Extraction Results"

        # Collect all unique field names
        all_fields = set()
        for result in extraction_results:
            extracted_json = result.get("extracted_json", {})
            if isinstance(extracted_json, dict):
                all_fields.update(extracted_json.keys())

        field_names = sorted(list(all_fields))

        # Write header
        headers = ["Document ID", "Template ID", "Version", "Created At"] + field_names
        ws.append(headers)

        # Style header row
        header_font = Font(bold=True)
        for cell in ws[1]:
            cell.font = header_font

        # Write data rows
        for result in extraction_results:
            row = [
                str(result.get("document_id", "")),
                str(result.get("template_id", "")),
                result.get("version", ""),
                result.get("created_at", ""),
            ]
            extracted_json = result.get("extracted_json", {})
            if isinstance(extracted_json, dict):
                for field in field_names:
                    value = extracted_json.get(field, "")
                    # Convert to string for Excel
                    row.append(str(value) if value is not None else "")
            else:
                row.extend([""] * len(field_names))
            ws.append(row)

        # Save to bytes
        output = io.BytesIO()
        wb.save(output)
        excel_content = output.getvalue()

        # Generate unique filename
        export_id = uuid.uuid4()
        filename = f"export_{export_id}.xlsx"
        export_path = f"{workspace_id}/exports/{filename}"

        # Save to storage
        await self.storage.upload(export_path, excel_content)

        logger.info(
            "Exported %d results to Excel: %s",
            len(extraction_results),
            export_path,
        )

        return export_path

    def generate_signed_url(
        self,
        export_path: str,
        expiration_hours: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate a signed URL for downloading an export.

        Args:
            export_path: Storage path to export file
            expiration_hours: URL expiration in hours (default: 24)

        Returns:
            Dict with download_url and expires_at
        """
        expiration_hours = expiration_hours or self.EXPORT_EXPIRATION_HOURS
        expires_at = datetime.now(timezone.utc) + timedelta(hours=expiration_hours)

        # Generate signed token
        token_data = f"{export_path}:{expires_at.isoformat()}"
        token = secrets.token_urlsafe(32)

        # In a production system, you'd sign this token properly
        # For now, we'll use a simple approach
        download_url = f"/api/exports/download?path={export_path}&token={token}"

        return {
            "download_url": download_url,
            "expires_at": expires_at.isoformat(),
            "path": export_path,
        }

    async def get_export_file(
        self,
        export_path: str,
    ) -> bytes:
        """Get export file content.

        Args:
            export_path: Storage path to export file

        Returns:
            File content as bytes
        """
        return await self.storage.download(export_path)

