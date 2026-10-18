-- Migration: Add 'queued' value to document_status_enum
-- This migration adds the 'queued' status to track documents that have been queued for processing

DO $$
BEGIN
    -- Check if 'queued' already exists in the enum
    IF NOT EXISTS (
        SELECT 1 
        FROM pg_enum 
        WHERE enumlabel = 'queued' 
        AND enumtypid = (
            SELECT oid 
            FROM pg_type 
            WHERE typname = 'document_status_enum'
        )
    ) THEN
        -- Add 'queued' to the enum
        ALTER TYPE document_status_enum ADD VALUE 'queued';
        RAISE NOTICE 'Added ''queued'' to document_status_enum';
    ELSE
        RAISE NOTICE '''queued'' already exists in document_status_enum';
    END IF;
END $$;

