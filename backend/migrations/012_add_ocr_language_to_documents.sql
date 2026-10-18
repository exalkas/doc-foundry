-- Add ocr_language column to documents table
-- This column stores the Tesseract language code used for OCR processing
-- Defaults to 'eng' (English) for backward compatibility

ALTER TABLE documents
ADD COLUMN IF NOT EXISTS ocr_language VARCHAR(10) DEFAULT 'eng';

-- Update existing documents to have 'eng' as default if NULL
UPDATE documents
SET ocr_language = 'eng'
WHERE ocr_language IS NULL;

-- Add comment to column
COMMENT ON COLUMN documents.ocr_language IS 'Tesseract OCR language code (e.g., eng, ell for Greek, fra for French). Defaults to eng.';

