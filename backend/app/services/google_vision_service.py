"""Google Cloud Vision API service for OCR processing."""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from google.api_core import exceptions as google_exceptions
from google.cloud import vision
from google.oauth2 import service_account
from PIL import Image

from app.config import settings
from app.services.ocr_language_mapper import map_language_code

logger = logging.getLogger(__name__)


class GoogleVisionService:
    """Service for performing OCR using Google Cloud Vision API."""

    def __init__(self):
        """Initialize Google Vision client with authentication."""
        self.project_id = settings.GOOGLE_CLOUD_PROJECT_ID
        self.timeout = settings.GOOGLE_CLOUD_VISION_TIMEOUT_SECONDS
        self.max_pages_per_request = settings.GOOGLE_CLOUD_VISION_MAX_PAGES_PER_REQUEST
        self.enable_async = settings.GOOGLE_CLOUD_VISION_ENABLE_ASYNC

        # Initialize client with credentials
        credentials = self._get_credentials()
        self.client = vision.ImageAnnotatorClient(credentials=credentials)

    def _get_credentials(self):
        """Get Google Cloud credentials from environment or service account file.

        Returns:
            Credentials object for Google Cloud API
        """
        credentials_path = settings.GOOGLE_CLOUD_VISION_CREDENTIALS_PATH

        if credentials_path and os.path.exists(credentials_path):
            logger.info(f"Using service account credentials from: {credentials_path}")
            return service_account.Credentials.from_service_account_file(
                credentials_path
            )

        # Use Application Default Credentials (ADC)
        logger.info("Using Application Default Credentials (ADC)")
        return None  # Client will use ADC automatically

    async def detect_text(
        self, image_path: str, language_hints: Optional[List[str]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Detect text in an image file.

        Args:
            image_path: Path to the image file
            language_hints: Optional list of language hints (ISO 639-1 codes)

        Returns:
            Tuple of (extracted text, metadata dictionary)

        Raises:
            OCRProcessingError: If OCR processing fails
        """
        try:
            # Read image file
            with open(image_path, "rb") as image_file:
                content = image_file.read()

            # Create image object
            image = vision.Image(content=content)

            # Configure image context with language hints
            image_context = vision.ImageContext()
            if language_hints:
                image_context.language_hints = language_hints

            # Perform OCR
            response = await asyncio.to_thread(
                self._retry_with_backoff,
                lambda: self.client.text_detection(
                    image=image, image_context=image_context
                ),
            )

            # Extract text and annotations
            annotations = response.text_annotations
            if not annotations:
                return "", self._build_empty_metadata(image_path)

            # First annotation contains full text
            full_text = annotations[0].description

            # Extract blocks from remaining annotations
            blocks = self._extract_blocks_from_annotations(
                annotations[1:], image_path
            )

            # Get image dimensions for normalization
            img = Image.open(image_path)
            width, height = img.size

            # Build metadata
            metadata = self._build_metadata(
                full_text, blocks, image_path, width, height
            )

            return full_text, metadata

        except Exception as e:
            logger.exception(f"Google Vision OCR failed for image {image_path}: {e}")
            raise OCRProcessingError(f"Google Vision OCR failed: {str(e)}") from e

    async def detect_text_from_pdf(
        self, pdf_path: str, language_hints: Optional[List[str]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Detect text in a PDF file.

        Args:
            pdf_path: Path to the PDF file
            language_hints: Optional list of language hints (ISO 639-1 codes)

        Returns:
            Tuple of (extracted text, metadata dictionary)

        Raises:
            OCRProcessingError: If OCR processing fails
        """
        try:
            if self.enable_async:
                return await self._detect_text_from_pdf_async(pdf_path, language_hints)
            else:
                return await self._detect_text_from_pdf_sync(pdf_path, language_hints)

        except Exception as e:
            logger.exception(f"Google Vision OCR failed for PDF {pdf_path}: {e}")
            raise OCRProcessingError(f"Google Vision OCR failed: {str(e)}") from e

    async def _detect_text_from_pdf_async(
        self, pdf_path: str, language_hints: Optional[List[str]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Detect text in PDF using synchronous batch API.
        
        Uses batch_annotate_files which supports direct PDF content (no GCS required).
        The synchronous API is run in a thread to avoid blocking the event loop.
        """
        from google.cloud.vision_v1 import (
            AnnotateFileRequest,
            BatchAnnotateFilesRequest,
            Feature,
            ImageContext,
            InputConfig,
        )

        # Read PDF file
        with open(pdf_path, "rb") as pdf_file:
            pdf_content = pdf_file.read()

        # Configure request
        feature = Feature(type_=Feature.Type.DOCUMENT_TEXT_DETECTION)
        image_context = ImageContext()
        if language_hints:
            image_context.language_hints = language_hints

        # Prepare request - use synchronous batch API which supports direct content
        request = BatchAnnotateFilesRequest(
            requests=[
                AnnotateFileRequest(
                    input_config=InputConfig(
                        content=pdf_content, mime_type="application/pdf"
                    ),
                    features=[feature],
                    image_context=image_context,
                )
            ]
        )

        # Submit batch request using synchronous API (run in thread to avoid blocking)
        # Note: batch_annotate_files supports direct content (no GCS required)
        logger.info("Processing PDF with batch API...")
        response = await asyncio.to_thread(
            self._retry_with_backoff,
            lambda: self.client.batch_annotate_files(request)
        )

        # Extract results
        # Response structure: response.responses is a list of AnnotateFileResponse
        if not response.responses or not response.responses[0].responses:
            return "", self._build_empty_metadata(pdf_path, is_pdf=True)

        # Combine all pages
        all_text_parts: List[str] = []
        all_blocks: List[Dict[str, Any]] = []
        page_count = 0

        # Process each file response
        for file_response in response.responses:
            # Each file_response.responses contains page responses
            for page_response in file_response.responses:
                page_count += 1
                if page_response.full_text_annotation:
                    page_text = page_response.full_text_annotation.text
                    all_text_parts.append(page_text)

                    # Extract blocks for this page
                    page_blocks = self._extract_blocks_from_full_text_annotation(
                        page_response.full_text_annotation, page_count
                    )
                    all_blocks.extend(page_blocks)

        full_text = "\n\n".join(all_text_parts)

        # Build metadata
        metadata = self._build_metadata(
            full_text, all_blocks, pdf_path, page_count=page_count, is_pdf=True
        )

        return full_text, metadata

    async def _detect_text_from_pdf_sync(
        self, pdf_path: str, language_hints: Optional[List[str]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Detect text in PDF using sync API (for smaller PDFs)."""
        # For sync processing, we'd need to convert PDF pages to images
        # Since Google Vision supports PDF natively via async API, we'll use that
        # This is a fallback that uses async internally
        return await self._detect_text_from_pdf_async(pdf_path, language_hints)

    def _extract_blocks_from_annotations(
        self, annotations: List, image_path: str
    ) -> List[Dict[str, Any]]:
        """Extract text blocks from Google Vision text annotations.

        Args:
            annotations: List of TextAnnotation objects (excluding first full-text one)
            image_path: Path to image for dimension calculation

        Returns:
            List of block dictionaries
        """
        blocks: List[Dict[str, Any]] = []

        # Get image dimensions
        try:
            img = Image.open(image_path)
            width, height = img.size
        except Exception:
            width, height = 1, 1  # Fallback

        for annotation in annotations:
            text = annotation.description
            if not text or not text.strip():
                continue

            # Get bounding polygon
            vertices = annotation.bounding_poly.vertices
            if len(vertices) < 2:
                continue

            # Calculate bounding box
            x_coords = [v.x for v in vertices if v.x is not None]
            y_coords = [v.y for v in vertices if v.y is not None]

            if not x_coords or not y_coords:
                continue

            min_x = min(x_coords)
            min_y = min(y_coords)
            max_x = max(x_coords)
            max_y = max(y_coords)

            # Normalize coordinates (0-1 range)
            bbox_normalized = [
                min_x / width if width > 0 else 0,
                min_y / height if height > 0 else 0,
                (max_x - min_x) / width if width > 0 else 0,
                (max_y - min_y) / height if height > 0 else 0,
            ]

            # Pixel coordinates
            bbox_pixels = [min_x, min_y, max_x - min_x, max_y - min_y]

            blocks.append(
                {
                    "text": text.strip(),
                    "bbox": bbox_normalized,
                    "bbox_pixels": bbox_pixels,
                    "confidence": 1.0,  # Google Vision doesn't provide per-block confidence
                    "page": 1,
                }
            )

        return blocks

    def _extract_blocks_from_full_text_annotation(
        self, full_text_annotation: Any, page: int
    ) -> List[Dict[str, Any]]:
        """Extract blocks from Google Vision FullTextAnnotation (for PDFs).

        Args:
            full_text_annotation: FullTextAnnotation object
            page: Page number (1-indexed)

        Returns:
            List of block dictionaries
        """
        blocks: List[Dict[str, Any]] = []

        if not full_text_annotation or not full_text_annotation.pages:
            return blocks

        # Get page dimensions
        page_obj = full_text_annotation.pages[0]
        width = page_obj.width if page_obj.width else 1
        height = page_obj.height if page_obj.height else 1

        # Extract blocks from pages
        for page_obj in full_text_annotation.pages:
            for block in page_obj.blocks:
                block_text_parts: List[str] = []
                min_x, min_y = float("inf"), float("inf")
                max_x, max_y = float("-inf"), float("-inf")

                for paragraph in block.paragraphs:
                    for word in paragraph.words:
                        # Extract word text
                        word_text = "".join(
                            symbol.text for symbol in word.symbols
                        )
                        block_text_parts.append(word_text)

                        # Update bounding box
                        for vertex in word.bounding_box.vertices:
                            if vertex.x is not None:
                                min_x = min(min_x, vertex.x)
                                max_x = max(max_x, vertex.x)
                            if vertex.y is not None:
                                min_y = min(min_y, vertex.y)
                                max_y = max(max_y, vertex.y)

                if block_text_parts and min_x != float("inf"):
                    block_text = " ".join(block_text_parts)

                    # Normalize coordinates
                    bbox_normalized = [
                        min_x / width if width > 0 else 0,
                        min_y / height if height > 0 else 0,
                        (max_x - min_x) / width if width > 0 else 0,
                        (max_y - min_y) / height if height > 0 else 0,
                    ]

                    bbox_pixels = [min_x, min_y, max_x - min_x, max_y - min_y]

                    blocks.append(
                        {
                            "text": block_text,
                            "bbox": bbox_normalized,
                            "bbox_pixels": bbox_pixels,
                            "confidence": 1.0,
                            "page": page,
                        }
                    )

        return blocks

    def _build_metadata(
        self,
        text: str,
        blocks: List[Dict[str, Any]],
        file_path: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
        page_count: Optional[int] = None,
        is_pdf: bool = False,
    ) -> Dict[str, Any]:
        """Build metadata dictionary from OCR results.

        Args:
            text: Extracted text
            blocks: List of text blocks
            file_path: Path to processed file
            width: Image width (for images)
            height: Image height (for images)
            page_count: Number of pages (for PDFs)
            is_pdf: Whether file is a PDF

        Returns:
            Metadata dictionary
        """
        metadata: Dict[str, Any] = {
            "text_length": len(text),
            "word_count": len(text.split()),
            "engine": "google_vision",
            "blocks": blocks,
        }

        if is_pdf:
            metadata["page_count"] = page_count or 1
            metadata["format"] = "pdf"
        else:
            if width and height:
                metadata["dimensions"] = [width, height]
            ext = Path(file_path).suffix.lower()
            metadata["format"] = ext[1:] if ext.startswith(".") else ext

        return metadata

    def _build_empty_metadata(
        self, file_path: str, is_pdf: bool = False
    ) -> Dict[str, Any]:
        """Build empty metadata when no text is detected.

        Args:
            file_path: Path to processed file
            is_pdf: Whether file is a PDF

        Returns:
            Empty metadata dictionary
        """
        metadata: Dict[str, Any] = {
            "text_length": 0,
            "word_count": 0,
            "engine": "google_vision",
            "blocks": [],
        }

        if is_pdf:
            metadata["format"] = "pdf"
            metadata["page_count"] = 0
        else:
            ext = Path(file_path).suffix.lower()
            metadata["format"] = ext[1:] if ext.startswith(".") else ext

        return metadata

    def _retry_with_backoff(self, func, max_retries: int = 3):
        """Retry a function call with exponential backoff.

        Args:
            func: Function to call
            max_retries: Maximum number of retries

        Returns:
            Function result

        Raises:
            Exception: If all retries fail
        """
        import time

        last_exception = None

        for attempt in range(max_retries):
            try:
                return func()
            except (
                google_exceptions.DeadlineExceeded,
                google_exceptions.ServiceUnavailable,
                google_exceptions.InternalServerError,
            ) as e:
                last_exception = e
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.warning(
                        f"Retry attempt {attempt + 1}/{max_retries} after {wait_time}s: {e}"
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"All retry attempts failed: {e}")
                    raise
            except (
                google_exceptions.InvalidArgument,
                google_exceptions.PermissionDenied,
                google_exceptions.NotFound,
            ) as e:
                # Don't retry on permanent errors
                logger.error(f"Permanent error (no retry): {e}")
                raise
            except google_exceptions.QuotaExceeded as e:
                # Quota exceeded - don't retry immediately
                logger.error(f"Quota exceeded: {e}")
                raise

        if last_exception:
            raise last_exception

    def _wait_for_operation(self, operation, timeout: Optional[int] = None):
        """Wait for a long-running operation to complete.

        Args:
            operation: Operation object
            timeout: Optional timeout in seconds

        Returns:
            Operation result
        """
        timeout = timeout or (self.timeout * 10)  # Allow more time for async operations
        return operation.result(timeout=timeout)

    async def _retry_async(self, coro_func, max_retries: int = 3):
        """Retry an async coroutine with exponential backoff.

        Args:
            coro_func: Function that returns a coroutine to call
            max_retries: Maximum number of retries

        Returns:
            Coroutine result
        """
        import time

        last_exception = None

        for attempt in range(max_retries):
            try:
                return await coro_func()
            except (
                google_exceptions.DeadlineExceeded,
                google_exceptions.ServiceUnavailable,
                google_exceptions.InternalServerError,
            ) as e:
                last_exception = e
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.warning(
                        f"Retry attempt {attempt + 1}/{max_retries} after {wait_time}s: {e}"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"All retry attempts failed: {e}")
                    raise
            except (
                google_exceptions.InvalidArgument,
                google_exceptions.PermissionDenied,
                google_exceptions.NotFound,
            ) as e:
                # Don't retry on permanent errors
                logger.error(f"Permanent error (no retry): {e}")
                raise
            except google_exceptions.QuotaExceeded as e:
                # Quota exceeded - don't retry immediately
                logger.error(f"Quota exceeded: {e}")
                raise

        if last_exception:
            raise last_exception

    async def _wait_for_async_operation(self, operation, timeout: Optional[int] = None):
        """Wait for an async long-running operation to complete.

        Args:
            operation: Async operation object from async client
            timeout: Optional timeout in seconds

        Returns:
            Operation result
        """
        timeout = timeout or (self.timeout * 10)  # Allow more time for async operations
        
        # Check if result() is a coroutine (async method)
        import inspect
        result_method = getattr(operation, 'result', None)
        if result_method and inspect.iscoroutinefunction(result_method):
            # Async result method - await it
            return await operation.result(timeout=timeout)
        else:
            # Synchronous result method - run in thread
            return await asyncio.to_thread(
                lambda: operation.result(timeout=timeout)
            )


class OCRProcessingError(Exception):
    """Raised when OCR processing fails."""

    pass

