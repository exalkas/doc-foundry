#!/usr/bin/env python3
"""
Check the actual enum values in the database.
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
    print("Checking enum values in database...")
    print(f"Connecting to database: {db_name} on {db_host}:{db_port} as {db_user}")
    
    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user=db_user,
            password=db_password,
            host=db_host,
            port=db_port
        )
        
        with conn.cursor() as cur:
            # Get all enum values
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
            print(f"\nEnum values in document_status_enum:")
            for i, value in enumerate(values, 1):
                print(f"  {i}. {value}")
            
            if 'queued' in values:
                print("\n✓ 'queued' is present in the enum")
            else:
                print("\n✗ 'queued' is NOT present in the enum")
        
        conn.close()
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

