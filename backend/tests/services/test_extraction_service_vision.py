"""Integration tests for ExtractionService with Google Vision."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.extraction_service import ExtractionService, ExtractionError
from app.services.google_vision_service import OCRProcessingError


class TestExtractionServiceVision:
    """Test ExtractionService integration with Google Vision."""

    @pytest.fixture
    def extraction_service(self):
        """Create ExtractionService instance."""
        with patch("app.services.extraction_service.GoogleVisionService"):
            service = ExtractionService()
            service.vision_service = MagicMock()
            yield service

    @pytest.fixture
    def mock_template(self):
        """Create a mock template."""
        template = MagicMock()
        template.id = "test-template-id"
        template.field_schema = {
            "fields": [
                {
                    "name": "test_field",
                    "pattern": r"test\s+(\w+)",
                    "required": False,
                }
            ]
        }
        return template

    @pytest.mark.asyncio
    async def test_perform_ocr_image_success(self, extraction_service, tmp_path):
        """Test successful OCR on image file."""
        test_image = tmp_path / "test.png"
        test_image.write_bytes(b"fake image data")

        # Mock Vision service response
        extraction_service.vision_service.detect_text = AsyncMock(
            return_value=(
                "Test OCR Text",
                {
                    "blocks": [],
                    "text_length": 12,
                    "word_count": 3,
                    "engine": "google_vision",
                },
            )
        )

        text, metadata = await extraction_service._perform_ocr(
            str(test_image), ".png", "eng"
        )

        assert text == "Test OCR Text"
        assert metadata["engine"] == "google_vision"
        assert metadata["ocr_language"] == "eng"
        extraction_service.vision_service.detect_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_perform_ocr_pdf_success(self, extraction_service, tmp_path):
        """Test successful OCR on PDF file."""
        test_pdf = tmp_path / "test.pdf"
        test_pdf.write_bytes(b"fake pdf data")

        # Mock Vision service response
        extraction_service.vision_service.detect_text_from_pdf = AsyncMock(
            return_value=(
                "PDF OCR Text",
                {
                    "blocks": [],
                    "text_length": 12,
                    "word_count": 3,
                    "page_count": 1,
                    "engine": "google_vision",
                },
            )
        )

        text, metadata = await extraction_service._perform_ocr(
            str(test_pdf), ".pdf", "eng"
        )

        assert text == "PDF OCR Text"
        assert metadata["engine"] == "google_vision"
        extraction_service.vision_service.detect_text_from_pdf.assert_called_once()

    @pytest.mark.asyncio
    async def test_perform_ocr_language_mapping(self, extraction_service, tmp_path):
        """Test that language codes are properly mapped."""
        test_image = tmp_path / "test.png"
        test_image.write_bytes(b"fake image data")

        extraction_service.vision_service.detect_text = AsyncMock(
            return_value=("Text", {"blocks": [], "engine": "google_vision"})
        )

        await extraction_service._perform_ocr(str(test_image), ".png", "eng")

        # Check that language hints were passed (mapped from 'eng' to 'en')
        call_args = extraction_service.vision_service.detect_text.call_args
        language_hints = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("language_hints")
        assert language_hints is not None
        assert "en" in language_hints

    @pytest.mark.asyncio
    async def test_perform_ocr_error_handling(self, extraction_service, tmp_path):
        """Test error handling in OCR processing."""
        test_image = tmp_path / "test.png"
        test_image.write_bytes(b"fake image data")

        extraction_service.vision_service.detect_text = AsyncMock(
            side_effect=OCRProcessingError("Vision API error")
        )

        with pytest.raises(OCRProcessingError):
            await extraction_service._perform_ocr(str(test_image), ".png", "eng")

    @pytest.mark.asyncio
    async def test_perform_ocr_generic_error(self, extraction_service, tmp_path):
        """Test handling of generic errors."""
        test_image = tmp_path / "test.png"
        test_image.write_bytes(b"fake image data")

        extraction_service.vision_service.detect_text = AsyncMock(
            side_effect=Exception("Unexpected error")
        )

        with pytest.raises(OCRProcessingError) as exc_info:
            await extraction_service._perform_ocr(str(test_image), ".png", "eng")

        assert "Google Vision OCR processing failed" in str(exc_info.value)

    def test_calculate_confidence_from_blocks(self, extraction_service):
        """Test confidence calculation from blocks."""
        blocks = [
            {"confidence": 0.9},
            {"confidence": 0.8},
            {"confidence": 0.7},
        ]

        confidence = extraction_service._calculate_confidence_from_blocks(blocks)
        assert confidence == pytest.approx(0.8)  # Average of 0.9, 0.8, 0.7

    def test_calculate_confidence_empty_blocks(self, extraction_service):
        """Test confidence calculation with empty blocks."""
        confidence = extraction_service._calculate_confidence_from_blocks([])
        assert confidence == 0.0

    def test_calculate_confidence_no_confidence_field(self, extraction_service):
        """Test confidence calculation when blocks don't have confidence."""
        blocks = [{"text": "test"}, {"text": "text"}]
        confidence = extraction_service._calculate_confidence_from_blocks(blocks)
        assert confidence == 1.0  # Default high confidence

