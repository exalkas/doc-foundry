#!/usr/bin/env python3
"""
Verify that the migration was applied and check enum status.
"""

import json
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

# Load environment variables
backend_dir = Path(__file__).parent.parent
env_path = backend_dir / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

# Try to load from db_config.json as fallback
db_config_path = backend_dir / "db_config.json"
if db_config_path.exists():
    with open(db_config_path) as f:
        db_config = json.load(f)
    os.environ.setdefault("DB_NAME", db_config.get("db_name", "docdata_saas"))
    os.environ.setdefault("DB_USER", db_config.get("db_user", "docdata_saas"))
    os.environ.setdefault("DB_PASSWORD", db_config.get("db_password", ""))
    os.environ.setdefault("DB_HOST", db_config.get("db_host", "localhost"))
    os.environ.setdefault("DB_PORT", str(db_config.get("db_port", 5432)))

db_name = os.getenv("DB_NAME", "docdata_saas")
db_user = os.getenv("DB_USER", "docdata_saas")
db_password = os.getenv("DB_PASSWORD", "")
db_host = os.getenv("DB_HOST", "localhost")
db_port = int(os.getenv("DB_PORT", "5432"))

def main():
    print("Verifying enum migration status...")
    print(f"Database: {db_name} on {db_host}:{db_port}")
    print()
    
    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user=db_user,
            password=db_password,
            host=db_host,
            port=db_port
        )
        
        with conn.cursor() as cur:
            # Check enum values
            cur.execute("""
                SELECT enumlabel 
                FROM pg_enum 
                WHERE enumtypid = (
                    SELECT oid 
                    FROM pg_type 
                    WHERE typname = 'document_status_enum'
                )
                ORDER BY enumsortorder;
            """)
            
            values = [row[0] for row in cur.fetchall()]
            print("Enum values in document_status_enum:")
            for value in values:
                marker = " [OK]" if value == "queued" else ""
                print(f"  - {value}{marker}")
            
            print()
            if 'queued' in values:
                print("SUCCESS: 'queued' is present in the database enum")
            else:
                print("ERROR: 'queued' is NOT present in the database enum")
                return 1
            
            # Check migration record
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'schema_migrations'
                );
            """)
            has_migrations_table = cur.fetchone()[0]
            
            if has_migrations_table:
                cur.execute("SELECT version FROM schema_migrations ORDER BY version")
                applied = [row[0] for row in cur.fetchall()]
                print(f"\nApplied migrations: {', '.join(applied) if applied else '(none)'}")
                
                if '002' in applied:
                    print("SUCCESS: Migration 002 (add queued) is recorded")
                else:
                    print("NOTE: Migration 002 is not recorded in schema_migrations table")
                    print("      This is OK if migrations were applied manually")
            else:
                print("\nNOTE: schema_migrations table does not exist")
                print("      This is OK if migrations were applied manually")
        
        conn.close()
        print("\n" + "="*60)
        print("RECOMMENDATION:")
        print("If you're still seeing the error, restart the worker process")
        print("to refresh SQLAlchemy's cached enum metadata.")
        print("="*60)
        return 0
        
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

