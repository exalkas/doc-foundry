#!/usr/bin/env python3
"""Add library_template_id column to templates table if it doesn't exist."""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
backend_dir = Path(__file__).parent.parent
env_path = backend_dir / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

# Add backend directory to Python path
sys.path.insert(0, str(backend_dir))

from app.database import engine
from sqlalchemy import text


async def add_column():
    """Add library_template_id column to templates table."""
    print("Checking if library_template_id column exists...")
    
    async with engine.connect() as conn:
        # Check if column exists
        result = await conn.execute(
            text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'templates' 
                AND column_name = 'library_template_id'
            """)
        )
        exists = result.fetchone() is not None
        
        if exists:
            print("✓ Column library_template_id already exists")
            return True
        
        print("Adding library_template_id column...")
        
        # First, check if template_library table exists (needed for foreign key)
        result = await conn.execute(
            text("""
                SELECT 1 
                FROM information_schema.tables 
                WHERE table_name = 'template_library'
            """)
        )
        template_library_exists = result.fetchone() is not None
        
        if not template_library_exists:
            print("Creating template_library table first...")
            # Create the enum type if it doesn't exist
            await conn.execute(
                text("""
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
                """)
            )
            await conn.commit()
            
            # Create template_library table
            await conn.execute(
                text("""
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
                """)
            )
            await conn.commit()
            
            # Create indexes (one at a time)
            await conn.execute(text("CREATE INDEX ix_template_library_category ON template_library(category);"))
            await conn.commit()
            await conn.execute(text("CREATE INDEX ix_template_library_is_active ON template_library(is_active);"))
            await conn.commit()
            await conn.execute(text("CREATE INDEX ix_template_library_category_active ON template_library(category, is_active);"))
            await conn.commit()
            await conn.execute(text("CREATE INDEX ix_template_library_name ON template_library(name);"))
            await conn.commit()
            print("✓ Created template_library table")
        
        # Add the column
        await conn.execute(
            text("""
                ALTER TABLE templates 
                ADD COLUMN library_template_id UUID 
                REFERENCES template_library(id) ON DELETE SET NULL;
            """)
        )
        await conn.commit()
        
        # Create index
        await conn.execute(
            text("""
                CREATE INDEX ix_templates_library_template_id ON templates(library_template_id);
            """)
        )
        await conn.commit()
        
        print("✓ Added library_template_id column to templates table")
        print("✓ Created index on library_template_id")
        
        # Mark migration as applied
        await conn.execute(
            text("""
                INSERT INTO schema_migrations (version) 
                VALUES ('009')
                ON CONFLICT (version) DO NOTHING;
            """)
        )
        await conn.commit()
        
        print("✓ Marked migration 009 as applied")
        return True


if __name__ == "__main__":
    try:
        success = asyncio.run(add_column())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

