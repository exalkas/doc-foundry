"""Tests for Google Vision service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.google_vision_service import GoogleVisionService, OCRProcessingError


class TestGoogleVisionService:
    """Test Google Vision service functionality."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for Google Vision."""
        with patch("app.services.google_vision_service.settings") as mock:
            mock.GOOGLE_CLOUD_PROJECT_ID = "test-project"
            mock.GOOGLE_CLOUD_VISION_CREDENTIALS_PATH = None
            mock.GOOGLE_CLOUD_VISION_TIMEOUT_SECONDS = 60
            mock.GOOGLE_CLOUD_VISION_MAX_PAGES_PER_REQUEST = 5
            mock.GOOGLE_CLOUD_VISION_ENABLE_ASYNC = True
            yield mock

    @pytest.fixture
    def vision_service(self, mock_settings):
        """Create Google Vision service instance with mocked client."""
        with patch("app.services.google_vision_service.vision.ImageAnnotatorClient"):
            service = GoogleVisionService()
            service.client = MagicMock()
            yield service

    def test_get_credentials_with_path(self, mock_settings):
        """Test getting credentials from file path."""
        mock_settings.GOOGLE_CLOUD_VISION_CREDENTIALS_PATH = "/path/to/creds.json"
        with patch("os.path.exists", return_value=True):
            with patch("app.services.google_vision_service.service_account.Credentials.from_service_account_file") as mock_creds:
                service = GoogleVisionService()
                mock_creds.assert_called_once_with("/path/to/creds.json")

    def test_get_credentials_adc(self, mock_settings):
        """Test using Application Default Credentials."""
        mock_settings.GOOGLE_CLOUD_VISION_CREDENTIALS_PATH = None
        with patch("os.path.exists", return_value=False):
            service = GoogleVisionService()
            assert service._get_credentials() is None  # ADC is None, client handles it

    @pytest.mark.asyncio
    async def test_detect_text_success(self, vision_service, tmp_path):
        """Test successful text detection from image."""
        # Create a test image file
        test_image = tmp_path / "test.png"
        test_image.write_bytes(b"fake image data")

        # Mock Vision API response
        mock_annotation = MagicMock()
        mock_annotation.description = "Test OCR Text"
        mock_annotation.bounding_poly.vertices = [
            MagicMock(x=0, y=0),
            MagicMock(x=100, y=0),
            MagicMock(x=100, y=50),
            MagicMock(x=0, y=50),
        ]

        mock_response = MagicMock()
        mock_response.text_annotations = [MagicMock(description="Test OCR Text"), mock_annotation]

        vision_service.client.text_detection = MagicMock(return_value=mock_response)

        with patch("PIL.Image.open") as mock_image:
            mock_img = MagicMock()
            mock_img.size = (200, 100)
            mock_image.return_value = mock_img

            text, metadata = await vision_service.detect_text(str(test_image))

            assert text == "Test OCR Text"
            assert metadata["engine"] == "google_vision"
            assert "blocks" in metadata

    @pytest.mark.asyncio
    async def test_detect_text_empty_response(self, vision_service, tmp_path):
        """Test handling empty OCR response."""
        test_image = tmp_path / "test.png"
        test_image.write_bytes(b"fake image data")

        mock_response = MagicMock()
        mock_response.text_annotations = []

        vision_service.client.text_detection = MagicMock(return_value=mock_response)

        with patch("PIL.Image.open") as mock_image:
            mock_img = MagicMock()
            mock_img.size = (200, 100)
            mock_image.return_value = mock_img

            text, metadata = await vision_service.detect_text(str(test_image))

            assert text == ""
            assert metadata["engine"] == "google_vision"
            assert metadata["blocks"] == []

    @pytest.mark.asyncio
    async def test_detect_text_error_handling(self, vision_service, tmp_path):
        """Test error handling in text detection."""
        test_image = tmp_path / "test.png"
        test_image.write_bytes(b"fake image data")

        vision_service.client.text_detection = MagicMock(
            side_effect=Exception("API Error")
        )

        with pytest.raises(OCRProcessingError):
            await vision_service.detect_text(str(test_image))

    def test_retry_with_backoff_success(self, vision_service):
        """Test retry logic with successful call."""
        func = MagicMock(return_value="success")
        result = vision_service._retry_with_backoff(func)
        assert result == "success"
        assert func.call_count == 1

    def test_retry_with_backoff_transient_error(self, vision_service):
        """Test retry logic with transient error."""
        from google.api_core import exceptions as google_exceptions

        func = MagicMock(
            side_effect=[
                google_exceptions.DeadlineExceeded("Timeout"),
                "success",
            ]
        )

        with patch("time.sleep"):  # Mock sleep to speed up test
            result = vision_service._retry_with_backoff(func, max_retries=3)
            assert result == "success"
            assert func.call_count == 2

    def test_retry_with_backoff_permanent_error(self, vision_service):
        """Test retry logic with permanent error (no retry)."""
        from google.api_core import exceptions as google_exceptions

        func = MagicMock(side_effect=google_exceptions.InvalidArgument("Invalid"))

        with pytest.raises(google_exceptions.InvalidArgument):
            vision_service._retry_with_backoff(func, max_retries=3)

        assert func.call_count == 1  # Should not retry

    def test_build_metadata_image(self, vision_service):
        """Test building metadata for image."""
        metadata = vision_service._build_metadata(
            "test text",
            [],
            "/path/to/image.png",
            width=100,
            height=200,
            is_pdf=False,
        )

        assert metadata["text_length"] == 9
        assert metadata["word_count"] == 2
        assert metadata["engine"] == "google_vision"
        assert metadata["dimensions"] == [100, 200]
        assert metadata["format"] == "png"

    def test_build_metadata_pdf(self, vision_service):
        """Test building metadata for PDF."""
        metadata = vision_service._build_metadata(
            "test text",
            [],
            "/path/to/doc.pdf",
            page_count=5,
            is_pdf=True,
        )

        assert metadata["text_length"] == 9
        assert metadata["engine"] == "google_vision"
        assert metadata["page_count"] == 5
        assert metadata["format"] == "pdf"

    def test_build_empty_metadata(self, vision_service):
        """Test building empty metadata."""
        metadata = vision_service._build_empty_metadata("/path/to/image.png", is_pdf=False)

        assert metadata["text_length"] == 0
        assert metadata["word_count"] == 0
        assert metadata["engine"] == "google_vision"
        assert metadata["blocks"] == []

