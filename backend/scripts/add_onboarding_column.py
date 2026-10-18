#!/usr/bin/env python3
"""
Migration script to add onboarding_completed column to workspaces table.

This script adds the missing onboarding_completed column to the workspaces table
if it doesn't already exist.

Usage:
    python scripts/add_onboarding_column.py
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

# Import after environment is loaded and path is set
from app.database import engine
from sqlalchemy import text


async def add_onboarding_column():
    """Add onboarding_completed column to workspaces table if it doesn't exist."""
    print("Checking for onboarding_completed column in workspaces table...")
    
    try:
        async with engine.begin() as conn:
            # Check if column already exists
            result = await conn.execute(
                text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'workspaces' 
                    AND column_name = 'onboarding_completed'
                """)
            )
            column_exists = result.fetchone() is not None
            
            if column_exists:
                print("[OK] Column 'onboarding_completed' already exists. No migration needed.")
                return True
            
            # Add the column
            print("Adding 'onboarding_completed' column to workspaces table...")
            await conn.execute(
                text("""
                    ALTER TABLE workspaces 
                    ADD COLUMN onboarding_completed BOOLEAN NOT NULL DEFAULT false
                """)
            )
            print("[OK] Successfully added 'onboarding_completed' column!")
            return True
            
    except Exception as e:
        print(f"[ERROR] Error adding column: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main entry point."""
    print("=" * 60)
    print("Migration: Add onboarding_completed column")
    print("=" * 60)
    print()
    
    success = await add_onboarding_column()
    
    if success:
        print("\n" + "=" * 60)
        print("[OK] Migration completed successfully!")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("[ERROR] Migration failed!")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

