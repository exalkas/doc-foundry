#!/usr/bin/env python3
"""
Complete database initialization script.

This script does everything needed to set up the database:
1. Creates database (if needed) - via setup_db.py
2. Creates all tables - via create_tables.py
3. Seeds initial data - via seed_db.py

Usage:
    python scripts/init_database.py
"""

import subprocess
import sys
import os
from pathlib import Path

backend_dir = Path(__file__).parent.parent
scripts_dir = backend_dir / "scripts"


def run_script(script_name: str, description: str) -> bool:
    """Run a Python script and return success status."""
    script_path = scripts_dir / script_name
    
    if not script_path.exists():
        print(f"✗ Script not found: {script_path}")
        return False
    
    print(f"\n{'=' * 60}")
    print(f"{description}")
    print(f"{'=' * 60}")
    
    try:
        # Set up environment with PYTHONPATH so scripts can import 'app' module
        env = os.environ.copy()
        pythonpath = str(backend_dir)
        if "PYTHONPATH" in env:
            pythonpath = f"{env['PYTHONPATH']}{os.pathsep}{pythonpath}"
        env["PYTHONPATH"] = pythonpath
        
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(backend_dir),
            env=env,
            check=False
        )
        
        if result.returncode == 0:
            print(f"✓ {description} completed successfully")
            return True
        else:
            print(f"✗ {description} failed with exit code {result.returncode}")
            return False
            
    except Exception as e:
        print(f"✗ Error running {script_name}: {e}")
        return False


def check_database_exists():
    """Check if database already exists by trying to connect."""
    import os
    from dotenv import load_dotenv
    
    # Load .env file
    env_path = backend_dir / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()
    
    db_name = os.getenv("DB_NAME", "docdata_saas")
    db_user = os.getenv("DB_USER", "docdata_saas")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    
    # If we don't have password, can't check - assume we need setup
    if not db_password:
        return False
    
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=db_host,
            port=int(db_port),
            user=db_user,
            password=db_password,
            database=db_name,
            connect_timeout=5
        )
        conn.close()
        return True
    except Exception:
        return False


def main():
    """Main entry point."""
    print("=" * 60)
    print("Complete Database Initialization")
    print("=" * 60)
    print()
    print("This will:")
    print("  1. Create database (if needed)")
    print("  2. Create all tables from models")
    print("  3. Seed initial data")
    print()
    
    # Step 1: Setup database (optional if database already exists)
    db_exists = check_database_exists()
    
    if db_exists:
        print("✓ Database already exists, skipping database setup")
        print("  (If you need to create database/user, run: python scripts/setup_db.py)")
    else:
        if not run_script("setup_db.py", "Database Setup"):
            print("\n⚠ Database setup failed or skipped.")
            print("  This may be okay if the database already exists.")
            print("  Continuing with table creation...")
            print()
    
    # Step 2: Create tables
    if not run_script("create_tables.py", "Table Creation"):
        print("\n✗ Table creation failed.")
        print("  Make sure:")
        print("    - Database exists")
        print("    - DB_NAME, DB_USER, DB_PASSWORD are set in .env")
        print("    - Database is accessible")
        sys.exit(1)
    
    # Step 3: Seed data
    if not run_script("seed_db.py", "Data Seeding"):
        print("\n⚠ Seeding failed, but tables were created.")
        print("You can run seed_db.py manually later.")
        # Don't exit on seeding failure - tables are more important
    
    print("\n" + "=" * 60)
    print("✓ Database initialization complete!")
    print("=" * 60)
    print("\nYou can now start the application.")
    sys.exit(0)


if __name__ == "__main__":
    main()

