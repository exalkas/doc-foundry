"""Exports router endpoints for downloading exported files."""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    get_current_workspace,
    get_current_workspace_member,
)
from app.database import get_db
from app.services.export_service import ExportService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/download")
async def download_export(
    path: str = Query(..., description="Export file path"),
    token: str = Query(..., description="Download token"),
    db: AsyncSession = Depends(get_db),
    current_workspace = Depends(get_current_workspace),
    current_member = Depends(get_current_workspace_member),
):
    """Download an exported file."""
    export_service = ExportService()
    
    # Verify the path belongs to the current workspace
    if not path.startswith(f"{current_workspace.id}/exports/"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    try:
        file_content = await export_service.get_export_file(path)
        
        # Determine content type based on file extension
        if path.endswith(".json"):
            media_type = "application/json"
        elif path.endswith(".csv"):
            media_type = "text/csv"
        elif path.endswith(".xlsx"):
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            media_type = "application/octet-stream"
        
        # Extract filename from path
        filename = path.split("/")[-1]
        
        return Response(
            content=file_content,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except Exception as e:
        logger.error(f"Error downloading export: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export file not found",
        )

