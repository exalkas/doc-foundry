#!/usr/bin/env python3
"""Fix missing stripe_customer_id column in users table."""

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


async def fix_column():
    """Add stripe_customer_id column if it doesn't exist."""
    print("Checking for stripe_customer_id column in users table...")
    
    try:
        async with engine.begin() as conn:
            # Check if column exists
            check_result = await conn.execute(
                text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'users' 
                    AND column_name = 'stripe_customer_id'
                """)
            )
            exists = check_result.fetchone() is not None
            
            if exists:
                print("✓ Column stripe_customer_id already exists")
            else:
                print("Adding stripe_customer_id column...")
                # Add column
                await conn.execute(
                    text("""
                        ALTER TABLE users
                        ADD COLUMN stripe_customer_id VARCHAR(255);
                    """)
                )
                # Add index
                await conn.execute(
                    text("""
                        CREATE INDEX IF NOT EXISTS ix_users_stripe_customer_id 
                        ON users(stripe_customer_id) 
                        WHERE stripe_customer_id IS NOT NULL;
                    """)
                )
                print("✓ Column stripe_customer_id added successfully")
        
        print("\n✓ Fix completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(fix_column())
    sys.exit(0 if success else 1)

