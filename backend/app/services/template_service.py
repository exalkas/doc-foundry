"""Template service for validation, versioning, and field extraction logic."""

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.template import Template

logger = logging.getLogger(__name__)


class TemplateValidationError(Exception):
    """Raised when template validation fails."""

    pass


class TemplateService:
    """Service for template validation, versioning, and field extraction."""

    def validate_field_schema(self, field_schema: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate a template field schema.

        Args:
            field_schema: Field schema dictionary

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors: List[str] = []
        fields = field_schema.get("fields", []) or field_schema.get("properties", [])

        if not fields:
            errors.append("Field schema must contain at least one field")

        for i, field_def in enumerate(fields):
            if not isinstance(field_def, dict):
                errors.append(f"Field {i} must be a dictionary")
                continue

            field_name = (
                field_def.get("name")
                or field_def.get("json_key")
                or field_def.get("key")
            )
            if not field_name:
                errors.append(f"Field {i} must have a name, json_key, or key")

            # Validate data type
            data_type = field_def.get("data_type", "string")
            valid_types = ["string", "number", "integer", "date", "boolean", "array", "enum"]
            if data_type not in valid_types:
                errors.append(
                    f"Field {field_name}: invalid data_type '{data_type}'. "
                    f"Must be one of: {', '.join(valid_types)}"
                )

            # Validate extraction strategy
            strategy = field_def.get("strategy", "regex")
            valid_strategies = ["regex", "anchor", "ml", "name"]
            if strategy not in valid_strategies:
                errors.append(
                    f"Field {field_name}: invalid strategy '{strategy}'. "
                    f"Must be one of: {', '.join(valid_strategies)}"
                )

            # Validate regex pattern if strategy is regex
            if strategy == "regex":
                pattern = field_def.get("pattern") or field_def.get("regex")
                if pattern:
                    try:
                        re.compile(pattern)
                    except re.error as e:
                        error_msg = str(e)
                        # Provide more helpful error message with the pattern
                        if "look-behind requires fixed-width pattern" in error_msg:
                            errors.append(
                                f"Field {field_name}: invalid regex pattern - variable-width look-behind detected. "
                                f"Pattern: '{pattern}'. Python's regex engine only supports fixed-width look-behinds. "
                                f"Use patterns like '(?<=text)' instead of '(?<=.*text)' or use capturing groups."
                            )
                        else:
                            errors.append(
                                f"Field {field_name}: invalid regex pattern '{pattern}': {error_msg}"
                            )
                        logger.warning(
                            f"Invalid regex pattern for field '{field_name}': {pattern}, error: {error_msg}"
                        )

            # Validate validation rules
            validation_rules = field_def.get("validation_rules", {})
            if validation_rules:
                if "min" in validation_rules and "max" in validation_rules:
                    if validation_rules["min"] > validation_rules["max"]:
                        errors.append(
                            f"Field {field_name}: validation min > max"
                        )

        return len(errors) == 0, errors

    async def create_template_version(
        self,
        session: AsyncSession,
        template_id: UUID,
        field_schema: Dict[str, Any],
        updated_by_user_id: UUID,
    ) -> Template:
        """Create a new version of a template.

        Args:
            session: Database session
            template_id: Template ID
            field_schema: New field schema
            updated_by_user_id: User ID making the update

        Returns:
            Updated Template object

        Raises:
            TemplateValidationError: If validation fails
        """
        # Validate schema
        is_valid, errors = self.validate_field_schema(field_schema)
        if not is_valid:
            raise TemplateValidationError(f"Invalid field schema: {', '.join(errors)}")

        # Get existing template
        result = await session.execute(
            select(Template).where(Template.id == template_id)
        )
        template = result.scalar_one_or_none()

        if not template:
            raise ValueError(f"Template not found: {template_id}")

        # Update template (simple versioning - in production, you might want
        # to create separate version records)
        template.field_schema = field_schema
        template.updated_at = datetime.now(timezone.utc)
        # Note: In a full versioning system, you'd track version numbers separately

        await session.flush()

        logger.info(
            "Created new version for template: id=%s, updated_by=%s",
            template_id,
            updated_by_user_id,
        )

        return template

    async def can_delete_template(
        self,
        session: AsyncSession,
        template_id: UUID,
    ) -> Tuple[bool, List[str]]:
        """Check if a template can be safely deleted.

        Args:
            session: Database session
            template_id: Template ID

        Returns:
            Tuple of (can_delete, list_of_warnings)
        """
        warnings: List[str] = []

        # Check if template has associated documents
        result = await session.execute(
            select(Template).where(Template.id == template_id)
        )
        template = result.scalar_one_or_none()

        if not template:
            return False, ["Template not found"]

        # Count documents using this template
        # (In a full implementation, you'd query Document table)
        if hasattr(template, "documents") and len(template.documents) > 0:
            warnings.append(
                f"Template has {len(template.documents)} associated documents. "
                "They will be unlinked but not deleted."
            )

        # Count extraction results
        if hasattr(template, "extraction_results") and len(template.extraction_results) > 0:
            warnings.append(
                f"Template has {len(template.extraction_results)} extraction results. "
                "Historical results will reference a deleted template."
            )

        # Template can be deleted, but with warnings
        return True, warnings

    async def archive_template(
        self,
        session: AsyncSession,
        template_id: UUID,
    ) -> Template:
        """Archive a template (soft delete).

        Args:
            session: Database session
            template_id: Template ID

        Returns:
            Archived Template object
        """
        result = await session.execute(
            select(Template).where(Template.id == template_id)
        )
        template = result.scalar_one_or_none()

        if not template:
            raise ValueError(f"Template not found: {template_id}")

        # In a full implementation, you'd add an `archived_at` field
        # For now, we'll just update the description
        if template.description:
            template.description = f"[ARCHIVED] {template.description}"
        else:
            template.description = "[ARCHIVED]"

        template.updated_at = datetime.now(timezone.utc)

        await session.flush()

        logger.info("Archived template: id=%s", template_id)

        return template

    def extract_field_value(
        self,
        text: str,
        field_def: Dict[str, Any],
    ) -> Tuple[Any, float]:
        """Extract a field value from text using field definition.

        Args:
            text: Text to extract from
            field_def: Field definition dictionary

        Returns:
            Tuple of (extracted_value, confidence_score)
        """
        strategy = field_def.get("strategy", "regex")

        if strategy == "regex":
            return self._extract_by_regex(text, field_def)
        elif strategy == "anchor":
            return self._extract_by_anchor(text, field_def)
        elif strategy == "name":
            return self._extract_by_name(text, field_def)
        else:
            # Default: try name-based extraction
            return self._extract_by_name(text, field_def)

    def _extract_by_regex(self, text: str, field_def: Dict[str, Any]) -> Tuple[Any, float]:
        """Extract field value using regex pattern."""
        pattern = field_def.get("pattern") or field_def.get("regex")
        if not pattern:
            return None, 0.0

        try:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            if matches:
                value = matches[0] if isinstance(matches[0], str) else str(matches[0])
                return value, 0.8
            return None, 0.0
        except re.error:
            logger.warning("Invalid regex pattern: %s", pattern)
            return None, 0.0

    def _extract_by_anchor(self, text: str, field_def: Dict[str, Any]) -> Tuple[Any, float]:
        """Extract field value using anchor text with multilingual support."""
        # Support multiple anchor formats:
        # 1. Single anchor string: "anchor" or "anchor_text"
        # 2. Multiple anchors array: "anchor_texts" (try all until one matches)
        # 3. Language-specific anchors: "anchor_en", "anchor_el", etc.
        anchors_to_try = []
        
        # Check for anchor_texts array (multilingual support)
        if "anchor_texts" in field_def and isinstance(field_def["anchor_texts"], list):
            anchors_to_try.extend(field_def["anchor_texts"])
        
        # Check for language-specific anchors (e.g., anchor_en, anchor_el)
        for key in field_def.keys():
            if key.startswith("anchor_") and key not in ["anchor_text", "anchor_texts"]:
                anchors_to_try.append(field_def[key])
        
        # Check for single anchor (backward compatibility)
        single_anchor = field_def.get("anchor") or field_def.get("anchor_text")
        if single_anchor:
            anchors_to_try.append(single_anchor)
        
        if not anchors_to_try:
            return None, 0.0

        # Try each anchor until one matches
        for anchor in anchors_to_try:
            if not anchor or not isinstance(anchor, str):
                continue
            
            anchor_lower = anchor.lower()
            anchor_pos = text.lower().find(anchor_lower)
            
            if anchor_pos == -1:
                continue

            # Extract text after anchor
            after_anchor = text[anchor_pos + len(anchor):].strip()
            
            # Extract value - handle multiple formats
            value = ""
            
            # First, try to get value from same line
            if after_anchor:
                first_part = after_anchor.split("\n")[0].strip()
                cleaned = first_part.lstrip(": \t-–—")
                
                if cleaned:
                    # Extract value - stop at significant whitespace or end of line
                    value_match = re.match(r'^(.+?)(?:\s{2,}|\t|\n|$)', cleaned, re.DOTALL)
                    if value_match:
                        value = value_match.group(1).strip()
                    else:
                        value = cleaned[:200].strip()
            
            # If no value on same line, try next line
            if not value and "\n" in after_anchor:
                lines = after_anchor.split("\n")
                for line in lines[1:]:
                    line = line.strip()
                    if line:
                        value = line[:200].strip()
                        break
            
            # Final fallback
            if not value:
                lines = after_anchor.split("\n")
                value = lines[0].strip() if lines else ""

            if value:
                return value, 0.7

        return None, 0.0

    def _extract_by_name(self, text: str, field_def: Dict[str, Any]) -> Tuple[Any, float]:
        """Extract field value by searching for field name."""
        field_name = field_def.get("name") or field_def.get("json_key")
        if not field_name:
            return None, 0.0

        pattern = rf"{re.escape(field_name)}[:\s]+([^\n]+)"
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            return matches[0].strip(), 0.6
        return None, 0.0

    def post_process_field(self, value: Any, field_def: Dict[str, Any]) -> Any:
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
                cleaned = re.sub(r"[^\d.-]", "", str(value))
                return int(float(cleaned)) if data_type == "integer" else float(cleaned)
            except (ValueError, TypeError):
                return None

        elif data_type == "date":
            date_formats = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"]
            for fmt in date_formats:
                try:
                    dt = datetime.strptime(str(value), fmt)
                    return dt.isoformat()
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

        return value

    def validate_field_value(self, value: Any, field_def: Dict[str, Any]) -> bool:
        """Validate extracted field value against validation rules.

        Args:
            value: Extracted value
            field_def: Field definition

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

