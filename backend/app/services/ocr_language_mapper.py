"""Language code mapping utilities for OCR services.

Maps various language code formats (Tesseract, ISO 639-1, etc.) to Google Vision API
language hints (ISO 639-1 format).
"""

from typing import List


# Mapping from Tesseract language codes to ISO 639-1 codes (Google Vision format)
TESSERACT_TO_ISO6391: dict[str, str] = {
    # Common languages
    "eng": "en",  # English
    "ell": "el",  # Greek
    "fra": "fr",  # French
    "spa": "es",  # Spanish
    "deu": "de",  # German
    "ita": "it",  # Italian
    "por": "pt",  # Portuguese
    "rus": "ru",  # Russian
    "jpn": "ja",  # Japanese
    "kor": "ko",  # Korean
    "chi_sim": "zh",  # Chinese Simplified
    "chi_tra": "zh-TW",  # Chinese Traditional
    "ara": "ar",  # Arabic
    "hin": "hi",  # Hindi
    "tur": "tr",  # Turkish
    "pol": "pl",  # Polish
    "nld": "nl",  # Dutch
    "swe": "sv",  # Swedish
    "nor": "no",  # Norwegian
    "dan": "da",  # Danish
    "fin": "fi",  # Finnish
    "ces": "cs",  # Czech
    "ron": "ro",  # Romanian
    "hun": "hu",  # Hungarian
    "bul": "bg",  # Bulgarian
    "hrv": "hr",  # Croatian
    "slk": "sk",  # Slovak
    "slv": "sl",  # Slovenian
    "est": "et",  # Estonian
    "lav": "lv",  # Latvian
    "lit": "lt",  # Lithuanian
    "vie": "vi",  # Vietnamese
    "tha": "th",  # Thai
    "ind": "id",  # Indonesian
    "msa": "ms",  # Malay
    "heb": "he",  # Hebrew
    "ukr": "uk",  # Ukrainian
    "cat": "ca",  # Catalan
    "srp": "sr",  # Serbian
    "mkd": "mk",  # Macedonian
    "bel": "be",  # Belarusian
    "isl": "is",  # Icelandic
    "gle": "ga",  # Irish
    "cym": "cy",  # Welsh
    "eus": "eu",  # Basque
    "glg": "gl",  # Galician
}


def map_language_code(lang_code: str) -> List[str]:
    """Map a language code to Google Vision API language hints.

    Supports multiple input formats:
    - Tesseract codes (e.g., 'eng', 'ell', 'fra')
    - ISO 639-1 codes (e.g., 'en', 'el', 'fr')
    - Multi-language codes (e.g., 'eng+fra' → ['en', 'fr'])

    Args:
        lang_code: Language code in various formats

    Returns:
        List of ISO 639-1 language codes for Google Vision API

    Examples:
        >>> map_language_code('eng')
        ['en']
        >>> map_language_code('eng+fra')
        ['en', 'fr']
        >>> map_language_code('en')
        ['en']
        >>> map_language_code('unknown')
        ['en']  # Default fallback
    """
    if not lang_code or not lang_code.strip():
        return ["en"]  # Default to English

    lang_code = lang_code.strip().lower()

    # Handle multi-language codes (e.g., 'eng+fra')
    if "+" in lang_code:
        codes = [c.strip() for c in lang_code.split("+")]
        return [map_single_language_code(c) for c in codes if c]

    return [map_single_language_code(lang_code)]


def map_single_language_code(lang_code: str) -> str:
    """Map a single language code to ISO 639-1 format.

    Args:
        lang_code: Single language code

    Returns:
        ISO 639-1 language code (defaults to 'en' if not found)
    """
    lang_code = lang_code.strip().lower()

    # If already ISO 639-1 format (2 characters), return as-is
    if len(lang_code) == 2 and lang_code.isalpha():
        return lang_code

    # Try Tesseract code mapping
    if lang_code in TESSERACT_TO_ISO6391:
        return TESSERACT_TO_ISO6391[lang_code]

    # If it's a 3-character code that might be ISO 639-2, try direct lookup
    # (Some ISO 639-2 codes match Tesseract codes)
    if lang_code in TESSERACT_TO_ISO6391:
        return TESSERACT_TO_ISO6391[lang_code]

    # Default to English if mapping not found
    return "en"


def get_supported_languages() -> List[str]:
    """Get list of all supported language codes (ISO 639-1 format).

    Returns:
        List of ISO 639-1 language codes supported by the mapper
    """
    return sorted(set(TESSERACT_TO_ISO6391.values()))

