-- Migration: Add deleted_at column to documents table for soft delete
-- This migration adds a deleted_at timestamp field to enable soft deletion of documents
-- while preserving scanned data (OCR text, metadata, extraction results)

DO $$
BEGIN
    -- Check if deleted_at column already exists
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'documents' 
        AND column_name = 'deleted_at'
    ) THEN
        -- Add deleted_at column
        ALTER TABLE documents 
        ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE NULL;
        
        -- Create index for efficient filtering of non-deleted documents
        CREATE INDEX IF NOT EXISTS ix_documents_deleted_at 
        ON documents(deleted_at) 
        WHERE deleted_at IS NULL;
        
        -- Create composite index for workspace + deleted_at queries
        CREATE INDEX IF NOT EXISTS ix_documents_workspace_deleted_at 
        ON documents(workspace_id, deleted_at) 
        WHERE deleted_at IS NULL;
        
        RAISE NOTICE 'Added deleted_at column to documents table';
    ELSE
        RAISE NOTICE 'deleted_at column already exists in documents table';
    END IF;
END $$;

