-- Migration: Ensure extraction_results.metadata column exists
-- This migration adds the metadata column if it doesn't exist

DO $$
BEGIN
    -- Check if column exists
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'extraction_results' 
        AND column_name = 'metadata'
    ) THEN
        -- Add the metadata column
        ALTER TABLE extraction_results 
        ADD COLUMN metadata JSON;
        
        RAISE NOTICE 'Added metadata column to extraction_results table';
    ELSE
        RAISE NOTICE 'metadata column already exists in extraction_results table';
    END IF;
END $$;

