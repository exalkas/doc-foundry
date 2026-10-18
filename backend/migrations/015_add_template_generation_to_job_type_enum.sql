-- Migration: Add 'template_generation' value to job_type_enum
-- This migration adds the 'template_generation' job type for AI template generation jobs

DO $$
BEGIN
    -- Check if 'template_generation' already exists in the enum
    IF NOT EXISTS (
        SELECT 1 
        FROM pg_enum 
        WHERE enumlabel = 'template_generation' 
        AND enumtypid = (
            SELECT oid 
            FROM pg_type 
            WHERE typname = 'job_type_enum'
        )
    ) THEN
        -- Check if enum type exists
        IF EXISTS (
            SELECT 1 FROM pg_type WHERE typname = 'job_type_enum'
        ) THEN
            -- Add 'template_generation' to the enum
            ALTER TYPE job_type_enum ADD VALUE 'template_generation';
            RAISE NOTICE 'Added ''template_generation'' to job_type_enum';
        ELSE
            RAISE NOTICE 'job_type_enum does not exist, skipping migration';
        END IF;
    ELSE
        RAISE NOTICE '''template_generation'' already exists in job_type_enum';
    END IF;
END $$;

