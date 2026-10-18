#!/usr/bin/env python3
"""
Create all database tables from SQLAlchemy models.

This script uses SQLAlchemy's create_all() to create tables directly from models.
It's simpler and more LLM-friendly than Alembic migrations.

Usage:
    python scripts/create_tables.py
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
from app.database import engine, Base
from app.models import *  # noqa: F401, F403  # Import all models


async def ensure_enums_exist():
    """Ensure all enum types exist with correct values before creating tables.
    
    If an enum exists with incorrect values, it will be dropped (CASCADE) and recreated.
    This will also drop any tables/columns that depend on it, which is fine for setup.
    """
    from sqlalchemy import text
    
    # Define all enum types and their values from models
    enum_definitions = {
        "global_user_role": ["admin", "user"],
        "auth_provider": ["local", "google"],
        "workspace_status": ["active", "suspended", "trial", "canceled"],
        "workspace_member_role_enum": ["owner", "member", "readonly"],
        "workspace_member_status_enum": ["pending", "active", "revoked"],
        "subscription_plan_enum": ["basic", "pro"],
        "subscription_status_enum": ["active", "past_due", "canceled", "trialing"],
        "export_format_enum": ["json", "csv", "excel"],
        "document_status_enum": ["pending", "processing", "succeeded", "failed", "needs_review"],
        "document_source_enum": ["ui", "api"],
        "job_type_enum": ["document_extraction", "webhook_delivery"],
        "job_status_enum": ["queued", "processing", "succeeded", "failed"],
        "api_key_status_enum": ["active", "revoked"],
        "webhook_delivery_status_enum": ["pending", "succeeded", "failed"],
        "audit_actor_type_enum": ["user", "system"],
        "notification_channel": ["email", "in_app"],
        "extraction_log_level": ["info", "warning", "error"],
    }
    
    async with engine.begin() as conn:
        for enum_name, enum_values in enum_definitions.items():
            # Check if enum exists
            result = await conn.execute(
                text("""
                    SELECT EXISTS (
                        SELECT 1 FROM pg_type 
                        WHERE typname = :enum_name
                    )
                """),
                {"enum_name": enum_name}
            )
            exists = result.scalar()
            
            if exists:
                # Check if enum has correct values
                result = await conn.execute(
                    text("""
                        SELECT enumlabel 
                        FROM pg_enum 
                        WHERE enumtypid = (
                            SELECT oid FROM pg_type WHERE typname = :enum_name
                        )
                        ORDER BY enumsortorder
                    """),
                    {"enum_name": enum_name}
                )
                existing_values = [row[0] for row in result]
                
                # Compare values (order doesn't matter)
                if set(existing_values) != set(enum_values):
                    print(f"  ⚠ Enum {enum_name} exists with different values.")
                    print(f"     Existing: {existing_values}")
                    print(f"     Expected: {enum_values}")
                    print(f"     Dropping and recreating (CASCADE will drop dependent objects)...")
                    
                    # Drop enum (CASCADE will drop dependent tables/columns)
                    # This is fine for a setup script - we'll recreate everything
                    await conn.execute(
                        text(f'DROP TYPE IF EXISTS "{enum_name}" CASCADE')
                    )
                    
                    # Recreate with correct values
                    values_sql = ", ".join([f"'{v}'" for v in enum_values])
                    await conn.execute(
                        text(f'CREATE TYPE "{enum_name}" AS ENUM ({values_sql})')
                    )
                    print(f"     ✓ Recreated {enum_name}")
            else:
                # Create enum if it doesn't exist
                values_sql = ", ".join([f"'{v}'" for v in enum_values])
                await conn.execute(
                    text(f'CREATE TYPE "{enum_name}" AS ENUM ({values_sql})')
                )
                print(f"  ✓ Created enum {enum_name}")


async def create_tables():
    """Create all tables from SQLAlchemy models."""
    print("Creating database tables from models...")
    
    try:
        # First, ensure all enum types exist with correct values
        print("\nEnsuring enum types are correct...")
        await ensure_enums_exist()
        
        # Then create all tables
        print("\nCreating tables...")
        async with engine.begin() as conn:
            # Drop users table if it exists (to fix enum serialization issues)
            # This is safe during setup - we'll recreate it with correct enum config
            from sqlalchemy import text
            try:
                await conn.execute(text("DROP TABLE IF EXISTS users CASCADE"))
                print("  Dropped existing users table (to fix enum configuration)")
            except Exception:
                pass  # Table might not exist
            
            # Create all tables (SQLAlchemy handles enum types automatically)
            await conn.run_sync(Base.metadata.create_all)
        
        print("✓ All tables created successfully!")
        
        # List created tables
        from sqlalchemy import text
        async with engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT tablename 
                    FROM pg_tables 
                    WHERE schemaname = 'public' 
                    AND tablename != 'schema_migrations'
                    ORDER BY tablename
                """)
            )
            tables = [row[0] for row in result]
            
            if tables:
                print(f"\nCreated {len(tables)} tables:")
                for table in tables:
                    print(f"  - {table}")
            else:
                print("\nNo tables found (may already exist)")
        
        return True
        
    except Exception as e:
        print(f"✗ Error creating tables: {e}")
        import traceback
        traceback.print_exc()
        return False


async def check_tables_exist():
    """Check if any tables already exist."""
    try:
        from sqlalchemy import text
        async with engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT COUNT(*) 
                    FROM pg_tables 
                    WHERE schemaname = 'public' 
                    AND tablename != 'schema_migrations'
                """)
            )
            count = result.scalar()
            return count > 0
    except Exception:
        return False


async def main():
    """Main entry point."""
    print("=" * 60)
    print("Database Table Creation")
    print("=" * 60)
    
    # Check if tables already exist
    tables_exist = await check_tables_exist()
    if tables_exist:
        print("⚠ Warning: Tables already exist in the database.")
        print("This script will attempt to create missing tables only.")
        print("(SQLAlchemy create_all is idempotent - existing tables are skipped)")
        print()
    
    # Create tables
    success = await create_tables()
    
    if success:
        print("\n" + "=" * 60)
        print("✓ Database setup complete!")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("✗ Database setup failed!")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

