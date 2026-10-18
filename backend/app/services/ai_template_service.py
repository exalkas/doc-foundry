"""AI/LLM-based template generation service."""

import json
import logging
from typing import Any, Dict, List, Optional

try:
    from openai import OpenAI
    from openai import APIError as OpenAIAPIError
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None
    OpenAIAPIError = Exception

from app.config import settings

logger = logging.getLogger(__name__)


class AITemplateGenerationError(Exception):
    """Raised when AI template generation fails."""

    pass


class AITemplateService:
    """Service for generating templates using LLM from OCR text."""

    def __init__(self):
        """Initialize AI template service."""
        if not OPENAI_AVAILABLE:
            logger.warning("openai package not installed, AI template generation will be disabled")
            self.client = None
        elif not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not configured, AI template generation will be disabled")
            self.client = None
        else:
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL

    async def generate_template_from_ocr(
        self,
        ocr_text: str,
        ocr_blocks: Optional[List[Dict[str, Any]]] = None,
        export_format: str = "json",
        document_type_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a template field_schema from OCR text using LLM.

        Args:
            ocr_text: Text extracted from OCR
            ocr_blocks: Optional list of OCR blocks with bounding boxes
            export_format: Preferred export format (json, csv, excel)
            document_type_hint: Optional hint about document type (e.g., "invoice", "receipt")

        Returns:
            Dictionary containing field_schema with fields array

        Raises:
            AITemplateGenerationError: If generation fails
        """
        if not self.client:
            if not OPENAI_AVAILABLE:
                raise AITemplateGenerationError(
                    "OpenAI package not installed. Install it with: pip install openai"
                )
            raise AITemplateGenerationError(
                "OpenAI API key not configured. Please set OPENAI_API_KEY environment variable."
            )

        if not ocr_text or not ocr_text.strip():
            raise AITemplateGenerationError("OCR text is required for template generation")

        try:
            # Build context from OCR blocks if available
            ocr_context = ""
            if ocr_blocks:
                ocr_context = "\n\nOCR Blocks with positions:\n"
                for i, block in enumerate(ocr_blocks[:50]):  # Limit to first 50 blocks
                    text = block.get("text", "")
                    page = block.get("page", 1)
                    ocr_context += f"Block {i+1} (Page {page}): {text}\n"

            # Construct prompt
            prompt = self._build_template_generation_prompt(
                ocr_text, ocr_context, export_format, document_type_hint
            )

            # Call OpenAI API
            logger.info(f"Calling OpenAI API (model: {self.model}) for template generation")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing documents and creating structured data extraction templates. You understand document layouts, field types, and extraction strategies.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,  # Lower temperature for more consistent, structured output
                response_format={"type": "json_object"},  # Force JSON response
            )

            # Parse response
            content = response.choices[0].message.content
            if not content:
                raise AITemplateGenerationError("Empty response from OpenAI API")

            # Parse JSON response
            try:
                result = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse OpenAI response as JSON: {e}")
                logger.debug(f"Response content: {content}")
                raise AITemplateGenerationError(f"Invalid JSON response from AI: {str(e)}")

            # Validate and normalize the response
            field_schema = self._normalize_field_schema(result)

            logger.info(
                f"Successfully generated template with {len(field_schema.get('fields', []))} fields"
            )
            return field_schema

        except OpenAIAPIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise AITemplateGenerationError(f"AI service error: {str(e)}")
        except Exception as e:
            logger.exception(f"Unexpected error during template generation: {e}")
            raise AITemplateGenerationError(f"Template generation failed: {str(e)}")

    def _build_template_generation_prompt(
        self,
        ocr_text: str,
        ocr_context: str,
        export_format: str,
        document_type_hint: Optional[str],
    ) -> str:
        """Build the prompt for template generation.

        Args:
            ocr_text: OCR text content
            ocr_context: Additional OCR block context
            export_format: Preferred export format
            document_type_hint: Optional document type hint

        Returns:
            Formatted prompt string
        """
        # Detect if document is multilingual
        is_multilingual = self._detect_multilingual_content(ocr_text)
        language_info = ""
        if is_multilingual:
            detected_languages = self._detect_languages(ocr_text)
            language_info = f"\n\nMULTILINGUAL DOCUMENT DETECTED: This document contains text in multiple languages: {', '.join(detected_languages)}. "
            language_info += "When creating anchor-based extraction patterns, you MUST include anchor texts in ALL detected languages. "
            language_info += "For example, if a field label appears in both English and Greek, include both 'anchor_en' and 'anchor_el' (or use 'anchor_texts' array)."
        
        # Truncate OCR text if too long (keep first 8000 chars for context)
        truncated_text = ocr_text[:8000] if len(ocr_text) > 8000 else ocr_text
        if len(ocr_text) > 8000:
            truncated_text += "\n\n[... OCR text truncated ...]"

        prompt = f"""Analyze the following OCR text from a document and create a structured data extraction template.

Document Type Hint: {document_type_hint or "Unknown"}
Preferred Export Format: {export_format.upper()}
{language_info}

OCR Text:
{truncated_text}
{ocr_context}

Based on this document, create a template field_schema that identifies all extractable structured fields. For each field, determine:
1. Field name (human-readable, prefer English)
2. JSON key (snake_case identifier)
3. Data type (string, number, integer, date, boolean, array)
4. Whether the field is required
5. Extraction strategy (regex, anchor, ml, or name)
6. If using anchor strategy:
   - For multilingual documents: provide "anchor_texts" array with labels in all detected languages
   - OR provide language-specific anchors like "anchor_en", "anchor_el", etc.
   - For single-language documents: provide "anchor" or "anchor_text"
7. If using regex strategy, provide a regex pattern (but prefer anchor for multilingual docs)
8. Optional validation rules

Return a JSON object with this exact structure:
{{
  "fields": [
    {{
      "name": "Field Display Name",
      "json_key": "field_key",
      "data_type": "string|number|integer|date|boolean|array",
      "required": true|false,
      "strategy": "regex|anchor|ml|name",
      "anchor": "single anchor text (for single-language docs)",
      "anchor_texts": ["anchor in language 1", "anchor in language 2"],
      "anchor_en": "English anchor text",
      "anchor_el": "Greek anchor text",
      "pattern": "regex pattern if strategy is regex",
      "validation": {{
        "min_length": 0,
        "max_length": 100,
        "format": "email|url|phone|date"
      }}
    }}
  ]
}}

Guidelines:
- Identify all meaningful structured data fields (dates, amounts, names, IDs, etc.)
- Use appropriate data types (dates should be "date", numbers should be "number" or "integer")
- For dates, use "date" data_type and consider regex patterns like "\\d{{1,2}}[/-]\\d{{1,2}}[/-]\\d{{2,4}}"
- For amounts/currency, use "number" data_type
- IMPORTANT FOR MULTILINGUAL DOCUMENTS:
  * Prefer "anchor" strategy over "regex" for better multilingual support
  * CRITICAL: Look at the OCR text and find the EXACT label text that appears before each value
  * Extract the literal text strings from the OCR - do NOT translate or paraphrase
  * Include anchor texts in ALL detected languages using the EXACT strings from the OCR
  * Example: If OCR shows "ΑΡΙΘΜΟΣ ΚΥΚΛΟΦΟΡΙΑΣ" (Greek) and "Registration Number" (English) 
    appearing before "XHK 4630", use EXACTLY:
    "anchor_texts": ["ΑΡΙΘΜΟΣ ΚΥΚΛΟΦΟΡΙΑΣ", "Registration Number"]
  * Do NOT use translations - use the actual text as it appears in the OCR
  * For each field, scan the OCR text to find where the value appears and note the label text immediately before it
- For single-language documents, use "anchor" or "anchor_text" with the EXACT label text from the OCR
- Use "regex" strategy only when patterns are language-independent (e.g., dates, numbers)
- Make field names descriptive and json_key values in snake_case
- Include validation where appropriate (e.g., email format, phone format)
- Return only valid JSON, no markdown formatting

CRITICAL REGEX PATTERN RULES:
- Python's regex engine does NOT support variable-width look-behind assertions
- NEVER use patterns like "(?<=.*text)" or "(?<=.+text)" - these will fail validation
- Use fixed-width look-behinds only: "(?<=text)" or "(?<=text:)" are valid
- Better alternatives:
  * Use capturing groups: "Field Name:\\s*(.+)" instead of "(?<=.*Field Name:)(.+)"
  * Use anchor strategy instead of regex when fields appear near specific text (ESPECIALLY for multilingual docs)
  * Use simple patterns: "Full Name:\\s*([A-Za-z\\s]+)" instead of "(?<=.*Full Name:)(.+)"
- Valid examples:
  * "Invoice\\s*[#:]?\\s*([A-Z0-9-]+)" - captures invoice number after "Invoice #:" or "Invoice:"
  * "Date\\s*[:\\s]+(\\d{{1,2}}[/-]\\d{{1,2}}[/-]\\d{{2,4}})" - captures date after "Date:"
  * "(?<=Total:)\\s*\\$?([\\d,]+(?:\\.[\\d{{2}}])?)" - fixed-width look-behind (valid)
- Invalid examples (DO NOT USE):
  * "(?<=.*Full Name:)(.+)" - variable-width look-behind (invalid)
  * "(?<=.+Date:)(.+)" - variable-width look-behind (invalid)

Now analyze the document and return the template schema as JSON:"""

        return prompt

    def _normalize_field_schema(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize and validate the generated field schema.

        Args:
            result: Raw result from LLM

        Returns:
            Normalized field_schema dictionary

        Raises:
            AITemplateGenerationError: If schema is invalid
        """
        # Extract fields array
        if "fields" in result:
            fields = result["fields"]
        elif "field_schema" in result and "fields" in result["field_schema"]:
            fields = result["field_schema"]["fields"]
        else:
            raise AITemplateGenerationError(
                "Generated schema missing 'fields' array. Response structure invalid."
            )

        if not isinstance(fields, list):
            raise AITemplateGenerationError("'fields' must be an array")

        if len(fields) == 0:
            raise AITemplateGenerationError("Generated schema has no fields")

        # Normalize each field
        normalized_fields = []
        for i, field in enumerate(fields):
            if not isinstance(field, dict):
                logger.warning(f"Skipping invalid field at index {i}: not a dictionary")
                continue

            # Ensure required fields exist
            name = field.get("name") or field.get("field_name") or f"Field_{i+1}"
            json_key = field.get("json_key") or field.get("key") or self._to_snake_case(name)
            data_type = field.get("data_type") or field.get("type") or "string"
            strategy = field.get("strategy") or "regex"

            # Validate data_type
            valid_types = ["string", "number", "integer", "date", "boolean", "array", "enum"]
            if data_type not in valid_types:
                logger.warning(f"Invalid data_type '{data_type}' for field '{name}', defaulting to 'string'")
                data_type = "string"

            # Validate strategy
            valid_strategies = ["regex", "anchor", "ml", "name"]
            if strategy not in valid_strategies:
                logger.warning(f"Invalid strategy '{strategy}' for field '{name}', defaulting to 'regex'")
                strategy = "regex"

            normalized_field = {
                "name": name,
                "json_key": json_key,
                "data_type": data_type,
                "required": field.get("required", False),
                "strategy": strategy,
            }

            # Add anchor text(s) if strategy is anchor (support multilingual)
            if strategy == "anchor":
                # Support multiple anchor formats
                if "anchor_texts" in field and isinstance(field["anchor_texts"], list):
                    normalized_field["anchor_texts"] = field["anchor_texts"]
                elif "anchor" in field:
                    normalized_field["anchor"] = field["anchor"]
                elif "anchor_text" in field:
                    normalized_field["anchor"] = field["anchor_text"]
                
                # Support language-specific anchors (e.g., anchor_en, anchor_el)
                for key in field.keys():
                    if key.startswith("anchor_") and key not in ["anchor_text", "anchor_texts"]:
                        normalized_field[key] = field[key]
            
            # Add pattern if strategy is regex
            if strategy == "regex" and "pattern" in field:
                # Sanitize regex pattern to fix common issues
                sanitized_pattern = self._sanitize_regex_pattern(field["pattern"], name)
                normalized_field["pattern"] = sanitized_pattern

            # Add validation if present
            if "validation" in field and isinstance(field["validation"], dict):
                normalized_field["validation"] = field["validation"]

            normalized_fields.append(normalized_field)

        if len(normalized_fields) == 0:
            raise AITemplateGenerationError("No valid fields found in generated schema")

        return {"fields": normalized_fields}

    def _sanitize_regex_pattern(self, pattern: str, field_name: str) -> str:
        """Sanitize regex pattern to fix common issues, especially variable-width look-behinds.

        Args:
            pattern: Original regex pattern
            field_name: Name of the field (for logging)

        Returns:
            Sanitized regex pattern
        """
        import re

        if not pattern:
            return pattern

        # Check for variable-width look-behinds (Python re doesn't support these)
        # Patterns like (?<=.*text) or (?<=.+text) are invalid
        # We'll try to convert them to valid alternatives

        # Pattern to match variable-width look-behinds: (?<=.*...) or (?<=.+...)
        # This matches: (?<= followed by .* or .+ followed by text and closing )
        var_width_lookbehind_pattern = r'\(\?<=(?:\.\*|\.\+)([^)]+)\)'
        
        def replace_lookbehind(match):
            # Extract the text inside the look-behind (everything after .* or .+)
            inner_text = match.group(1)
            # Escape special regex characters in the text, but preserve regex metacharacters
            # that might be intentional (like \s, \d, etc.)
            # Simple approach: escape the text, but this might be too aggressive
            # Better: only escape if it's literal text
            escaped_text = re.escape(inner_text)
            # Convert to a capturing group pattern instead
            # Match the text followed by optional whitespace, then capture the value
            return f'{escaped_text}\\s*(.+?)'

        sanitized = pattern
        original_pattern = pattern
        
        # Replace variable-width look-behinds
        if re.search(var_width_lookbehind_pattern, pattern):
            logger.warning(
                f"Field '{field_name}': Detected variable-width look-behind in pattern, "
                f"attempting to fix: {pattern}"
            )
            # Replace all occurrences
            sanitized = re.sub(var_width_lookbehind_pattern, replace_lookbehind, pattern)
            
            # If the pattern already had a capturing group right after the look-behind,
            # we might have created a duplicate. Try to clean it up.
            # Pattern like: (?<=.*text)(.+) becomes text\s*(.+?)(.+)
            # We want: text\s*(.+)
            # Remove duplicate capturing groups that are adjacent (handle both greedy and non-greedy)
            sanitized = re.sub(r'\(\.\+?\?\)\s*\(\.\+?\)', r'(.+)', sanitized)  # (.+?)(.+)
            sanitized = re.sub(r'\(\.\+?\)\s*\(\.\+?\?\)', r'(.+)', sanitized)  # (.+)(.+?)
            sanitized = re.sub(r'\(\.\+?\)\s*\(\.\+?\)', r'(.+)', sanitized)    # (.+)(.+)
            
            logger.info(f"Field '{field_name}': Fixed pattern from '{original_pattern}' to '{sanitized}'")

        # Validate the sanitized pattern compiles
        try:
            re.compile(sanitized)
        except re.error as e:
            logger.warning(
                f"Field '{field_name}': Sanitized pattern still invalid: {sanitized}, "
                f"error: {e}. Original pattern was: {original_pattern}"
            )
            # If sanitization failed, return original and let validation catch it
            # The validation will provide a better error message
            return original_pattern

        return sanitized

    def _detect_multilingual_content(self, text: str) -> bool:
        """Detect if text contains multiple languages.
        
        Args:
            text: OCR text to analyze
            
        Returns:
            True if multilingual content detected, False otherwise
        """
        if not text:
            return False
        
        # Check for Greek characters (common in multilingual EU documents)
        has_greek = any('\u0370' <= char <= '\u03FF' for char in text)
        
        # Check for Cyrillic characters
        has_cyrillic = any('\u0400' <= char <= '\u04FF' for char in text)
        
        # Check for non-ASCII Latin characters (accented characters)
        has_accented = any(ord(char) > 127 and char.isalpha() for char in text if '\u0370' > char or char > '\u03FF')
        
        # Check for common non-English patterns
        # If we have Greek/Cyrillic AND English text, it's multilingual
        has_english = any(char.isascii() and char.isalpha() for char in text)
        
        # Consider multilingual if we have both non-Latin scripts and English
        return (has_greek or has_cyrillic) and has_english
    
    def _detect_languages(self, text: str) -> List[str]:
        """Detect which languages are present in the text.
        
        Args:
            text: OCR text to analyze
            
        Returns:
            List of detected language codes (e.g., ['en', 'el'])
        """
        languages = []
        
        if not text:
            return languages
        
        # Check for Greek characters
        has_greek = any('\u0370' <= char <= '\u03FF' for char in text)
        if has_greek:
            languages.append('el')  # Greek
        
        # Check for Cyrillic characters
        has_cyrillic = any('\u0400' <= char <= '\u04FF' for char in text)
        if has_cyrillic:
            languages.append('ru')  # Russian (could be other Cyrillic languages)
        
        # Check for English (ASCII letters)
        has_english = any(char.isascii() and char.isalpha() for char in text)
        if has_english:
            languages.append('en')  # English
        
        # If no specific script detected, assume English
        if not languages:
            languages.append('en')
        
        return languages

    def _to_snake_case(self, text: str) -> str:
        """Convert text to snake_case.

        Args:
            text: Text to convert

        Returns:
            Snake case string
        """
        import re

        # Replace spaces and special chars with underscores
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s-]+", "_", text)
        # Convert to lowercase
        text = text.lower()
        # Remove leading/trailing underscores
        text = text.strip("_")
        return text

