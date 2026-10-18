-- init_db.sql
-- PostgreSQL initialization script for application: docdata_saas
-- This script is idempotent and safe to run multiple times.
--
-- It will:
--  1. Create the role/user "docdata_saas" if it does not exist
--  2. Set a secure password for the user (overridable via environment when used in Docker)
--  3. Create the database "docdata_saas" if it does not exist
--  4. Grant all privileges on the database to the user
--  5. Configure default privileges so new objects are accessible to the user
--
-- NOTE ABOUT PASSWORD:
--  - PostgreSQL plain SQL cannot generate a truly random password by itself.
--  - By default, this script uses a placeholder password:
--        DEFAULT PASSWORD: ChangeMe_DocdataSaas_ReplaceThis!
--  - In production, you should:
--      * Replace this password before first use, OR
--      * Use a Docker/post-deploy mechanism to pass in a secure password
--        (e.g., by running: ALTER ROLE docdata_saas WITH PASSWORD 'your_secure_password';
--         after container start or via a separate initialization step).


-----------------------------------------------------------------------
-- 1. Ensure role/user "docdata_saas" exists
-----------------------------------------------------------------------

DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'docdata_saas'
    ) THEN
        -- Create a login role/user for the application.
        -- Adjust CREATEDB / CREATEROLE as needed; here we give only LOGIN.
        CREATE ROLE docdata_saas
            LOGIN
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOINHERIT
            NOREPLICATION
            CONNECTION LIMIT -1
            PASSWORD 'ChangeMe_DocdataSaas_ReplaceThis!';  -- Replace with a secure password
    ELSE
        -- Optionally, ensure properties on an existing role.
        -- We DO NOT overwrite the existing password automatically to avoid
        -- inadvertently breaking existing deployments.
        ALTER ROLE docdata_saas
            LOGIN
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOINHERIT
            NOREPLICATION
            CONNECTION LIMIT -1;
    END IF;
END
$$;


-----------------------------------------------------------------------
-- 2. Ensure database "docdata_saas" exists
-----------------------------------------------------------------------

DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_database
        WHERE datname = 'docdata_saas'
    ) THEN
        -- Create the application database owned by the app user.
        CREATE DATABASE docdata_saas
            WITH
                OWNER = docdata_saas
                ENCODING = 'UTF8'
                LC_COLLATE = 'en_US.utf8'
                LC_CTYPE = 'en_US.utf8'
                TEMPLATE = template0
                CONNECTION LIMIT = -1;
    ELSE
        -- Optionally, ensure ownership is correct if database already exists.
        -- This is safe to run repeatedly.
        ALTER DATABASE docdata_saas OWNER TO docdata_saas;
    END IF;
END
$$;


-----------------------------------------------------------------------
-- 3. Grant privileges on the database to the user
-----------------------------------------------------------------------
-- These commands should be run in the context of the "postgres" database
-- or any database where you have the necessary privileges.
-----------------------------------------------------------------------

-- Grant all database-level privileges.
GRANT ALL PRIVILEGES ON DATABASE docdata_saas TO docdata_saas;

-- Ensure the user can connect to the database.
REVOKE CONNECT ON DATABASE docdata_saas FROM PUBLIC;
GRANT CONNECT ON DATABASE docdata_saas TO docdata_saas;


-----------------------------------------------------------------------
-- 4. Set default privileges for future objects in the database
-----------------------------------------------------------------------
-- Default privileges are per-(role, database, schema). To make these
-- apply consistently, we:
--   * Connect as the owner (docdata_saas) when modifying defaults, OR
--   * Use ALTER DEFAULT PRIVILEGES FOR ROLE owner IN SCHEMA ...
--
-- IMPORTANT:
--   - The following statements adjust default privileges for objects
--     created by the role "docdata_saas" in all its schemas.
--   - These must be run *inside* the target database, so we use
--     a DO block with SET LOCAL search_path if needed.
-----------------------------------------------------------------------

-- Switch to the target database for the following operations.
-- NOTE: Many migration/deployment tools execute this script after
-- selecting the appropriate database. If using psql, invoke with:
--   psql -d postgres -f init_db.sql
-- followed by:
--   psql -d docdata_saas -f init_db.sql
-- Or adapt this section to your deployment tooling.

-- The following block is meant to be executed within docdata_saas.
-- If your tooling does not re-connect automatically, you can split
-- this script into two files (cluster-level and db-level).
--
-- For environments that do support running this in the target DB
-- context, the commands are fully idempotent:

-- Ensure the role is owner of default public schema (common pattern).
ALTER DATABASE docdata_saas SET search_path = public, pg_catalog;

-- The following statements must be executed in the context of the
-- "docdata_saas" database. If you are currently connected to another
-- database, reconnect as:
--   \c docdata_saas
-- before running them.

-- For documentation purposes; safe to re-run.
COMMENT ON DATABASE docdata_saas IS 'Primary application database for docdata_saas';

-----------------------------------------------------------------------
-- 4a. Default privileges for objects created by owner in public schema
-----------------------------------------------------------------------

-- NOTE: These ALTER DEFAULT PRIVILEGES statements are intended to be
-- run while connected to docdata_saas. They are idempotent and can be
-- run multiple times without issue.

ALTER DEFAULT PRIVILEGES FOR ROLE docdata_saas IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE, REFERENCES, TRIGGER
    ON TABLES
    TO docdata_saas;

ALTER DEFAULT PRIVILEGES FOR ROLE docdata_saas IN SCHEMA public
    GRANT USAGE, SELECT, UPDATE
    ON SEQUENCES
    TO docdata_saas;

ALTER DEFAULT PRIVILEGES FOR ROLE docdata_saas IN SCHEMA public
    GRANT EXECUTE
    ON FUNCTIONS
    TO docdata_saas;

ALTER DEFAULT PRIVILEGES FOR ROLE docdata_saas IN SCHEMA public
    GRANT USAGE
    ON TYPES
    TO docdata_saas;

ALTER DEFAULT PRIVILEGES FOR ROLE docdata_saas IN SCHEMA public
    GRANT USAGE
    ON SCHEMAS
    TO docdata_saas;


-----------------------------------------------------------------------
-- 5. Optional: Explicit grants on existing objects (if any)
-----------------------------------------------------------------------
-- These commands ensure that if schema/objects already exist in the
-- public schema, the application user still has the needed privileges.
-- They are safe to run even if objects are not yet created.
-----------------------------------------------------------------------

-- Grant on existing schemas.
GRANT USAGE, CREATE ON SCHEMA public TO docdata_saas;

-- Grant on all existing tables.
GRANT SELECT, INSERT, UPDATE, DELETE, REFERENCES, TRIGGER
    ON ALL TABLES IN SCHEMA public
    TO docdata_saas;

-- Grant on all existing sequences.
GRANT USAGE, SELECT, UPDATE
    ON ALL SEQUENCES IN SCHEMA public
    TO docdata_saas;

-- Grant on all existing functions.
GRANT EXECUTE
    ON ALL FUNCTIONS IN SCHEMA public
    TO docdata_saas;


-----------------------------------------------------------------------
-- END OF SCRIPT
-----------------------------------------------------------------------