-- Migration: Add 'scanned' value to document_status_enum
-- This migration adds the 'scanned' status to track documents that have been OCR'd
-- but don't have a template applied yet (ready for template application)

DO $$
BEGIN
    -- Check if 'scanned' already exists in the enum
    IF NOT EXISTS (
        SELECT 1 
        FROM pg_enum 
        WHERE enumlabel = 'scanned' 
        AND enumtypid = (
            SELECT oid 
            FROM pg_type 
            WHERE typname = 'document_status_enum'
        )
    ) THEN
        -- Check if enum type exists
        IF EXISTS (
            SELECT 1 FROM pg_type WHERE typname = 'document_status_enum'
        ) THEN
            -- Add 'scanned' to the enum
            ALTER TYPE document_status_enum ADD VALUE 'scanned';
            RAISE NOTICE 'Added ''scanned'' to document_status_enum';
        ELSE
            RAISE NOTICE 'document_status_enum does not exist, skipping migration';
        END IF;
    ELSE
        RAISE NOTICE '''scanned'' already exists in document_status_enum';
    END IF;
END $$;

