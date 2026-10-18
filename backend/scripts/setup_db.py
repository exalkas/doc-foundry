#!/usr/bin/env python3
"""
Programmatic PostgreSQL database setup for the docdata_saas application.

This script:
- Connects using a PostgreSQL superuser (for local dev or admin usage)
- Creates the application database and user if they do not exist
- Grants appropriate privileges
- Is idempotent: safe to run multiple times

Environment variables:
  DB_SUPERUSER           (default: postgres)
  DB_SUPERUSER_PASSWORD  (optional; required if superuser requires a password)
  DB_HOST                (default: localhost)
  DB_PORT                (default: 5432)
  DB_NAME                (default: docdata_saas)
  DB_USER                (default: docdata_saas)
  DB_PASSWORD            (required to create user if it does not exist)

Usage:
  python setup_db.py
"""

import os
import sys
import traceback
from typing import Optional, Tuple

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


def get_env(var_name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(var_name)
    if value is None or value == "":
        return default
    return value


def print_header():
    print("=== PostgreSQL Database Setup: docdata_saas ===")


def print_config(
    superuser: str,
    host: str,
    port: int,
    db_name: str,
    db_user: str,
    has_superuser_password: bool,
    has_db_password: bool,
):
    print("Configuration:")
    print(f"  Superuser:       {superuser}")
    print(f"  Superuser pass:  {'<set>' if has_superuser_password else '<not set>'}")
    print(f"  Host:            {host}")
    print(f"  Port:            {port}")
    print(f"  Target DB name:  {db_name}")
    print(f"  Target DB user:  {db_user}")
    print(f"  Target DB pass:  {'<set>' if has_db_password else '<not set>'}")
    print("")


def connect_as_superuser(
    superuser: str,
    password: Optional[str],
    host: str,
    port: int,
) -> psycopg2.extensions.connection:
    """Connect to the default 'postgres' database as superuser."""
    conn_params = {
        "dbname": "postgres",
        "user": superuser,
        "password": password,
        "host": host,
        "port": port,
    }

    # Remove None values so psycopg2 can fall back correctly
    conn_params_clean = {k: v for k, v in conn_params.items() if v is not None}

    print("Connecting as superuser to manage databases and roles...")
    conn = psycopg2.connect(**conn_params_clean)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    print("Superuser connection established.")
    return conn


def database_exists(conn, db_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM pg_database
            WHERE datname = %s
            """,
            (db_name,),
        )
        return cur.fetchone() is not None


def user_exists(conn, username: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM pg_roles
            WHERE rolname = %s
            """,
            (username,),
        )
        return cur.fetchone() is not None


def create_user_if_not_exists(
    conn,
    username: str,
    password: str,
) -> None:
    if user_exists(conn, username):
        print(f"User '{username}' already exists. Skipping creation.")
        return

    print(f"Creating user '{username}'...")
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL(
                "CREATE ROLE {user} LOGIN PASSWORD %s"
            ).format(
                user=sql.Identifier(username),
            ),
            (password,),
        )
    print(f"User '{username}' created.")


def create_database_if_not_exists(
    conn,
    db_name: str,
    owner: str,
) -> None:
    if database_exists(conn, db_name):
        print(f"Database '{db_name}' already exists. Skipping creation.")
        return

    print(f"Creating database '{db_name}' owned by '{owner}'...")
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL(
                "CREATE DATABASE {dbname} OWNER {owner}"
            ).format(
                dbname=sql.Identifier(db_name),
                owner=sql.Identifier(owner),
            )
        )
    print(f"Database '{db_name}' created.")


def grant_privileges_on_database(
    conn,
    db_name: str,
    username: str,
) -> None:
    print(f"Granting privileges on database '{db_name}' to '{username}'...")
    with conn.cursor() as cur:
        # Grant basic privileges on database
        cur.execute(
            sql.SQL(
                "GRANT ALL PRIVILEGES ON DATABASE {dbname} TO {user}"
            ).format(
                dbname=sql.Identifier(db_name),
                user=sql.Identifier(username),
            )
        )
    print(f"Privileges granted on database '{db_name}' to '{username}'.")


def configure_default_privileges(
    host: str,
    port: int,
    superuser: str,
    superuser_password: Optional[str],
    db_name: str,
    db_user: str,
) -> None:
    """
    Configure default privileges for future objects in the target database.

    This connects specifically to the target database and sets default privileges
    for the db_user so that future tables/sequences/functions, created by the
    database owner (typically db_user), are accessible.
    """
    print(f"Configuring default privileges in database '{db_name}'...")

    conn_params = {
        "dbname": db_name,
        "user": superuser,
        "password": superuser_password,
        "host": host,
        "port": port,
    }
    conn_params_clean = {k: v for k, v in conn_params.items() if v is not None}

    conn = None
    try:
        conn = psycopg2.connect(**conn_params_clean)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

        with conn.cursor() as cur:
            # Ensure db_user is the owner that will set default privileges,
            # or adjust as needed for your project. Here we set defaults for
            # the owner (db_user) and grant to itself (idempotent).
            cur.execute(
                sql.SQL("ALTER DEFAULT PRIVILEGES FOR USER {owner} IN SCHEMA public "
                        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {grantee}")
                .format(
                    owner=sql.Identifier(db_user),
                    grantee=sql.Identifier(db_user),
                )
            )
            cur.execute(
                sql.SQL("ALTER DEFAULT PRIVILEGES FOR USER {owner} IN SCHEMA public "
                        "GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO {grantee}")
                .format(
                    owner=sql.Identifier(db_user),
                    grantee=sql.Identifier(db_user),
                )
            )
            cur.execute(
                sql.SQL("ALTER DEFAULT PRIVILEGES FOR USER {owner} IN SCHEMA public "
                        "GRANT EXECUTE ON FUNCTIONS TO {grantee}")
                .format(
                    owner=sql.Identifier(db_user),
                    grantee=sql.Identifier(db_user),
                )
            )
            cur.execute(
                sql.SQL("ALTER DEFAULT PRIVILEGES FOR USER {owner} IN SCHEMA public "
                        "GRANT USAGE ON TYPES TO {grantee}")
                .format(
                    owner=sql.Identifier(db_user),
                    grantee=sql.Identifier(db_user),
                )
            )

        print(f"Default privileges configured in database '{db_name}'.")
    except Exception as e:
        print(f"Warning: Failed to configure default privileges on '{db_name}': {e}")
        traceback.print_exc()
    finally:
        if conn is not None:
            conn.close()


def validate_config(
    db_name: str,
    db_user: str,
    db_password: Optional[str],
) -> Tuple[bool, Optional[str]]:
    if not db_name:
        return False, "DB_NAME must be provided (environment variable DB_NAME)."
    if not db_user:
        return False, "DB_USER must be provided (environment variable DB_USER)."
    if not db_password:
        # Avoid leaking passwords in logs; just state it's missing
        return (
            False,
            "DB_PASSWORD must be provided (environment variable DB_PASSWORD) "
            "to create or manage the application user.",
        )
    return True, None


def main() -> int:
    print_header()

    superuser = get_env("DB_SUPERUSER", "postgres")
    superuser_password = get_env("DB_SUPERUSER_PASSWORD", None)
    host = get_env("DB_HOST", "localhost")
    port_str = get_env("DB_PORT", "5432")
    db_name = get_env("DB_NAME", "docdata_saas")
    db_user = get_env("DB_USER", "docdata_saas")
    db_password = get_env("DB_PASSWORD", None)

    try:
        port = int(port_str)
    except ValueError:
        print(f"Error: Invalid DB_PORT '{port_str}'. Must be an integer.")
        return 1

    is_valid, error_msg = validate_config(db_name, db_user, db_password)
    if not is_valid:
        print(f"Configuration error: {error_msg}")
        return 1

    print_config(
        superuser=superuser,
        host=host,
        port=port,
        db_name=db_name,
        db_user=db_user,
        has_superuser_password=superuser_password is not None,
        has_db_password=db_password is not None,
    )

    conn = None
    try:
        conn = connect_as_superuser(superuser, superuser_password, host, port)

        # 1. Create user if needed
        create_user_if_not_exists(conn, db_user, db_password)

        # 2. Create database if needed (owned by the app user)
        create_database_if_not_exists(conn, db_name, db_user)

        # 3. Grant privileges on the database (idempotent)
        grant_privileges_on_database(conn, db_name, db_user)

        # 4. Configure default privileges for future objects
        configure_default_privileges(host, port, superuser, superuser_password, db_name, db_user)

        print("")
        print("=== Database setup completed successfully. ===")
        return 0

    except psycopg2.OperationalError as e:
        print("OperationalError: Could not connect or execute commands against PostgreSQL.")
        print(str(e))
        traceback.print_exc()
        return 2
    except Exception as e:
        print("Unexpected error during database setup:")
        print(str(e))
        traceback.print_exc()
        return 3
    finally:
        if conn is not None:
            conn.close()
            print("Superuser connection closed.")


if __name__ == "__main__":
    sys.exit(main())