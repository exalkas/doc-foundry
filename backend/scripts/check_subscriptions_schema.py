#!/usr/bin/env python3
"""Check subscriptions table schema."""

import asyncio
import sys
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.database import engine
from sqlalchemy import text

async def check_schema():
    """Check subscriptions table columns."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'subscriptions'
                ORDER BY ordinal_position
            """)
        )
        columns = result.all()
        
        print("Subscriptions table columns:")
        print("=" * 60)
        for col in columns:
            print(f"  {col[0]:30} {col[1]:20} nullable={col[2]}")
        
        # Check if user_id exists
        column_names = [col[0] for col in columns]
        if 'user_id' not in column_names:
            print("\n⚠ WARNING: user_id column is missing!")
            print("Migration 008 may not have run successfully.")
        else:
            print("\n✓ user_id column exists")

if __name__ == "__main__":
    asyncio.run(check_schema())

