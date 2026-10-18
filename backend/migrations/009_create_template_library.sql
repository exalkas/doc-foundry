-- Migration: Create template_library table and add library_template_id to templates table
-- This migration is idempotent and safe to run multiple times.

DO $$
BEGIN
    -- Check if template_library table already exists
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.tables 
        WHERE table_name = 'template_library'
    ) THEN
        -- Create template_category_enum if it doesn't exist
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'template_category_enum') THEN
                CREATE TYPE template_category_enum AS ENUM (
                    'accounting_finance',
                    'logistics',
                    'ecommerce',
                    'hr_legal'
                );
            END IF;
        END $$;

        -- Create template_library table
        CREATE TABLE template_library (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(255) NOT NULL,
            description TEXT,
            category template_category_enum NOT NULL,
            document_type VARCHAR(128),
            field_schema JSONB NOT NULL,
            default_export_format export_format_enum NOT NULL DEFAULT 'json',
            preview_image_url VARCHAR(512),
            tags TEXT[],
            is_active BOOLEAN NOT NULL DEFAULT true,
            usage_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        -- Create indexes
        CREATE INDEX ix_template_library_category ON template_library(category);
        CREATE INDEX ix_template_library_is_active ON template_library(is_active);
        CREATE INDEX ix_template_library_category_active ON template_library(category, is_active);
        CREATE INDEX ix_template_library_name ON template_library(name);

        RAISE NOTICE 'Created template_library table';
    ELSE
        RAISE NOTICE 'template_library table already exists';
    END IF;
END $$;

-- Add library_template_id column to templates table if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'templates' 
        AND column_name = 'library_template_id'
    ) THEN
        ALTER TABLE templates 
        ADD COLUMN library_template_id UUID 
        REFERENCES template_library(id) ON DELETE SET NULL;

        CREATE INDEX ix_templates_library_template_id ON templates(library_template_id);

        RAISE NOTICE 'Added library_template_id column to templates table';
    ELSE
        RAISE NOTICE 'library_template_id column already exists in templates table';
    END IF;
END $$;

-- Note: Seed data should be inserted via Python script: python scripts/seed_template_library.py
-- This ensures proper field_schema JSON structure and allows for easier updates

