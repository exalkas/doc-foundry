-- Migration: Fix documents with COMPLETED status but no extraction results
-- These documents should have SCANNED status instead
-- This migration updates documents that have status 'completed' but no extraction_results
-- to have status 'scanned'

DO $$
DECLARE
    v_updated_count integer;
BEGIN
    -- Check if enum type exists and has 'scanned' value
    IF EXISTS (
        SELECT 1 FROM pg_type WHERE typname = 'document_status_enum'
    ) AND EXISTS (
        SELECT 1 FROM pg_enum 
        WHERE enumlabel = 'scanned' 
        AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'document_status_enum')
    ) THEN
        -- Update documents that have status 'completed' but no extraction_results
        UPDATE documents d
        SET status = 'scanned'::document_status_enum
        WHERE d.status = 'completed'::document_status_enum
        AND NOT EXISTS (
            SELECT 1 
            FROM extraction_results er 
            WHERE er.document_id = d.id
        );
        
        GET DIAGNOSTICS v_updated_count = ROW_COUNT;
        RAISE NOTICE 'Updated % documents from completed to scanned (no extraction results)', v_updated_count;
    ELSE
        RAISE NOTICE 'document_status_enum does not exist or scanned value not found, skipping migration';
    END IF;
END $$;

