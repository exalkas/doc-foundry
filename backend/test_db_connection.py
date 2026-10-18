"""
Test script to verify database connection and .env file loading.
This helps debug connection issues by showing what credentials are being used.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import psycopg2
from psycopg2 import OperationalError

# Load .env file from the backend directory
backend_dir = Path(__file__).parent
env_path = backend_dir / ".env"

print(f"Looking for .env file at: {env_path}")
print(f".env file exists: {env_path.exists()}\n")

if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print("[OK] Loaded .env file")
else:
    load_dotenv()
    print("[WARNING] .env file not found, using default load_dotenv() behavior")

# Get environment variables
db_host = os.getenv("DB_HOST", "localhost")
db_port = os.getenv("DB_PORT", "5432")
db_name = os.getenv("DB_NAME")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")

print("\n" + "="*60)
print("Database Configuration:")
print("="*60)
print(f"DB_HOST:     {db_host}")
print(f"DB_PORT:     {db_port}")
print(f"DB_NAME:     {db_name}")
print(f"DB_USER:     {db_user}")
if db_password:
    # Show first 3 and last 3 characters for security
    masked_password = f"{db_password[:3]}...{db_password[-3:]}" if len(db_password) > 6 else "***"
    print(f"DB_PASSWORD: {masked_password} (length: {len(db_password)})")
else:
    print(f"DB_PASSWORD: <NOT SET>")
print("="*60 + "\n")

# Check for missing variables
missing = []
if not db_name:
    missing.append("DB_NAME")
if not db_user:
    missing.append("DB_USER")
if not db_password:
    missing.append("DB_PASSWORD")

if missing:
    print(f"[ERROR] Missing required environment variables: {', '.join(missing)}")
    sys.exit(1)

# Build connection string (for display, mask password)
display_url = f"postgresql://{db_user}:***@{db_host}:{db_port}/{db_name}"
print(f"Attempting to connect to: {display_url}\n")

# Try to connect
try:
    print("Testing database connection...")
    conn = psycopg2.connect(
        host=db_host,
        port=db_port,
        database=db_name,
        user=db_user,
        password=db_password,
        connect_timeout=5
    )
    
    # Test query
    cursor = conn.cursor()
    cursor.execute("SELECT version();")
    version = cursor.fetchone()[0]
    
    cursor.execute("SELECT current_database(), current_user;")
    db_info = cursor.fetchone()
    
    print("[SUCCESS] Connection successful!\n")
    print("Database Information:")
    print(f"  PostgreSQL Version: {version[:50]}...")
    print(f"  Current Database:   {db_info[0]}")
    print(f"  Current User:       {db_info[1]}")
    
    cursor.close()
    conn.close()
    print("\n[SUCCESS] Connection test passed!")
    sys.exit(0)
    
except OperationalError as e:
    print(f"\n[ERROR] Connection failed!")
    print(f"Error: {e}")
    print("\nTroubleshooting tips:")
    print("1. Verify the password in .env matches the PostgreSQL user password")
    print("2. Check if PostgreSQL is running: pg_isready")
    print("3. Verify the user exists: psql -U postgres -c '\\du'")
    print("4. Check pg_hba.conf for authentication method")
    sys.exit(1)
except Exception as e:
    print(f"\n[ERROR] Unexpected error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

