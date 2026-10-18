#!/usr/bin/env bash
#
# setup_db.sh - PostgreSQL database initialization script for docdata_saas
#
# This script:
#   - Creates the PostgreSQL user "docdata_saas" (if it does not exist)
#   - Creates the PostgreSQL database "docdata_saas" (if it does not exist)
#   - Grants all privileges on the database to that user
#   - Sets default privileges so the user owns future objects
#
# Idempotent:
#   - Safe to run multiple times; it only creates user/db if missing.
#
# Works in:
#   - Local Linux environments
#   - Docker containers (e.g. as an init script or entrypoint helper)
#
# Usage:
#   Environment variables (recommended):
#     PGHOST           - PostgreSQL host (default: localhost)
#     PGPORT           - PostgreSQL port (default: 5432)
#     PGSUPERUSER      - PostgreSQL superuser name (default: postgres)
#     PGSUPERPASS      - PostgreSQL superuser password (optional; if set, PGPASSWORD used)
#
#     APP_DB_NAME      - App database name (default: docdata_saas)
#     APP_DB_USER      - App database user (default: docdata_saas)
#     APP_DB_PASSWORD  - App database user password
#                        If NOT set, a random strong password will be generated and printed.
#
#   Or command-line arguments (override env vars where applicable):
#     ./setup_db.sh [--host HOST] [--port PORT] [--superuser USER] [--superpass PASS] \
#                   [--db-name NAME] [--db-user USER] [--db-pass PASS]
#
#   Examples:
#     # Using environment variables (recommended)
#     export PGHOST=localhost
#     export PGSUPERUSER=postgres
#     export PGSUPERPASS="my_postgres_root_pass"
#     export APP_DB_PASSWORD="someStrongPassword123!"
#     ./setup_db.sh
#
#     # Using command-line arguments
#     ./setup_db.sh --host localhost --superuser postgres --superpass mypass \
#                   --db-name docdata_saas --db-user docdata_saas --db-pass 'StrongPass!123'
#
# Exit codes:
#   0 - Success
#   1 - Usage or argument error
#   2 - psql not found
#   3 - Connection error
#   4 - SQL execution error

set -euo pipefail

###############################################################################
# Helper: print usage
###############################################################################
print_usage() {
  cat <<EOF
Usage: $0 [OPTIONS]

Options:
  --host HOST        PostgreSQL host (default: from PGHOST env or "localhost")
  --port PORT        PostgreSQL port (default: from PGPORT env or "5432")
  --superuser USER   PostgreSQL superuser (default: from PGSUPERUSER env or "postgres")
  --superpass PASS   PostgreSQL superuser password (default: from PGSUPERPASS env or empty)
  --db-name NAME     Application database name (default: from APP_DB_NAME env or "docdata_saas")
  --db-user USER     Application database user (default: from APP_DB_USER env or "docdata_saas")
  --db-pass PASS     Application database user password
                     (default: from APP_DB_PASSWORD env or auto-generated random strong password)

Examples:
  export PGHOST=localhost
  export PGSUPERUSER=postgres
  export PGSUPERPASS="my_postgres_root_pass"
  export APP_DB_PASSWORD="someStrongPassword123!"
  $0

  $0 --host localhost --superuser postgres --superpass mypass \\
     --db-name docdata_saas --db-user docdata_saas --db-pass 'StrongPass!123'

EOF
}

###############################################################################
# Parse command-line arguments
###############################################################################
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGSUPERUSER="${PGSUPERUSER:-postgres}"
PGSUPERPASS="${PGSUPERPASS:-}"

APP_DB_NAME="${APP_DB_NAME:-docdata_saas}"
APP_DB_USER="${APP_DB_USER:-docdata_saas}"
APP_DB_PASSWORD="${APP_DB_PASSWORD:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      shift
      PGHOST="${1:-}"
      ;;
    --port)
      shift
      PGPORT="${1:-}"
      ;;
    --superuser)
      shift
      PGSUPERUSER="${1:-}"
      ;;
    --superpass)
      shift
      PGSUPERPASS="${1:-}"
      ;;
    --db-name)
      shift
      APP_DB_NAME="${1:-}"
      ;;
    --db-user)
      shift
      APP_DB_USER="${1:-}"
      ;;
    --db-pass)
      shift
      APP_DB_PASSWORD="${1:-}"
      ;;
    -h|--help)
      print_usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      print_usage
      exit 1
      ;;
  esac
  shift
done

###############################################################################
# Validate required parameters and generate password if missing
###############################################################################
if [[ -z "$APP_DB_NAME" || -z "$APP_DB_USER" ]]; then
  echo "Error: Database name and user must not be empty." >&2
  exit 1
fi

# Generate a strong random password if none was provided.
if [[ -z "$APP_DB_PASSWORD" ]]; then
  if command -v openssl >/dev/null 2>&1; then
    APP_DB_PASSWORD="$(openssl rand -base64 32 | tr -d '\n' | head -c 48)"
  elif command -v pwgen >/dev/null 2>&1; then
    APP_DB_PASSWORD="$(pwgen -s 32 1)"
  else
    # Fallback to /dev/urandom; still strong enough for most cases
    APP_DB_PASSWORD="$(head -c 48 /dev/urandom | base64 | tr -d '\n' | head -c 48)"
  fi
  GENERATED_PASSWORD=1
else
  GENERATED_PASSWORD=0
fi

###############################################################################
# Check for psql availability
###############################################################################
if ! command -v psql >/dev/null 2>&1; then
  echo "Error: psql command not found. Please ensure PostgreSQL client tools are installed and in PATH." >&2
  exit 2
fi

###############################################################################
# Prepare psql connection options
###############################################################################
PSQL_OPTS=(
  "-h" "$PGHOST"
  "-p" "$PGPORT"
  "-U" "$PGSUPERUSER"
  "-v" "ON_ERROR_STOP=1"
)

# Export superuser password for psql if provided
if [[ -n "$PGSUPERPASS" ]]; then
  export PGPASSWORD="$PGSUPERPASS"
else
  # Unset to avoid using some unexpected value
  unset PGPASSWORD || true
fi

###############################################################################
# Function to run SQL against the "postgres" database as superuser
###############################################################################
run_psql_postgres() {
  local sql="$1"
  psql "${PSQL_OPTS[@]}" -d postgres -Atqc "$sql"
}

###############################################################################
# Connection test
###############################################################################
echo "Testing connection to PostgreSQL as superuser '$PGSUPERUSER' on $PGHOST:$PGPORT ..."
if ! run_psql_postgres "SELECT 1;" >/dev/null 2>&1; then
  echo "Error: Unable to connect to PostgreSQL with provided superuser credentials." >&2
  exit 3
fi
echo "Connection successful."

###############################################################################
# Create user and database if they do not exist (idempotent)
###############################################################################
echo "Ensuring database user '$APP_DB_USER' exists ..."
CREATE_USER_SQL="
DO \$\$
BEGIN
   IF NOT EXISTS (
       SELECT FROM pg_catalog.pg_roles WHERE rolname = '${APP_DB_USER}'
   ) THEN
       CREATE ROLE ${APP_DB_USER} LOGIN PASSWORD '${APP_DB_PASSWORD}';
   ELSE
       ALTER ROLE ${APP_DB_USER} LOGIN PASSWORD '${APP_DB_PASSWORD}';
   END IF;
END
\$\$;
"
if ! run_psql_postgres "$CREATE_USER_SQL" >/dev/null 2>&1; then
  echo "Error: Failed to create or alter role '$APP_DB_USER'." >&2
  exit 4
fi
echo "User '$APP_DB_USER' ensured."

echo "Ensuring database '$APP_DB_NAME' exists ..."
CREATE_DB_SQL="
DO \$\$
BEGIN
   IF NOT EXISTS (
       SELECT FROM pg_database WHERE datname = '${APP_DB_NAME}'
   ) THEN
       CREATE DATABASE ${APP_DB_NAME}
       WITH OWNER = ${APP_DB_USER}
            ENCODING = 'UTF8'
            LC_COLLATE = 'C'
            LC_CTYPE = 'C'
            TEMPLATE = template0;
   END IF;
END
\$\$;
"
if ! run_psql_postgres "$CREATE_DB_SQL" >/dev/null 2>&1; then
  echo "Error: Failed to create database '$APP_DB_NAME'." >&2
  exit 4
fi
echo "Database '$APP_DB_NAME' ensured."

###############################################################################
# Grant privileges and set default privileges
###############################################################################
echo "Granting privileges on database '$APP_DB_NAME' to user '$APP_DB_USER' ..."

GRANT_DB_SQL="
GRANT ALL PRIVILEGES ON DATABASE ${APP_DB_NAME} TO ${APP_DB_USER};
"
if ! run_psql_postgres "$GRANT_DB_SQL" >/dev/null 2>&1; then
  echo "Error: Failed to grant privileges on database '$APP_DB_NAME'." >&2
  exit 4
fi

# Now run privilege statements inside the target database
grant_schema_and_defaults() {
  local sql="$1"
  psql "${PSQL_OPTS[@]}" -d "$APP_DB_NAME" -Atqc "$sql"
}

SCHEMA_AND_DEFAULTS_SQL="
-- Ensure public schema exists and is owned by app user
CREATE SCHEMA IF NOT EXISTS public AUTHORIZATION ${APP_DB_USER};

ALTER SCHEMA public OWNER TO ${APP_DB_USER};

-- Grant usage on public schema
GRANT ALL ON SCHEMA public TO ${APP_DB_USER};

-- Set default privileges so that future tables, sequences, functions, etc.
-- created by the superuser are accessible to the app user.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE, REFERENCES, TRIGGER ON TABLES TO ${APP_DB_USER};

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO ${APP_DB_USER};

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO ${APP_DB_USER};

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE ON TYPES TO ${APP_DB_USER};

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE ON SCHEMAS TO ${APP_DB_USER};
"

if ! grant_schema_and_defaults "$SCHEMA_AND_DEFAULTS_SQL" >/dev/null 2>&1; then
  echo "Error: Failed to configure schema and default privileges in '$APP_DB_NAME'." >&2
  exit 4
fi

echo "Privileges configured successfully."

###############################################################################
# Final output (including password if generated)
###############################################################################
echo
echo "PostgreSQL setup completed successfully."
echo "----------------------------------------"
echo "Host:           $PGHOST"
echo "Port:           $PGPORT"
echo "Superuser:      $PGSUPERUSER"
echo "Database:       $APP_DB_NAME"
echo "User:           $APP_DB_USER"

if [[ "$GENERATED_PASSWORD" -eq 1 ]]; then
  echo
  echo "A strong random password was generated for the database user."
  echo "Store this credential securely:"
  echo "  APP_DB_USER:     $APP_DB_USER"
  echo "  APP_DB_PASSWORD: $APP_DB_PASSWORD"
fi

exit 0