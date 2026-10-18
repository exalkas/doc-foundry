"""File validation service for security and safety checks."""

import logging
import os
from pathlib import Path
from typing import Optional, Tuple

try:
    import magic
except ImportError:
    magic = None

from PIL import Image

from app.services.plan_service import PlanService

logger = logging.getLogger(__name__)


class FileValidationError(Exception):
    """Raised when file validation fails."""

    pass


class FileValidationService:
    """Service for validating uploaded files."""

    # Maximum file sizes (in bytes)
    MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB default

    # Allowed MIME types
    ALLOWED_MIME_TYPES = {
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/tiff",
        "image/tif",
        "image/bmp",
        "image/gif",
    }

    # Allowed file extensions
    ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".gif"}

    def __init__(self, plan_service: Optional[PlanService] = None):
        """Initialize file validation service.

        Args:
            plan_service: Plan service instance
        """
        self.plan_service = plan_service or PlanService()

    def validate_file_type(
        self,
        file_path: str,
        declared_mime_type: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Validate file type by checking actual content.

        Args:
            file_path: Path to file
            declared_mime_type: MIME type declared by client (not trusted)

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not os.path.exists(file_path):
            return False, "File not found"

        # Check extension
        ext = Path(file_path).suffix.lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            return (
                False,
                f"File extension '{ext}' not allowed. Allowed: {', '.join(self.ALLOWED_EXTENSIONS)}",
            )

        # Check actual MIME type using python-magic if available
        if magic:
            try:
                mime_type = magic.from_file(file_path, mime=True)
                if mime_type not in self.ALLOWED_MIME_TYPES:
                    return (
                        False,
                        f"File type '{mime_type}' not allowed. "
                        f"Allowed: {', '.join(self.ALLOWED_MIME_TYPES)}",
                    )
            except Exception as e:
                logger.warning("Failed to detect MIME type: %s", e)
                # Fall through to extension-based validation

        return True, None

    def validate_file_size(
        self,
        file_path: str,
        plan_tier: str = "free",
    ) -> Tuple[bool, Optional[str]]:
        """Validate file size against plan limits.

        Args:
            file_path: Path to file
            plan_tier: Plan tier identifier

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not os.path.exists(file_path):
            return False, "File not found"

        file_size_bytes = os.path.getsize(file_path)
        file_size_mb = file_size_bytes / (1024 * 1024)

        return self.plan_service.check_file_size_limit(plan_tier, file_size_mb)

    def validate_image_dimensions(
        self,
        file_path: str,
        plan_tier: str = "free",
    ) -> Tuple[bool, Optional[str]]:
        """Validate image dimensions against plan limits.

        Args:
            file_path: Path to image file
            plan_tier: Plan tier identifier

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not os.path.exists(file_path):
            return False, "File not found"

        ext = Path(file_path).suffix.lower()
        if ext not in {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".gif"}:
            return True, None  # Not an image, skip dimension check

        try:
            with Image.open(file_path) as img:
                width, height = img.size
                return self.plan_service.check_image_dimensions(plan_tier, width, height)
        except Exception as e:
            logger.warning("Failed to read image dimensions: %s", e)
            return False, f"Failed to read image dimensions: {str(e)}"

    def validate_file(
        self,
        file_path: str,
        plan_tier: str = "free",
        declared_mime_type: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Perform comprehensive file validation.

        Args:
            file_path: Path to file
            plan_tier: Plan tier identifier
            declared_mime_type: MIME type declared by client

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Validate file type
        is_valid, error = self.validate_file_type(file_path, declared_mime_type)
        if not is_valid:
            return False, error

        # Validate file size
        is_valid, error = self.validate_file_size(file_path, plan_tier)
        if not is_valid:
            return False, error

        # Validate image dimensions (if image)
        is_valid, error = self.validate_image_dimensions(file_path, plan_tier)
        if not is_valid:
            return False, error

        return True, None

    def sanitize_pdf(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """Sanitize PDF file (placeholder for future implementation).

        In production, this would:
        - Remove embedded JavaScript
        - Remove malicious objects
        - Validate PDF structure
        - Use a library like pdf-lib or PyPDF2

        Args:
            file_path: Path to PDF file

        Returns:
            Tuple of (is_safe, error_message)
        """
        # Placeholder implementation
        # In production, integrate with PDF sanitization library
        logger.info("PDF sanitization check (placeholder): %s", file_path)
        return True, None

    def scan_for_viruses(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """Scan file for viruses (placeholder for ClamAV integration).

        Args:
            file_path: Path to file

        Returns:
            Tuple of (is_safe, error_message)
        """
        # Placeholder for ClamAV integration
        # In production, integrate with ClamAV daemon or API
        logger.info("Virus scan (placeholder): %s", file_path)
        return True, None

