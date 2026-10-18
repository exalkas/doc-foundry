"""Tests for OCR language mapper."""

import pytest

from app.services.ocr_language_mapper import (
    get_supported_languages,
    map_language_code,
    map_single_language_code,
)


class TestLanguageMapper:
    """Test language code mapping functionality."""

    def test_map_tesseract_code_to_iso(self):
        """Test mapping Tesseract codes to ISO 639-1."""
        assert map_single_language_code("eng") == "en"
        assert map_single_language_code("ell") == "el"
        assert map_single_language_code("fra") == "fr"
        assert map_single_language_code("spa") == "es"
        assert map_single_language_code("deu") == "de"

    def test_map_iso_code_unchanged(self):
        """Test that ISO 639-1 codes are returned as-is."""
        assert map_single_language_code("en") == "en"
        assert map_single_language_code("el") == "el"
        assert map_single_language_code("fr") == "fr"

    def test_map_unknown_code_defaults_to_english(self):
        """Test that unknown codes default to English."""
        assert map_single_language_code("unknown") == "en"
        assert map_single_language_code("xyz") == "en"

    def test_map_multi_language_code(self):
        """Test mapping multi-language codes."""
        result = map_language_code("eng+fra")
        assert "en" in result
        assert "fr" in result
        assert len(result) == 2

    def test_map_single_language_code_list(self):
        """Test that single codes return list with one element."""
        result = map_language_code("eng")
        assert result == ["en"]
        assert isinstance(result, list)

    def test_map_empty_code_defaults_to_english(self):
        """Test that empty codes default to English."""
        assert map_language_code("") == ["en"]
        assert map_language_code("   ") == ["en"]

    def test_get_supported_languages(self):
        """Test getting list of supported languages."""
        languages = get_supported_languages()
        assert isinstance(languages, list)
        assert "en" in languages
        assert "el" in languages
        assert "fr" in languages
        assert len(languages) > 0

    def test_case_insensitive_mapping(self):
        """Test that mapping is case-insensitive."""
        assert map_single_language_code("ENG") == "en"
        assert map_single_language_code("Eng") == "en"
        assert map_single_language_code("ell") == "el"
        assert map_single_language_code("ELL") == "el"

    def test_whitespace_handling(self):
        """Test that whitespace is handled correctly."""
        assert map_single_language_code("  eng  ") == "en"
        assert map_language_code("  eng+fra  ") == ["en", "fr"]

