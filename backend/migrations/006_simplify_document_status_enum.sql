-- Migration: Simplify document_status_enum by removing 'needs_review' and 'queued', renaming 'succeeded' to 'completed'
-- This migration:
-- 1. Maps existing 'needs_review' status to 'completed'
-- 2. Maps existing 'queued' status to 'pending'
-- 3. Maps existing 'succeeded' status to 'completed'
-- 4. Removes 'needs_review' and 'queued' from enum
-- 5. Renames 'succeeded' to 'completed' in enum

DO $$
DECLARE
    v_exists boolean;
BEGIN
    -- Check if enum type exists
    SELECT EXISTS (
        SELECT 1 FROM pg_type WHERE typname = 'document_status_enum'
    ) INTO v_exists;

    IF v_exists THEN
        -- Step 1: Create new enum type with simplified values first
        CREATE TYPE document_status_enum_new AS ENUM ('pending', 'processing', 'completed', 'failed');

        -- Step 2: Add a temporary text column to hold converted values
        ALTER TABLE documents ADD COLUMN status_new text;
        
        -- Step 3: Map old statuses to new statuses in the text column
        UPDATE documents 
        SET status_new = CASE 
            WHEN status::text = 'needs_review' THEN 'completed'
            WHEN status::text = 'queued' THEN 'pending'
            WHEN status::text = 'succeeded' THEN 'completed'
            WHEN status::text = 'pending' THEN 'pending'
            WHEN status::text = 'processing' THEN 'processing'
            WHEN status::text = 'failed' THEN 'failed'
            ELSE 'pending'  -- Default fallback
        END;

        -- Step 4: Alter documents table to use new enum (convert from text)
        ALTER TABLE documents 
        ALTER COLUMN status TYPE document_status_enum_new 
        USING status_new::document_status_enum_new;

        -- Step 5: Drop temporary column
        ALTER TABLE documents DROP COLUMN status_new;

        -- Step 6: Drop old enum and rename new one
        DROP TYPE document_status_enum;
        ALTER TYPE document_status_enum_new RENAME TO document_status_enum;

        RAISE NOTICE 'Successfully simplified document_status_enum';
    ELSE
        RAISE NOTICE 'document_status_enum does not exist, skipping migration';
    END IF;
END $$;

