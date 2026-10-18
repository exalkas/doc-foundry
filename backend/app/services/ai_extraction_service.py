"""AI/LLM-based extraction service (optional)."""

import logging
from typing import Any, Dict, Optional, Tuple

from app.services.extraction_service import ExtractionResult, ExtractionService

logger = logging.getLogger(__name__)


class AIExtractionService:
    """Service for LLM-based document extraction (optional feature)."""

    def __init__(self, extraction_service: Optional[ExtractionService] = None):
        """Initialize AI extraction service.

        Args:
            extraction_service: Base extraction service for OCR
        """
        self.extraction_service = extraction_service or ExtractionService()

    async def extract_with_llm(
        self,
        ocr_text: str,
        template: Any,
        image_path: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], float]:
        """Extract structured data using LLM.

        Args:
            ocr_text: Text extracted from OCR
            template: Template model with field_schema
            image_path: Optional path to image for vision models

        Returns:
            Tuple of (extracted_data, confidence_score)

        Note:
            This is a placeholder implementation. In production, integrate with:
            - OpenAI GPT-4 Vision
            - Anthropic Claude
            - Google Gemini
            - Or other LLM APIs
        """
        logger.info("LLM extraction (placeholder): template=%s", template.id if hasattr(template, "id") else "unknown")

        # Placeholder: In production, this would:
        # 1. Build prompt from template field_schema
        # 2. Call LLM API with OCR text (and optionally image)
        # 3. Parse structured response
        # 4. Return extracted data with confidence

        # For now, fall back to rule-based extraction
        field_schema = template.field_schema if hasattr(template, "field_schema") else {}
        fields = field_schema.get("fields", []) or field_schema.get("properties", [])

        extracted_data: Dict[str, Any] = {}
        for field_def in fields:
            if isinstance(field_def, dict):
                field_name = (
                    field_def.get("name")
                    or field_def.get("json_key")
                    or field_def.get("key")
                )
                if field_name:
                    # Use template service for extraction
                    from app.services.template_service import TemplateService
                    template_service = TemplateService()
                    value, _ = template_service.extract_field_value(ocr_text, field_def)
                    extracted_data[field_name] = value

        # LLM extraction typically has higher confidence
        confidence = 0.85

        return extracted_data, confidence

    async def extract_hybrid(
        self,
        file_path: str,
        template: Any,
        use_llm: bool = False,
        ocr_language: str = "eng",
    ) -> ExtractionResult:
        """Extract using hybrid approach (rule-based + LLM fallback).

        Args:
            file_path: Path to document file
            template: Template model
            use_llm: Whether to use LLM for extraction
            ocr_language: Language code (e.g., 'eng', 'ell' for Greek, 'en', 'el')

        Returns:
            ExtractionResult
        """
        # First, perform OCR
        from pathlib import Path
        ocr_text, ocr_metadata = await self.extraction_service._perform_ocr(
            file_path, Path(file_path).suffix.lower(), ocr_language
        )

        # Then extract using chosen method
        if use_llm:
            extracted_data, confidence = await self.extract_with_llm(ocr_text, template, file_path)
        else:
            # Use rule-based extraction
            extracted_data, field_confidences = await self.extraction_service._apply_template(
                ocr_text, template
            )
            confidence = self.extraction_service._calculate_confidence(field_confidences)

        # Build result
        needs_review = confidence < self.extraction_service.CONFIDENCE_THRESHOLD_MEDIUM

        return ExtractionResult(
            extracted_data=extracted_data,
            confidence=confidence,
            needs_review=needs_review,
            metadata={
                "engine": "llm" if use_llm else "rule-based",
                "ocr_metadata": ocr_metadata,
            },
            errors=[],
            warnings=[],
        )

