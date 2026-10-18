-- Migration: Add 'needs_review' value to document_status_enum
-- This migration is idempotent and safe to run multiple times.

DO $$
BEGIN
    -- Check if 'needs_review' already exists in the enum
    IF NOT EXISTS (
        SELECT 1 
        FROM pg_enum 
        WHERE enumlabel = 'needs_review' 
        AND enumtypid = (
            SELECT oid 
            FROM pg_type 
            WHERE typname = 'document_status_enum'
        )
    ) THEN
        -- Add 'needs_review' to the enum
        ALTER TYPE document_status_enum ADD VALUE 'needs_review';
        RAISE NOTICE 'Added ''needs_review'' to document_status_enum';
    ELSE
        RAISE NOTICE '''needs_review'' already exists in document_status_enum';
    END IF;
END $$;

