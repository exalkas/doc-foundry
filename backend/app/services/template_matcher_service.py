"""Template auto-matching service for documents."""

import logging
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.template import Template

logger = logging.getLogger(__name__)


class TemplateMatcherService:
    """Service for automatically matching documents to templates."""

    def __init__(self):
        """Initialize template matcher service."""
        pass

    async def auto_match_template(
        self, session: AsyncSession, document_id: UUID, workspace_id: UUID
    ) -> Tuple[Optional[Template], float]:
        """Auto-match a document to the best template.

        Args:
            session: Database session
            document_id: Document ID
            workspace_id: Workspace ID

        Returns:
            Tuple of (best matching template or None if no good match found, best_score)
        """
        # Get document
        doc_result = await session.execute(
            select(Document).where(
                Document.id == document_id,
                Document.workspace_id == workspace_id,
            )
        )
        document = doc_result.scalar_one_or_none()

        if not document:
            logger.warning(f"Document {document_id} not found")
            return None, 0.0

        # Get OCR text
        ocr_text = document.raw_ocr_text
        if not ocr_text:
            logger.warning(f"Document {document_id} has no OCR text")
            return None, 0.0

        # Get all templates for workspace
        templates_result = await session.execute(
            select(Template).where(Template.workspace_id == workspace_id)
        )
        templates = templates_result.scalars().all()

        if not templates:
            logger.info(f"No templates found for workspace {workspace_id}")
            return None, 0.0

        # Score each template
        best_match: Optional[Tuple[Template, float]] = None
        best_score = 0.0

        for template in templates:
            score = self._calculate_match_score(ocr_text, template)
            if score > best_score:
                best_score = score
                best_match = (template, score)

        # Only return if score is above threshold
        if best_match and best_score >= 0.3:  # 30% similarity threshold
            logger.info(
                f"Matched document {document_id} to template {best_match[0].id} "
                f"with score {best_score:.2f}"
            )
            return best_match[0], best_score

        logger.info(
            f"No good template match found for document {document_id} "
            f"(best score: {best_score:.2f})"
        )
        return None, best_score

    def _calculate_match_score(self, ocr_text: str, template: Template) -> float:
        """Calculate similarity score between OCR text and template.

        Args:
            ocr_text: Extracted OCR text
            template: Template to match against

        Returns:
            Similarity score between 0.0 and 1.0
        """
        # Simple keyword-based matching
        # Extract keywords from template name and description
        template_text = f"{template.name} {template.description or ''} {template.document_type or ''}".lower()
        
        # Extract field names from template schema
        field_schema = template.field_schema or {}
        fields = field_schema.get("fields", []) or field_schema.get("properties", {})
        
        if isinstance(fields, list):
            field_names = [f.get("name", "") or f.get("json_key", "") for f in fields if isinstance(f, dict)]
        elif isinstance(fields, dict):
            field_names = list(fields.keys())
        else:
            field_names = []
        
        template_keywords = set(template_text.split())
        template_keywords.update([f.lower() for f in field_names if f])
        
        # Extract keywords from OCR text
        ocr_lower = ocr_text.lower()
        ocr_words = set(ocr_lower.split())
        
        # Calculate Jaccard similarity
        intersection = len(template_keywords.intersection(ocr_words))
        union = len(template_keywords.union(ocr_words))
        
        if union == 0:
            return 0.0
        
        jaccard_score = intersection / union
        
        # Boost score if document_type matches
        if template.document_type:
            doc_type_lower = template.document_type.lower()
            if doc_type_lower in ocr_lower:
                jaccard_score += 0.2
        
        # Normalize to 0-1 range
        return min(jaccard_score, 1.0)

