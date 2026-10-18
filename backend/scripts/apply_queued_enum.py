#!/usr/bin/env python3
"""
Apply the migration to add 'queued' to document_status_enum.
This script can be run directly to fix the enum issue.
"""

import json
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
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

migration_sql = """
DO $$
BEGIN
    -- Check if 'queued' already exists in the enum
    IF NOT EXISTS (
        SELECT 1 
        FROM pg_enum 
        WHERE enumlabel = 'queued' 
        AND enumtypid = (
            SELECT oid 
            FROM pg_type 
            WHERE typname = 'document_status_enum'
        )
    ) THEN
        -- Add 'queued' to the enum
        ALTER TYPE document_status_enum ADD VALUE 'queued';
        RAISE NOTICE 'Added ''queued'' to document_status_enum';
    ELSE
        RAISE NOTICE '''queued'' already exists in document_status_enum';
    END IF;
END $$;
"""

def main():
    print("Applying migration to add 'queued' to document_status_enum...")
    print(f"Connecting to database: {db_name} on {db_host}:{db_port} as {db_user}")
    
    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user=db_user,
            password=db_password,
            host=db_host,
            port=db_port
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        with conn.cursor() as cur:
            cur.execute(migration_sql)
            # Check for notices
            notices = conn.notices
            if notices:
                for notice in notices:
                    print(notice.strip())
        
        print("Migration applied successfully!")
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

