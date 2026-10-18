"""Check migration status and manually apply if needed."""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
backend_dir = Path(__file__).parent
env_path = backend_dir / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

# Add backend directory to Python path
sys.path.insert(0, str(backend_dir))

from app.database import engine
from sqlalchemy import text


async def check_and_fix():
    """Check migration status and apply fix if needed."""
    print("Checking migration status...")
    print()
    
    try:
        async with engine.begin() as conn:
            # Check if migration 012 was recorded
            result = await conn.execute(
                text("SELECT version FROM schema_migrations WHERE version = '012'")
            )
            migration_recorded = result.fetchone() is not None
            
            # Check if column exists
            result = await conn.execute(
                text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'documents'
                    AND column_name = 'ocr_language'
                """)
            )
            column_exists = result.fetchone() is not None
            
            print(f"Migration 012 recorded: {migration_recorded}")
            print(f"Column ocr_language exists: {column_exists}")
            print()
            
            if migration_recorded and not column_exists:
                print("[WARNING] Migration was recorded but column doesn't exist!")
                print("This suggests the migration SQL didn't execute properly.")
                print()
                print("Manually applying the migration...")
                
                # Manually apply the migration
                await conn.execute(
                    text("""
                        ALTER TABLE documents
                        ADD COLUMN IF NOT EXISTS ocr_language VARCHAR(10) DEFAULT 'eng'
                    """)
                )
                
                await conn.execute(
                    text("""
                        UPDATE documents
                        SET ocr_language = 'eng'
                        WHERE ocr_language IS NULL
                    """)
                )
                
                print("[OK] Column added successfully!")
                
            elif not migration_recorded and not column_exists:
                print("[INFO] Migration not recorded and column doesn't exist.")
                print("Applying migration...")
                
                # Apply migration
                await conn.execute(
                    text("""
                        ALTER TABLE documents
                        ADD COLUMN IF NOT EXISTS ocr_language VARCHAR(10) DEFAULT 'eng'
                    """)
                )
                
                await conn.execute(
                    text("""
                        UPDATE documents
                        SET ocr_language = 'eng'
                        WHERE ocr_language IS NULL
                    """)
                )
                
                # Record migration
                await conn.execute(
                    text("INSERT INTO schema_migrations (version) VALUES ('012')")
                )
                
                print("[OK] Migration applied and recorded!")
                
            elif column_exists:
                print("[OK] Column already exists - no action needed!")
            else:
                print("[ERROR] Unexpected state!")
                return False
            
            # Verify column now exists
            result = await conn.execute(
                text("""
                    SELECT column_name, data_type, column_default
                    FROM information_schema.columns
                    WHERE table_name = 'documents'
                    AND column_name = 'ocr_language'
                """)
            )
            
            row = result.fetchone()
            if row:
                print()
                print("[SUCCESS] Column verified:")
                print(f"    Name: {row[0]}")
                print(f"    Type: {row[1]}")
                print(f"    Default: {row[2]}")
                return True
            else:
                print("[ERROR] Column still doesn't exist after applying!")
                return False
                
    except Exception as e:
        print(f"[ERROR] Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(check_and_fix())
    sys.exit(0 if success else 1)

