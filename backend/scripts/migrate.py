#!/usr/bin/env python3
"""
Simple SQL-based migration system.

This is a lightweight alternative to Alembic that uses plain SQL files.
LLMs can easily generate SQL migrations.

Usage:
    python scripts/migrate.py migrate    # Apply pending migrations
    python scripts/migrate.py status     # Show migration status
    python scripts/migrate.py create <name>  # Create new migration file (manual)
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load .env file
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


async def ensure_schema_migrations_table():
    """Create schema_migrations table if it doesn't exist."""
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.execute(
            text("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version VARCHAR(255) PRIMARY KEY,
                    applied_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
            """)
        )


async def get_applied_migrations():
    """Get list of applied migration versions."""
    from sqlalchemy import text
    await ensure_schema_migrations_table()
    
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT version FROM schema_migrations ORDER BY version")
        )
        return [row[0] for row in result]


async def get_pending_migrations():
    """Get list of pending migration files."""
    migrations_dir = backend_dir / "migrations"
    
    if not migrations_dir.exists():
        return []
    
    # Get all SQL files
    migration_files = sorted(migrations_dir.glob("*.sql"))
    
    # Extract version numbers (e.g., "001_initial.sql" -> "001")
    pending = []
    applied = await get_applied_migrations()
    
    for file in migration_files:
        version = file.stem.split("_")[0]  # Get number part
        if version not in applied:
            pending.append((version, file))
    
    return pending


async def apply_migration(version: str, file_path: Path):
    """Apply a single migration file."""
    from sqlalchemy import text
    import re
    print(f"  Applying {file_path.name}...")
    
    sql_content = file_path.read_text(encoding="utf-8")
    
    # Split SQL into individual statements
    # Handle DO $$ blocks as single statements (they contain semicolons inside)
    statements = []
    
    # Use regex to find DO $$ blocks and split on them
    # Pattern: DO $$ ... END $$;
    do_block_pattern = r'(DO\s+\$\$.*?END\s+\$\$;)'
    
    # Find all DO blocks
    do_blocks = re.findall(do_block_pattern, sql_content, re.DOTALL | re.IGNORECASE)
    
    # Remove DO blocks from content temporarily (replace with placeholder)
    remaining_content = sql_content
    for i, block in enumerate(do_blocks):
        placeholder = f"__DO_BLOCK_PLACEHOLDER_{i}__"
        remaining_content = remaining_content.replace(block, placeholder, 1)
        statements.append(block.strip())
    
    # Split remaining content by semicolons (outside of DO blocks)
    # But preserve placeholders
    parts = re.split(r';\s*\n', remaining_content)
    for part in parts:
        part = part.strip()
        if not part or part.startswith('--'):
            continue
        # Check if this part contains a placeholder (shouldn't happen, but handle it)
        if '__DO_BLOCK_PLACEHOLDER_' in part:
            # Skip - DO blocks are already added
            continue
        statements.append(part + ';')
    
    # Filter out empty statements and comments-only statements
    statements = [s for s in statements if s.strip() and not s.strip().startswith('--')]
    
    async with engine.begin() as conn:
        # Execute each statement separately using exec_driver_sql
        # This bypasses asyncpg's prepared statement limitation
        for stmt in statements:
            if stmt.strip():
                await conn.exec_driver_sql(stmt)
        
        # Record migration
        await conn.execute(
            text("INSERT INTO schema_migrations (version) VALUES (:version)"),
            {"version": version}
        )
    
    print(f"    [OK] Applied {file_path.name}")


async def migrate():
    """Apply all pending migrations."""
    print("Checking for pending migrations...")
    
    pending = await get_pending_migrations()
    
    if not pending:
        print("[OK] No pending migrations")
        return True
    
    print(f"Found {len(pending)} pending migration(s):")
    for version, file_path in pending:
        print(f"  - {file_path.name}")
    
    print("\nApplying migrations...")
    
    try:
        for version, file_path in pending:
            await apply_migration(version, file_path)
        
        print("\n[SUCCESS] All migrations applied successfully!")
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Error applying migrations: {e}")
        import traceback
        traceback.print_exc()
        return False


async def status():
    """Show migration status."""
    print("Migration Status")
    print("=" * 60)
    
    applied = await get_applied_migrations()
    pending = await get_pending_migrations()
    
    print(f"\nApplied migrations: {len(applied)}")
    if applied:
        for version in applied:
            print(f"  [OK] {version}")
    
    print(f"\nPending migrations: {len(pending)}")
    if pending:
        for version, file_path in pending:
            print(f"  [PENDING] {file_path.name}")
    else:
        print("  (none)")
    
    print()


async def create_migration(name: str):
    """Create a new migration file."""
    migrations_dir = backend_dir / "migrations"
    migrations_dir.mkdir(exist_ok=True)
    
    # Get next migration number
    existing_files = sorted(migrations_dir.glob("*.sql"))
    if existing_files:
        last_file = existing_files[-1]
        last_num = int(last_file.stem.split("_")[0])
        next_num = last_num + 1
    else:
        next_num = 1
    
    # Create migration file
    version = f"{next_num:03d}"
    filename = f"{version}_{name}.sql"
    file_path = migrations_dir / filename
    
    file_path.write_text(
        f"-- Migration: {name}\n"
        f"-- Created: {datetime.utcnow().isoformat()}\n"
        f"\n"
        f"-- Add your SQL migration here\n"
        f"\n"
    )
    
    print(f"[OK] Created migration file: {file_path}")
    print(f"  Edit it and then run: python scripts/migrate.py migrate")


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python scripts/migrate.py migrate          # Apply pending migrations")
        print("  python scripts/migrate.py status           # Show migration status")
        print("  python scripts/migrate.py create <name>    # Create new migration")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "migrate":
        success = await migrate()
        sys.exit(0 if success else 1)
    elif command == "status":
        await status()
        sys.exit(0)
    elif command == "create":
        if len(sys.argv) < 3:
            print("Error: Migration name required")
            print("Usage: python scripts/migrate.py create <name>")
            sys.exit(1)
        await create_migration(sys.argv[2])
        sys.exit(0)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

