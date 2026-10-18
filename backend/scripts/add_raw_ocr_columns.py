#!/usr/bin/env python3
"""
Add raw_ocr_text and raw_ocr_metadata columns to documents table.

Usage:
    python scripts/add_raw_ocr_columns.py
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env file and set up Python path
backend_dir = Path(__file__).parent.parent
env_path = backend_dir / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

# Add backend directory to Python path so we can import 'app'
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from app.database import engine


async def add_raw_ocr_columns():
    """Add raw_ocr_text and raw_ocr_metadata columns to documents table."""
    async with engine.begin() as conn:
        # Check if columns already exist
        check_query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'documents' 
            AND column_name IN ('raw_ocr_text', 'raw_ocr_metadata')
        """)
        result = await conn.execute(check_query)
        existing_columns = {row[0] for row in result.fetchall()}

        # Add raw_ocr_text column if it doesn't exist
        if "raw_ocr_text" not in existing_columns:
            print("Adding raw_ocr_text column...")
            await conn.execute(text("""
                ALTER TABLE documents 
                ADD COLUMN raw_ocr_text TEXT
            """))
            print("✓ Added raw_ocr_text column")
        else:
            print("✓ raw_ocr_text column already exists")

        # Add raw_ocr_metadata column if it doesn't exist
        if "raw_ocr_metadata" not in existing_columns:
            print("Adding raw_ocr_metadata column...")
            await conn.execute(text("""
                ALTER TABLE documents 
                ADD COLUMN raw_ocr_metadata JSONB
            """))
            print("✓ Added raw_ocr_metadata column")
        else:
            print("✓ raw_ocr_metadata column already exists")

        print("\nMigration completed successfully!")


if __name__ == "__main__":
    try:
        asyncio.run(add_raw_ocr_columns())
    except Exception as e:
        print(f"Error running migration: {e}")
        sys.exit(1)

