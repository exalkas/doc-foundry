"""Document extraction service with real OCR integration."""

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings
from app.core.storage import StorageService, StorageError
from app.services.plan_service import PlanService
from app.services.google_vision_service import GoogleVisionService, OCRProcessingError
from app.services.ocr_language_mapper import map_language_code

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Result of document extraction."""

    extracted_data: Dict[str, Any]
    confidence: float
    needs_review: bool
    metadata: Dict[str, Any]
    errors: List[str]
    warnings: List[str]


class ExtractionError(Exception):
    """Base exception for extraction errors."""

    pass


class UnsupportedFileTypeError(ExtractionError):
    """Raised when file type is not supported for extraction."""

    pass


class OCRProcessingError(ExtractionError):
    """Raised when OCR processing fails."""

    pass


class ExtractionService:
    """Service for extracting structured data from documents using OCR."""

    # Supported file types
    SUPPORTED_IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".gif"}
    SUPPORTED_PDF_TYPES = {".pdf"}
    
    # Confidence thresholds
    CONFIDENCE_THRESHOLD_LOW = 0.3  # 30% - used when validation fails
    CONFIDENCE_THRESHOLD_MEDIUM = 0.6  # 60% - used to determine if review is needed
    CONFIDENCE_THRESHOLD_HIGH = 0.8  # 80% - high confidence threshold

    def __init__(self, storage_service: Optional[StorageService] = None, plan_service: Optional[PlanService] = None):
        """Initialize extraction service.

        Args:
            storage_service: Storage service for file access. If None, creates default.
            plan_service: Plan service for confidence thresholds. If None, creates default.
        """
        self.storage = storage_service or StorageService(settings.STORAGE_ROOT)
        self.plan_service = plan_service or PlanService()
        self.vision_service = GoogleVisionService()

    async def extract(
        self,
        file_path: str,
        template: Any,
        timeout_seconds: int = 300,
        plan_tier: str = "free",
        ocr_language: str = "eng",
    ) -> ExtractionResult:
        """Extract structured data from a document using OCR and template.

        Args:
            file_path: Path to the document file
            template: Template model with field_schema
            timeout_seconds: Maximum time to spend on extraction

        Returns:
            ExtractionResult with extracted data, confidence, and metadata

        Raises:
            UnsupportedFileTypeError: If file type is not supported
            OCRProcessingError: If OCR processing fails
        """
        template_id = template.id if hasattr(template, "id") else "unknown"
        logger.info(
            f"Starting extraction for file: {file_path}, template: {template_id}"
        )

        start_time = datetime.now(timezone.utc)
        errors: List[str] = []
        warnings: List[str] = []

        try:
            # Resolve file path
            try:
                full_path = self.storage.resolve_path(file_path)
            except StorageError as e:
                raise ExtractionError(f"Invalid storage path: {str(e)}") from e
            
            if not Path(full_path).exists():
                raise ExtractionError(f"File not found: {full_path}")

            # Get file extension
            ext = Path(full_path).suffix.lower()
            if ext not in self.SUPPORTED_IMAGE_TYPES | self.SUPPORTED_PDF_TYPES:
                raise UnsupportedFileTypeError(
                    f"Unsupported file type: {ext}. "
                    f"Supported: {', '.join(self.SUPPORTED_IMAGE_TYPES | self.SUPPORTED_PDF_TYPES)}"
                )

            # Extract text using OCR
            try:
                ocr_text, ocr_metadata = await asyncio.wait_for(
                    self._perform_ocr(full_path, ext, ocr_language),
                    timeout=timeout_seconds,
                )
            except asyncio.TimeoutError:
                raise OCRProcessingError(f"OCR processing timed out after {timeout_seconds}s")
            except Exception as e:
                logger.exception("OCR processing failed: %s", e)
                raise OCRProcessingError(f"OCR processing failed: {str(e)}") from e

            # Check if template is AI-generated
            is_ai_generated = self._is_ai_generated_template(template)
            
            # Extract structured data using template
            try:
                # For AI-generated templates, try AI extraction first if available
                if is_ai_generated:
                    extracted_data, field_confidences = await self._try_ai_extraction_first(
                        ocr_text, template, file_path
                    )
                else:
                    # Regular regex-based extraction
                    extracted_data, field_confidences = await self._apply_template(
                        ocr_text, template
                    )
                
                # If extraction returned empty results and template is AI-generated, try AI extraction as fallback
                if not extracted_data and is_ai_generated:
                    logger.info("Regex extraction returned empty results for AI-generated template, trying AI extraction as fallback")
                    extracted_data, field_confidences = await self._try_ai_extraction_fallback(
                        ocr_text, template, file_path
                    )
                
                if not extracted_data:
                    warnings.append("No fields were extracted from the document. Check if template fields match the document structure.")
                    logger.warning(
                        f"No fields extracted for template {template.id if hasattr(template, 'id') else 'unknown'}. "
                        f"OCR text length: {len(ocr_text)}, Template fields: {len(template.field_schema.get('fields', []) if hasattr(template, 'field_schema') else [])}"
                    )
            except Exception as e:
                logger.exception("Template application failed: %s", e)
                errors.append(f"Template application failed: {str(e)}")
                extracted_data = {}
                field_confidences = {}

            # Calculate overall confidence
            overall_confidence = self._calculate_confidence(field_confidences)

            # Get plan-based confidence threshold
            confidence_threshold = self.plan_service.get_confidence_threshold(plan_tier)

            # Determine if review is needed based on plan threshold
            needs_review = (
                overall_confidence < confidence_threshold
                or len(errors) > 0
                or self._has_validation_failures(extracted_data, template)
            )

            # Build metadata
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            # Include OCR text in ocr_metadata for easy access
            ocr_metadata_with_text = {
                **ocr_metadata,
                "text": ocr_text,  # Store OCR text in metadata for worker access
            }
            metadata = {
                "engine": "google_vision",
                "template_id": str(template.id) if hasattr(template, "id") else None,
                "file_path": file_path,
                "file_type": ext,
                "processing_time_seconds": processing_time,
                "ocr_metadata": ocr_metadata_with_text,
                "field_count": len(extracted_data),
                "field_confidences": field_confidences,
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }

            logger.info(
                "Extraction completed: confidence=%.2f, needs_review=%s, fields=%d",
                overall_confidence,
                needs_review,
                len(extracted_data),
            )

            return ExtractionResult(
                extracted_data=extracted_data,
                confidence=overall_confidence,
                needs_review=needs_review,
                metadata=metadata,
                errors=errors,
                warnings=warnings,
            )

        except ExtractionError:
            raise
        except Exception as e:
            logger.exception("Unexpected error during extraction: %s", e)
            raise ExtractionError(f"Extraction failed: {str(e)}") from e

    async def _perform_ocr(self, file_path: str, ext: str, lang: str = "eng") -> Tuple[str, Dict[str, Any]]:
        """Perform OCR on a file using Google Cloud Vision API.

        Args:
            file_path: Full path to the file
            ext: File extension
            lang: Language code (e.g., 'eng', 'ell' for Greek, 'fra' for French)
                 Will be mapped to Google Vision language hints

        Returns:
            Tuple of (extracted text, metadata)

        Raises:
            OCRProcessingError: If OCR processing fails
        """
        try:
            # Map language code to Google Vision format
            language_hints = map_language_code(lang)

            # Perform OCR based on file type
            if ext in self.SUPPORTED_PDF_TYPES:
                ocr_text, ocr_metadata = await self.vision_service.detect_text_from_pdf(
                    file_path, language_hints
                )
            else:
                ocr_text, ocr_metadata = await self.vision_service.detect_text(
                    file_path, language_hints
                )

            # Ensure metadata structure matches expected format
            ocr_metadata["ocr_language"] = lang  # Preserve original language code
            ocr_metadata["engine"] = "google_vision"

            # Calculate overall confidence from blocks if available
            if ocr_metadata.get("blocks"):
                ocr_metadata["confidence"] = self._calculate_confidence_from_blocks(
                    ocr_metadata["blocks"]
                )
            else:
                ocr_metadata["confidence"] = 1.0  # Default high confidence for Google Vision

            return ocr_text, ocr_metadata

        except OCRProcessingError:
            raise
        except Exception as e:
            error_msg = str(e)
            logger.exception(f"Google Vision OCR failed for {file_path}: {error_msg}")
            raise OCRProcessingError(
                f"Google Vision OCR processing failed: {error_msg}. "
                "Please verify GOOGLE_CLOUD_PROJECT_ID is set and credentials are configured. "
                "See GOOGLE_VISION_SETUP.md for setup instructions."
            ) from e

    def _calculate_confidence_from_blocks(self, blocks: List[Dict[str, Any]]) -> float:
        """Calculate overall confidence score from OCR blocks.

        Args:
            blocks: List of block dictionaries with confidence scores

        Returns:
            Average confidence score (0.0 to 1.0)
        """
        if not blocks:
            return 0.0

        confidences = [
            block.get("confidence", 1.0) for block in blocks if block.get("confidence") is not None
        ]

        if confidences:
            return sum(confidences) / len(confidences)

        # Default to high confidence for Google Vision (doesn't provide per-block confidence)
        return 1.0

    async def _apply_template(
        self, ocr_text: str, template: Any
    ) -> Tuple[Dict[str, Any], Dict[str, float]]:
        """Apply template field schema to extracted text.

        Args:
            ocr_text: Text extracted from OCR
            template: Template model with field_schema

        Returns:
            Tuple of (extracted data dict, field confidence dict)
        """
        import json
        
        field_schema = template.field_schema if hasattr(template, "field_schema") else {}
        fields = field_schema.get("fields", [])
        if not fields:
            # Try alternative schema format
            fields = field_schema.get("properties", [])

        extracted_data: Dict[str, Any] = {}
        field_confidences: Dict[str, float] = {}
        
        # #region agent log
        log_path = r"e:\BACKUP\Apps\alkassoftware\7sevens\.cursor\debug.log"
        try:
            # Log template structure
            field_summaries = []
            for f in fields[:10]:  # First 10 fields
                if isinstance(f, dict):
                    field_summaries.append({
                        "name": f.get("name"),
                        "json_key": f.get("json_key"),
                        "strategy": f.get("strategy"),
                        "has_anchor": "anchor" in f or "anchor_text" in f,
                        "has_anchor_texts": "anchor_texts" in f,
                        "anchor_keys": [k for k in f.keys() if "anchor" in k.lower()]
                    })
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "A",
                    "location": "extraction_service.py:_apply_template:start",
                    "message": "Template application started",
                    "data": {
                        "template_id": str(template.id) if hasattr(template, "id") else None,
                        "fields_count": len(fields),
                        "ocr_text_length": len(ocr_text),
                        "ocr_text_sample": ocr_text[:300],
                        "field_summaries": field_summaries
                    },
                    "timestamp": int(time.time() * 1000)
                }) + "\n")
        except Exception:
            pass
        # #endregion
        
        # Log OCR text sample for debugging
        ocr_sample = ocr_text[:500] if len(ocr_text) > 500 else ocr_text
        logger.debug(f"Applying template to OCR text (length: {len(ocr_text)}, sample: {ocr_sample[:200]}...)")
        logger.debug(f"Template has {len(fields)} fields to extract")

        for field_def in fields:
            if isinstance(field_def, dict):
                field_name = field_def.get("name") or field_def.get("json_key") or field_def.get("key")
                if not field_name:
                    logger.debug(f"Skipping field without name/json_key/key: {field_def}")
                    continue

                # Extract field value based on extraction strategy
                # Default to "anchor" if anchor_texts or anchor is present, otherwise "regex"
                default_strategy = "anchor" if (
                    field_def.get("anchor_texts") or 
                    field_def.get("anchor") or 
                    field_def.get("anchor_text")
                ) else "regex"
                strategy = field_def.get("strategy", default_strategy)
                logger.debug(f"Extracting field '{field_name}' using strategy '{strategy}'")
                
                value, confidence = await self._extract_field_value(
                    ocr_text, field_def, strategy
                )

                # Log extraction result
                if value is None:
                    logger.debug(
                        f"Field '{field_name}' extraction failed (strategy: {strategy}, confidence: {confidence})"
                    )
                else:
                    logger.debug(
                        f"Field '{field_name}' extracted successfully: '{value[:100] if isinstance(value, str) and len(str(value)) > 100 else value}' (confidence: {confidence:.2f})"
                    )

                # Apply post-processing
                value = self._post_process_field(value, field_def)

                # Validate field
                if not self._validate_field(value, field_def):
                    confidence = min(confidence, self.CONFIDENCE_THRESHOLD_LOW)
                    logger.debug(f"Field '{field_name}' validation failed, confidence reduced to {confidence:.2f}")

                extracted_data[field_name] = value
                field_confidences[field_name] = confidence

        # Log summary
        successful_fields = sum(1 for v in extracted_data.values() if v is not None)
        logger.info(
            f"Template application completed: {successful_fields}/{len(fields)} fields extracted successfully"
        )
        
        # #region agent log
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "A",
                    "location": "extraction_service.py:_apply_template:complete",
                    "message": "Template application completed",
                    "data": {
                        "fields_total": len(fields),
                        "fields_extracted": successful_fields,
                        "extracted_data": {k: (str(v)[:100] if isinstance(v, str) and len(str(v)) > 100 else v) for k, v in list(extracted_data.items())[:10]},
                        "field_confidences": {k: v for k, v in list(field_confidences.items())[:10]}
                    },
                    "timestamp": int(time.time() * 1000)
                }) + "\n")
        except Exception:
            pass
        # #endregion
        
        return extracted_data, field_confidences

    async def _extract_field_value(
        self, text: str, field_def: Dict[str, Any], strategy: str
    ) -> Tuple[Any, float]:
        """Extract a single field value from text.

        Args:
            text: OCR extracted text
            field_def: Field definition from template
            strategy: Extraction strategy (regex, anchor, ml)

        Returns:
            Tuple of (extracted value, confidence score)
        """
        if strategy == "regex":
            return self._extract_by_regex(text, field_def)
        elif strategy == "anchor":
            return self._extract_by_anchor(text, field_def)
        else:
            # Default: try to find by field name
            return self._extract_by_name(text, field_def)

    def _extract_by_regex(self, text: str, field_def: Dict[str, Any]) -> Tuple[Any, float]:
        """Extract field value using regex pattern.

        Args:
            text: OCR text
            field_def: Field definition with regex pattern

        Returns:
            Tuple of (value, confidence)
        """
        pattern = field_def.get("pattern") or field_def.get("regex")
        field_name = field_def.get("name") or field_def.get("json_key") or "unknown"
        
        if not pattern:
            logger.debug(f"Field '{field_name}': No regex pattern provided")
            return None, 0.0

        try:
            # Use Unicode-aware matching for multilingual support
            flags = re.IGNORECASE | re.MULTILINE | re.UNICODE
            matches = re.findall(pattern, text, flags)
            
            if matches:
                value = matches[0] if isinstance(matches[0], str) else str(matches[0])
                logger.debug(
                    f"Field '{field_name}': Regex pattern matched successfully. "
                    f"Pattern: '{pattern}', Matched: '{value[:100] if len(str(value)) > 100 else value}'"
                )
                return value, 0.8
            else:
                # Log why pattern didn't match - show sample of text around potential matches
                logger.debug(
                    f"Field '{field_name}': Regex pattern did not match. "
                    f"Pattern: '{pattern}'. "
                    f"OCR text sample (first 500 chars): {text[:500]}"
                )
                return None, 0.0
        except re.error as e:
            logger.warning(
                f"Field '{field_name}': Invalid regex pattern '{pattern}': {str(e)}"
            )
            return None, 0.0

    def _extract_by_anchor(self, text: str, field_def: Dict[str, Any]) -> Tuple[Any, float]:
        """Extract field value using anchor text with multilingual support.

        Args:
            text: OCR text
            field_def: Field definition with anchor text(s)

        Returns:
            Tuple of (value, confidence)
        """
        import json
        import os
        
        field_name = field_def.get("name") or field_def.get("json_key") or "unknown"
        
        # #region agent log
        log_path = r"e:\BACKUP\Apps\alkassoftware\7sevens\.cursor\debug.log"
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "A",
                    "location": "extraction_service.py:_extract_by_anchor:entry",
                    "message": "Anchor extraction started",
                    "data": {
                        "field_name": field_name,
                        "strategy": field_def.get("strategy"),
                        "has_anchor": "anchor" in field_def or "anchor_text" in field_def,
                        "has_anchor_texts": "anchor_texts" in field_def,
                        "field_def_keys": list(field_def.keys())
                    },
                    "timestamp": int(time.time() * 1000)
                }) + "\n")
        except Exception:
            pass
        # #endregion
        
        # Support multiple anchor formats:
        # 1. Single anchor string: "anchor" or "anchor_text"
        # 2. Multiple anchors array: "anchor_texts" (try all until one matches)
        # 3. Language-specific anchors: "anchor_en", "anchor_el", etc.
        anchors_to_try = []
        
        # Check for anchor_texts array (multilingual support)
        if "anchor_texts" in field_def and isinstance(field_def["anchor_texts"], list):
            # Filter out empty strings
            valid_anchors = [a for a in field_def["anchor_texts"] if a and isinstance(a, str) and a.strip()]
            anchors_to_try.extend(valid_anchors)
        
        # Check for language-specific anchors (e.g., anchor_en, anchor_el)
        for key in field_def.keys():
            if key.startswith("anchor_") and key not in ["anchor_text", "anchor_texts"]:
                anchor_value = field_def[key]
                if anchor_value and isinstance(anchor_value, str) and anchor_value.strip():
                    anchors_to_try.append(anchor_value)
        
        # Check for single anchor (backward compatibility)
        single_anchor = field_def.get("anchor") or field_def.get("anchor_text")
        if single_anchor and isinstance(single_anchor, str) and single_anchor.strip():
            anchors_to_try.append(single_anchor)
        
        if not anchors_to_try:
            logger.warning(
                f"Field '{field_name}': No valid anchor text provided for anchor strategy. "
                f"Field definition keys: {list(field_def.keys())}"
            )
            return None, 0.0
        
        logger.debug(
            f"Field '{field_name}': Found {len(anchors_to_try)} anchor(s) to try: {[a[:50] for a in anchors_to_try[:3]]}"
        )
        
        # #region agent log
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "A",
                    "location": "extraction_service.py:_extract_by_anchor:anchors_collected",
                    "message": "Anchors collected for field",
                    "data": {
                        "field_name": field_name,
                        "anchors_count": len(anchors_to_try),
                        "anchors": anchors_to_try[:5],
                        "ocr_text_length": len(text),
                        "ocr_text_sample": text[:200] if len(text) > 200 else text
                    },
                    "timestamp": int(time.time() * 1000)
                }) + "\n")
        except Exception:
            pass
        # #endregion
        
        if not anchors_to_try:
            logger.debug(f"Field '{field_name}': No anchor text provided")
            return None, 0.0

        logger.debug(
            f"Field '{field_name}': Trying {len(anchors_to_try)} anchor(s): {anchors_to_try[:3]}..."
        )

        # Try each anchor until one matches
        for anchor_idx, anchor in enumerate(anchors_to_try):
            if not anchor or not isinstance(anchor, str):
                continue
            
            # #region agent log
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "B",
                        "location": "extraction_service.py:_extract_by_anchor:trying_anchor",
                        "message": "Trying anchor",
                        "data": {
                            "field_name": field_name,
                            "anchor_index": anchor_idx,
                            "anchor": anchor,
                            "anchor_length": len(anchor)
                        },
                        "timestamp": int(time.time() * 1000)
                    }) + "\n")
            except Exception:
                pass
            # #endregion
            
            # Try multiple matching strategies for robustness
            import re
            anchor_pos = -1
            actual_anchor_len = len(anchor)
            use_normalized = False
            
            # Strategy 1: Exact case-insensitive match
            text_lower = text.lower()
            anchor_lower = anchor.lower()
            anchor_pos = text_lower.find(anchor_lower)
            
            # Strategy 2: Normalize whitespace and try again
            if anchor_pos == -1:
                normalized_anchor = re.sub(r'\s+', ' ', anchor.strip())
                normalized_text = re.sub(r'\s+', ' ', text)
                text_lower_norm = normalized_text.lower()
                anchor_lower_norm = normalized_anchor.lower()
                anchor_pos_norm = text_lower_norm.find(anchor_lower_norm)
                
                if anchor_pos_norm != -1:
                    # Map back to original text position (approximate)
                    # Find the anchor in original text using regex with flexible whitespace
                    anchor_pattern = re.escape(anchor)
                    anchor_pattern = re.sub(r'\\s+', r'\\s+', anchor_pattern)  # Make spaces flexible
                    match = re.search(anchor_pattern, text, re.IGNORECASE)
                    if match:
                        anchor_pos = match.start()
                        actual_anchor_len = match.end() - match.start()
                        use_normalized = True
            
            # Strategy 3: Try with flexible whitespace using regex
            if anchor_pos == -1:
                # Create pattern that allows flexible whitespace
                anchor_escaped = re.escape(anchor.strip())
                # Replace escaped spaces with flexible whitespace pattern
                anchor_pattern = re.sub(r'\\ ', r'\\s+', anchor_escaped)
                match = re.search(anchor_pattern, text, re.IGNORECASE)
                if match:
                    anchor_pos = match.start()
                    actual_anchor_len = match.end() - match.start()
                    use_normalized = False
            
            # #region agent log
            try:
                context_start = max(0, anchor_pos - 50) if anchor_pos != -1 else 0
                context_end = min(len(text), anchor_pos + len(anchor) + 100) if anchor_pos != -1 else 200
                context_text = text[context_start:context_end] if anchor_pos != -1 else text[:200]
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "B",
                        "location": "extraction_service.py:_extract_by_anchor:anchor_search",
                        "message": "Anchor search result",
                        "data": {
                            "field_name": field_name,
                            "anchor": anchor,
                            "anchor_found": anchor_pos != -1,
                            "anchor_position": anchor_pos,
                            "context_text": context_text
                        },
                        "timestamp": int(time.time() * 1000)
                    }) + "\n")
            except Exception:
                pass
            # #endregion
            
            if anchor_pos == -1:
                logger.warning(
                    f"Field '{field_name}': Anchor '{anchor}' not found in text. "
                    f"Tried exact match, normalized whitespace, and flexible regex."
                )
                # Log a sample of the OCR text to help debug
                logger.debug(f"Field '{field_name}': OCR text sample (first 1000 chars): {text[:1000]}")
                # Log what we're searching for
                logger.debug(f"Field '{field_name}': Searching for anchor (length {len(anchor)}): '{anchor[:100]}'")
                continue

            # Extract text after anchor using the actual anchor length we found
            after_anchor = text[anchor_pos + actual_anchor_len:].strip()
            logger.debug(
                f"Field '{field_name}': Found anchor '{anchor[:50]}...' at position {anchor_pos}, "
                f"extracting from position {anchor_pos + actual_anchor_len}"
            )
            
            # #region agent log
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "E",
                        "location": "extraction_service.py:_extract_by_anchor:before_extraction",
                        "message": "Before value extraction",
                        "data": {
                            "field_name": field_name,
                            "anchor": anchor,
                            "after_anchor_preview": after_anchor[:300],
                            "after_anchor_length": len(after_anchor)
                        },
                        "timestamp": int(time.time() * 1000)
                    }) + "\n")
            except Exception:
                pass
            # #endregion
            
            # Extract value - handle multiple formats:
            # 1. Value on same line: "Label: Value" or "Label Value"
            # 2. Value on next line
            # 3. Stop at field boundaries (parenthesized codes like (A), (B), (C.1.1), etc.)
            value = ""
            import re
            
            # Pattern to detect field boundaries: parenthesized codes like (A), (B), (C.1.1), etc.
            # Match patterns like (A), (B), (C.1.1), (C.1.2), etc. at start of line or after whitespace
            field_boundary_pattern = re.compile(r'\s*\([A-Z0-9.]+\)\s*', re.MULTILINE)
            
            # Find the next field boundary to limit extraction scope
            # Look for field codes that appear after the anchor (not immediately after, but as next field marker)
            # We want to find patterns like " (A) ", " (B) ", " (C.1.1) " etc.
            # Also look for common field separators like newlines with field codes
            boundary_match = field_boundary_pattern.search(after_anchor)
            extraction_limit = len(after_anchor)
            
            if boundary_match:
                boundary_pos = boundary_match.start()
                # Check if this boundary is likely a next field marker
                # It should be preceded by whitespace/newline and followed by text
                before_boundary = after_anchor[max(0, boundary_pos-5):boundary_pos]
                after_boundary_text = after_anchor[boundary_match.end():boundary_match.end()+20]
                
                # If boundary is preceded by newline or significant whitespace, it's likely a field marker
                # But if it's immediately after anchor with little content, it might be part of current field
                if boundary_pos > 5:  # At least 5 chars before boundary
                    # Check if there's meaningful content before the boundary
                    text_before = after_anchor[:boundary_pos].strip()
                    if len(text_before) > 3:  # There's actual content before boundary
                        extraction_limit = boundary_pos
                    else:
                        # Too little content, look for next boundary
                        next_match = field_boundary_pattern.search(after_anchor, boundary_pos + len(boundary_match.group()))
                        if next_match and next_match.start() > boundary_pos + 10:
                            extraction_limit = next_match.start()
            
            # Also check for common document structure markers that indicate field boundaries
            # Look for patterns like ":" followed by field code, or newline patterns
            colon_field_pattern = re.compile(r':\s*\([A-Z0-9.]+\)')
            colon_match = colon_field_pattern.search(after_anchor[:extraction_limit])
            if colon_match:
                # Stop at colon + field code pattern
                extraction_limit = min(extraction_limit, colon_match.start() + 1)
            
            # Limit the text we're working with to avoid capturing next field
            # Also limit to first 200 chars max to prevent excessive extraction
            limited_text = after_anchor[:min(extraction_limit, 200)].strip()
            
            # First, try to get value from same line (after removing separators)
            if limited_text:
                # Split by newline to get same-line content
                first_part = limited_text.split("\n")[0].strip()
                
                # #region agent log
                try:
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps({
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "A",
                            "location": "extraction_service.py:_extract_by_anchor:same_line_extraction",
                            "message": "Same line extraction attempt",
                            "data": {
                                "field_name": field_name,
                                "first_part": first_part[:200],
                                "first_part_length": len(first_part),
                                "extraction_limit": extraction_limit,
                                "has_boundary": boundary_match is not None
                            },
                            "timestamp": int(time.time() * 1000)
                        }) + "\n")
                except Exception:
                    pass
                # #endregion
                
                # Handle colon-separated values: "Label: Value" or "(A) Label: Value"
                # If there's a colon, value is typically after it
                colon_pos = first_part.find(':')
                if colon_pos >= 0:
                    # Value is after the colon
                    after_colon = first_part[colon_pos + 1:].strip()
                    # Remove leading separators
                    after_colon = after_colon.lstrip(" \t-–—")
                    
                    if after_colon:
                        # Extract value stopping at field boundaries, double spaces, or end
                        value_pattern = r'^(.+?)(?:\s*\([A-Z0-9.]+\)\s*|\s{2,}|\t|\n|$)'
                        value_match = re.match(value_pattern, after_colon, re.DOTALL)
                        if value_match:
                            value = value_match.group(1).strip()
                        else:
                            # Take until first field boundary or reasonable limit
                            parts = re.split(r'\s*\([A-Z0-9.]+\)\s*', after_colon, 1)
                            value = parts[0].strip() if parts else ""
                
                # If no value extracted from colon, try normal extraction
                if not value:
                    # Remove common separators (colon, dash, etc.)
                    cleaned = first_part.lstrip(": \t-–—")
                    
                    if cleaned:
                        # Improved extraction pattern that stops at:
                        # 1. Field boundaries (parenthesized codes)
                        # 2. Double spaces or tabs (field separators)
                        # 3. End of line
                        # 4. Common field label patterns
                        
                        # Stop at field codes: (A), (B), (C.1.1), etc.
                        # Stop at double spaces/tabs
                        # Stop at end of line
                        # Limit to reasonable length (max 100 chars for single value)
                        value_pattern = r'^(.+?)(?:\s*\([A-Z0-9.]+\)\s*|\s{2,}|\t|\n|$)'
                        value_match = re.match(value_pattern, cleaned, re.DOTALL)
                        
                        if value_match:
                            value = value_match.group(1).strip()
                            # Additional cleanup: remove trailing field codes if captured
                            value = re.sub(r'\s*\([A-Z0-9.]+\)\s*$', '', value).strip()
                        else:
                            # Fallback: take until first field boundary or reasonable limit
                            # Split by field boundary pattern
                            parts = re.split(r'\s*\([A-Z0-9.]+\)\s*', cleaned, 1)
                            value = parts[0].strip() if parts else ""
                        
                        # Limit value length to prevent capturing too much
                        if value:
                            # Stop at double spaces (common field separator)
                            double_space_pos = value.find("  ")
                            if double_space_pos > 0:
                                value = value[:double_space_pos].strip()
                            
                            # Final length limit (max 100 chars for a single field value)
                            if len(value) > 100:
                                # Try to find a natural break point (space, comma, etc.)
                                break_chars = [' ', ',', ';', '|', '\t']
                                last_break = -1
                                for i in range(99, -1, -1):
                                    if value[i] in break_chars:
                                        last_break = i
                                        break
                                if last_break > 0:
                                    value = value[:last_break].strip()
                                else:
                                    value = value[:100].strip()
                    
                    # #region agent log
                    try:
                        with open(log_path, "a", encoding="utf-8") as f:
                            f.write(json.dumps({
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "A",
                                "location": "extraction_service.py:_extract_by_anchor:same_line_result",
                                "message": "Same line extraction result",
                                "data": {
                                    "field_name": field_name,
                                    "cleaned": cleaned[:200],
                                    "extracted_value": value,
                                    "value_length": len(value) if value else 0,
                                    "used_regex": value_match is not None
                                },
                                "timestamp": int(time.time() * 1000)
                            }) + "\n")
                    except Exception:
                        pass
                    # #endregion
            
            # If no value found on same line, try next line (but still respect boundaries)
            if not value and "\n" in limited_text:
                lines = limited_text.split("\n")
                # #region agent log
                try:
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps({
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "B",
                            "location": "extraction_service.py:_extract_by_anchor:next_line_extraction",
                            "message": "Next line extraction attempt",
                            "data": {
                                "field_name": field_name,
                                "lines_count": len(lines),
                                "first_few_lines": [l[:100] for l in lines[1:4]]
                            },
                            "timestamp": int(time.time() * 1000)
                        }) + "\n")
                except Exception:
                    pass
                # #endregion
                # Skip empty lines and get first non-empty line
                for line in lines[1:]:
                    line = line.strip()
                    if line:
                        # Stop at field boundaries
                        boundary_in_line = field_boundary_pattern.search(line)
                        if boundary_in_line:
                            line = line[:boundary_in_line.start()].strip()
                        
                        # Stop at double spaces
                        double_space_pos = line.find("  ")
                        if double_space_pos > 0:
                            line = line[:double_space_pos].strip()
                        
                        if line:
                            # Limit length
                            value = line[:100].strip()
                            break
                
                # #region agent log
                try:
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps({
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "B",
                            "location": "extraction_service.py:_extract_by_anchor:next_line_result",
                            "message": "Next line extraction result",
                            "data": {
                                "field_name": field_name,
                                "extracted_value": value,
                                "value_length": len(value) if value else 0
                            },
                            "timestamp": int(time.time() * 1000)
                        }) + "\n")
                except Exception:
                    pass
                # #endregion
            
            # Final fallback: if still no value, take first non-empty content (but limit strictly)
            if not value:
                # #region agent log
                try:
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps({
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "D",
                            "location": "extraction_service.py:_extract_by_anchor:fallback_extraction",
                            "message": "Fallback extraction attempt",
                            "data": {
                                "field_name": field_name,
                                "after_anchor_preview": limited_text[:200]
                            },
                            "timestamp": int(time.time() * 1000)
                        }) + "\n")
                except Exception:
                    pass
                # #endregion
                # Remove all whitespace and see if there's any content
                if limited_text.strip():
                    # Take first meaningful chunk (first 50 chars max for fallback)
                    first_line = limited_text.split("\n")[0].strip()
                    # Stop at field boundaries
                    boundary_in_line = field_boundary_pattern.search(first_line)
                    if boundary_in_line:
                        first_line = first_line[:boundary_in_line.start()].strip()
                    # Stop at double spaces
                    double_space_pos = first_line.find("  ")
                    if double_space_pos > 0:
                        first_line = first_line[:double_space_pos].strip()
                    value = first_line[:50].strip()  # Much shorter limit for fallback
                    
                    # #region agent log
                    try:
                        with open(log_path, "a", encoding="utf-8") as f:
                            f.write(json.dumps({
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "D",
                                "location": "extraction_service.py:_extract_by_anchor:fallback_result",
                                "message": "Fallback extraction result",
                                "data": {
                                    "field_name": field_name,
                                    "extracted_value": value,
                                    "value_length": len(value) if value else 0
                                },
                                "timestamp": int(time.time() * 1000)
                            }) + "\n")
                    except Exception:
                        pass
                    # #endregion
            
            # Post-process: Clean up extracted value
            if value:
                # Remove leading/trailing field codes like (A), (B), (C.1.1)
                value = re.sub(r'^\s*\([A-Z0-9.]+\)\s*', '', value)
                value = re.sub(r'\s*\([A-Z0-9.]+\)\s*$', '', value)
                value = value.strip()
                
                # Validate: Reject values that look like field labels instead of actual values
                # Check for common label patterns
                value_upper = value.upper()
                
                # Reject if it's a very long all-caps string (likely a label/header)
                if len(value) > 12 and value == value_upper and ' ' in value:
                    # Check if it contains common label words (in Greek, transliterated Greek, or English)
                    common_label_words = [
                        'REPUBLIC', 'DEMOCRACY', 'REGISTRATION', 'CERTIFICATE',
                        'VEHICLE', 'DATA', 'PERSONAL', 'HOLDER',
                        'AHMOKPATIA', 'KYPIOTHTAZ', 'KYKΛΟΦΟΡΙΑΣ',  # Greek equivalents
                        'EMHNIKH', 'AHMOKPATIA', 'EMHNIKH AHMOKPATIA',  # Transliterated Greek
                        'STOIXEIA', 'OXHMATOS', 'ONOMASTIKA',  # More Greek words
                        'KATOXOS', 'ADEIAS', 'KYKLOPORIAS'  # More Greek words
                    ]
                    # Check if value matches or contains any label word
                    if any(word in value_upper for word in common_label_words):
                        # This looks like a label, not a value
                        value = ""
                    
                    # Also reject if it's a very long all-caps phrase (likely header)
                    # Typical field values are short (license plates, names, dates, etc.)
                    # Headers/labels are often longer phrases
                    if len(value) > 20 and value.count(' ') > 2:
                        # Long phrase with multiple words - likely a label
                        value = ""
                
                # Reject if value starts with field code pattern
                if re.match(r'^\s*\([A-Z0-9.]+\)', value):
                    value = ""
                
                # Final cleanup: remove any remaining field codes in the middle
                value = re.sub(r'\s*\([A-Z0-9.]+\)\s*', ' ', value)
                value = ' '.join(value.split())  # Normalize whitespace
                value = value.strip()

            # #region agent log
            try:
                lines_for_log = after_anchor.split("\n") if "\n" in after_anchor else []
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "C",
                        "location": "extraction_service.py:_extract_by_anchor:value_extracted",
                        "message": "Value extracted after anchor",
                        "data": {
                            "field_name": field_name,
                            "anchor": anchor,
                            "after_anchor_raw": after_anchor[:100],
                            "lines_count": len(lines_for_log),
                            "extracted_value": value,
                            "value_length": len(value) if value else 0
                        },
                        "timestamp": int(time.time() * 1000)
                    }) + "\n")
            except Exception:
                pass
            # #endregion

            if value:
                logger.debug(
                    f"Field '{field_name}': Found anchor '{anchor}', extracted value: '{value[:100] if len(value) > 100 else value}'"
                )
                
                # Try to extract using offset if specified
                offset = field_def.get("offset", {})
                if offset:
                    # Simple implementation: extract at relative position
                    x_offset = offset.get("x", 0)
                    y_offset = offset.get("y", 0)
                    # For now, just return the first line after anchor
                    pass

                return value, 0.7 if value else 0.0

        # #region agent log
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "D",
                    "location": "extraction_service.py:_extract_by_anchor:no_match",
                    "message": "No anchor matched",
                    "data": {
                        "field_name": field_name,
                        "anchors_tried": len(anchors_to_try),
                        "anchors": anchors_to_try
                    },
                    "timestamp": int(time.time() * 1000)
                }) + "\n")
        except Exception:
            pass
        # #endregion
        
        logger.debug(f"Field '{field_name}': None of the {len(anchors_to_try)} anchor(s) matched")
        return None, 0.0

    def _extract_by_name(self, text: str, field_def: Dict[str, Any]) -> Tuple[Any, float]:
        """Extract field value by searching for field name.

        Args:
            text: OCR text
            field_def: Field definition

        Returns:
            Tuple of (value, confidence)
        """
        field_name = field_def.get("name") or field_def.get("json_key")
        if not field_name:
            return None, 0.0

        # Try to find field name in text
        pattern = rf"{re.escape(field_name)}[:\s]+([^\n]+)"
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            return matches[0].strip(), 0.6
        return None, 0.0

    def _post_process_field(self, value: Any, field_def: Dict[str, Any]) -> Any:
        """Apply post-processing to extracted field value.

        Args:
            value: Extracted value
            field_def: Field definition

        Returns:
            Processed value
        """
        if value is None:
            return None

        data_type = field_def.get("data_type", "string")
        post_processing = field_def.get("post_processing", [])

        # Type conversion
        if data_type == "number" or data_type == "integer":
            try:
                # Remove currency symbols, commas, etc.
                cleaned = re.sub(r"[^\d.-]", "", str(value))
                return int(float(cleaned)) if data_type == "integer" else float(cleaned)
            except (ValueError, TypeError):
                return None

        elif data_type == "date":
            # Try common date formats
            date_formats = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"]
            for fmt in date_formats:
                try:
                    from datetime import datetime
                    return datetime.strptime(str(value), fmt).isoformat()
                except (ValueError, TypeError):
                    continue
            return str(value)

        elif data_type == "boolean":
            if isinstance(value, bool):
                return value
            return str(value).lower() in ("true", "yes", "1", "on")

        # Apply post-processing rules
        if isinstance(value, str):
            for rule in post_processing:
                if rule == "trim":
                    value = value.strip()
                elif rule == "lowercase":
                    value = value.lower()
                elif rule == "uppercase":
                    value = value.upper()
                elif rule.startswith("remove_"):
                    # Remove prefix/suffix
                    to_remove = rule.replace("remove_", "")
                    value = value.replace(to_remove, "")
                elif rule.startswith("replace_"):
                    # Replace pattern
                    parts = rule.split("_", 2)
                    if len(parts) == 3:
                        value = value.replace(parts[1], parts[2])

        return value

    def _validate_field(self, value: Any, field_def: Dict[str, Any]) -> bool:
        """Validate extracted field value.

        Args:
            value: Extracted value
            field_def: Field definition with validation rules

        Returns:
            True if valid, False otherwise
        """
        if value is None:
            return not field_def.get("required", False)

        validation_rules = field_def.get("validation_rules", {})
        if not validation_rules:
            return True

        # Regex validation
        if "regex" in validation_rules:
            pattern = validation_rules["regex"]
            if not re.match(pattern, str(value)):
                return False

        # Range validation
        if "min" in validation_rules or "max" in validation_rules:
            try:
                num_value = float(value)
                if "min" in validation_rules and num_value < validation_rules["min"]:
                    return False
                if "max" in validation_rules and num_value > validation_rules["max"]:
                    return False
            except (ValueError, TypeError):
                return False

        # Allowed values
        if "allowed_values" in validation_rules:
            if value not in validation_rules["allowed_values"]:
                return False

        return True

    def _calculate_confidence(self, field_confidences: Dict[str, float]) -> float:
        """Calculate overall confidence from field confidences.

        Args:
            field_confidences: Dict mapping field names to confidence scores

        Returns:
            Overall confidence score (0.0 to 1.0)
        """
        if not field_confidences:
            return 0.0

        confidences = list(field_confidences.values())
        return sum(confidences) / len(confidences)

    def _has_validation_failures(
        self, extracted_data: Dict[str, Any], template: Any
    ) -> bool:
        """Check if extracted data has validation failures.

        Args:
            extracted_data: Extracted field values
            template: Template model

        Returns:
            True if validation failures exist
        """
        field_schema = template.field_schema if hasattr(template, "field_schema") else {}
        fields = field_schema.get("fields", []) or field_schema.get("properties", [])

        for field_def in fields:
            if isinstance(field_def, dict):
                field_name = (
                    field_def.get("name")
                    or field_def.get("json_key")
                    or field_def.get("key")
                )
                if not field_name:
                    continue

                value = extracted_data.get(field_name)
                if not self._validate_field(value, field_def):
                    return True

        return False

    def _is_ai_generated_template(self, template: Any) -> bool:
        """Check if template was AI-generated.
        
        Args:
            template: Template model with field_schema
            
        Returns:
            True if template is AI-generated, False otherwise
        """
        if not hasattr(template, "field_schema"):
            return False
        
        field_schema = template.field_schema
        if isinstance(field_schema, dict):
            # Check for AI-generated metadata
            metadata = field_schema.get("_metadata", {})
            if metadata.get("ai_generated", False):
                return True
            
            # Also check description for AI-generated indicators
            if hasattr(template, "description") and template.description:
                desc_lower = template.description.lower()
                if "auto-generated" in desc_lower or "ai" in desc_lower:
                    return True
        
        return False

    async def _try_ai_extraction_first(
        self, ocr_text: str, template: Any, file_path: str
    ) -> Tuple[Dict[str, Any], Dict[str, float]]:
        """Try AI extraction first for AI-generated templates.
        
        Args:
            ocr_text: OCR extracted text
            template: Template model
            file_path: Path to document file
            
        Returns:
            Tuple of (extracted data dict, field confidence dict)
        """
        try:
            from app.services.ai_extraction_service import AIExtractionService
            
            ai_service = AIExtractionService(extraction_service=self)
            extracted_data, confidence = await ai_service.extract_with_llm(
                ocr_text=ocr_text,
                template=template,
                image_path=file_path,
            )
            
            # Convert single confidence to field confidences
            field_confidences = {}
            if extracted_data:
                # Distribute confidence across fields
                field_count = len(extracted_data)
                per_field_confidence = confidence / field_count if field_count > 0 else confidence
                for field_name in extracted_data.keys():
                    field_confidences[field_name] = per_field_confidence
            
            logger.info(f"AI extraction succeeded for AI-generated template: {len(extracted_data)} fields extracted")
            return extracted_data, field_confidences
        except ImportError:
            logger.warning("AI extraction service not available, falling back to regex")
            return await self._apply_template(ocr_text, template)
        except Exception as e:
            logger.warning(f"AI extraction failed, falling back to regex: {e}")
            return await self._apply_template(ocr_text, template)

    async def _try_ai_extraction_fallback(
        self, ocr_text: str, template: Any, file_path: str
    ) -> Tuple[Dict[str, Any], Dict[str, float]]:
        """Try AI extraction as fallback when regex extraction fails.
        
        Args:
            ocr_text: OCR extracted text
            template: Template model
            file_path: Path to document file
            
        Returns:
            Tuple of (extracted data dict, field confidence dict)
        """
        try:
            from app.services.ai_extraction_service import AIExtractionService
            
            ai_service = AIExtractionService(extraction_service=self)
            extracted_data, confidence = await ai_service.extract_with_llm(
                ocr_text=ocr_text,
                template=template,
                image_path=file_path,
            )
            
            # Convert single confidence to field confidences
            field_confidences = {}
            if extracted_data:
                # Distribute confidence across fields
                field_count = len(extracted_data)
                per_field_confidence = confidence / field_count if field_count > 0 else confidence
                for field_name in extracted_data.keys():
                    field_confidences[field_name] = per_field_confidence
            
            logger.info(f"AI extraction fallback succeeded: {len(extracted_data)} fields extracted")
            return extracted_data, field_confidences
        except ImportError:
            logger.warning("AI extraction service not available for fallback")
            return {}, {}
        except Exception as e:
            logger.warning(f"AI extraction fallback failed: {e}")
            return {}, {}

    def extract_text_from_region(
        self,
        ocr_blocks: List[Dict[str, Any]],
        coordinates: List[float],
        page: int = 1,
    ) -> str:
        """Extract text from OCR blocks that overlap with the given region.
        
        Args:
            ocr_blocks: List of OCR block dictionaries with bbox, text, page
            coordinates: Normalized coordinates [x, y, width, height] (0-1 range)
            page: Page number to filter blocks (1-indexed)
            
        Returns:
            Combined text from overlapping blocks
        """
        if not ocr_blocks or len(coordinates) < 4:
            return ""
        
        x, y, width, height = coordinates[0], coordinates[1], coordinates[2], coordinates[3]
        
        # Calculate region bounds
        region_left = x
        region_top = y
        region_right = x + width
        region_bottom = y + height
        
        # Find blocks that overlap with the region
        matching_blocks = []
        for block in ocr_blocks:
            # Filter by page
            if block.get("page", 1) != page:
                continue
            
            # Get block coordinates (normalized)
            block_bbox = block.get("bbox", [])
            if len(block_bbox) < 4:
                continue
            
            block_left = block_bbox[0]
            block_top = block_bbox[1]
            block_right = block_left + block_bbox[2]
            block_bottom = block_top + block_bbox[3]
            
            # Check for overlap
            # Two rectangles overlap if:
            # - left edge of one is to the left of right edge of the other
            # - top edge of one is above bottom edge of the other
            if (block_left < region_right and block_right > region_left and
                block_top < region_bottom and block_bottom > region_top):
                matching_blocks.append(block)
        
        # Sort blocks by position (top to bottom, left to right)
        matching_blocks.sort(key=lambda b: (b.get("bbox", [0, 0, 0, 0])[1], b.get("bbox", [0, 0, 0, 0])[0]))
        
        # Combine text from matching blocks
        texts = [block.get("text", "").strip() for block in matching_blocks if block.get("text", "").strip()]
        return " ".join(texts)

