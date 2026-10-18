-- Migration: Add ai_pages_processed column to usage_records table
-- This migration is idempotent and safe to run multiple times.

DO $$
BEGIN
    -- Check if column already exists
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'usage_records' 
        AND column_name = 'ai_pages_processed'
    ) THEN
        -- Add the column with default value
        ALTER TABLE usage_records 
        ADD COLUMN ai_pages_processed INTEGER NOT NULL DEFAULT 0;
        
        RAISE NOTICE 'Added ai_pages_processed column to usage_records table';
    ELSE
        RAISE NOTICE 'ai_pages_processed column already exists in usage_records table';
    END IF;
END $$;

