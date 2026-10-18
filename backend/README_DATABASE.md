# Database Setup and Management

This document describes the database setup and migration system for DocData SaaS.

## Overview

We use a simple, LLM-friendly approach to database management:

- **Table Creation**: Direct creation from SQLAlchemy models using `create_all()`
- **Seeding**: Python scripts for initial data
- **Migrations**: Simple SQL-based migration system

This approach is much simpler than Alembic and works better with LLMs.

## Quick Start

### Complete Setup (Recommended)

Run the all-in-one initialization script:

```powershell
python scripts/init_database.py
```

This will:

1. Create the database (if needed)
2. Create all tables from models
3. Seed initial data

### Step-by-Step Setup

If you prefer to run steps individually:

1. **Create database** (if needed):

   ```powershell
   python scripts/setup_db.py
   ```

2. **Create tables**:

   ```powershell
   python scripts/create_tables.py
   ```

3. **Seed initial data**:
   ```powershell
   python scripts/seed_db.py
   ```

## Database Scripts

### `scripts/create_tables.py`

Creates all database tables from SQLAlchemy models.

- Uses `Base.metadata.create_all()` to create tables directly
- Idempotent: skips existing tables
- Handles PostgreSQL enum types automatically

**Usage:**

```powershell
python scripts/create_tables.py
```

### `scripts/seed_db.py`

Seeds the database with initial reference data.

- Creates admin user (admin@example.com / admin123)
- Creates sample workspace
- Idempotent: checks if data exists before seeding

**Usage:**

```powershell
python scripts/seed_db.py
```

### `scripts/migrate.py`

Simple SQL-based migration system for schema changes.

**Commands:**

- `python scripts/migrate.py migrate` - Apply pending migrations
- `python scripts/migrate.py status` - Show migration status
- `python scripts/migrate.py create <name>` - Create new migration file

**Migration Files:**

- Stored in `migrations/` directory
- Named: `001_description.sql`, `002_description.sql`, etc.
- Plain SQL that LLMs can generate easily

**Example:**

```powershell
# Create a new migration
python scripts/migrate.py create add_user_index

# Edit migrations/001_add_user_index.sql with your SQL

# Apply migrations
python scripts/migrate.py migrate
```

### `scripts/init_database.py`

Complete database initialization script.

Runs all setup steps in sequence:

1. Database creation
2. Table creation
3. Data seeding

**Usage:**

```powershell
python scripts/init_database.py
```

## Migration System

### How It Works

1. **Migration Files**: Plain SQL files in `migrations/` directory
2. **Version Tracking**: `schema_migrations` table tracks applied migrations
3. **Simple Commands**: Easy-to-use CLI for applying migrations

### Creating Migrations

1. Create migration file:

   ```powershell
   python scripts/migrate.py create add_new_column
   ```

2. Edit the generated SQL file in `migrations/`:

   ```sql
   -- Migration: add_new_column
   -- Created: 2024-01-15T10:00:00

   ALTER TABLE users ADD COLUMN new_field VARCHAR(255);
   ```

3. Apply migration:
   ```powershell
   python scripts/migrate.py migrate
   ```

### Migration Best Practices

- Use numbered prefixes: `001_`, `002_`, etc.
- Write idempotent SQL when possible
- Test migrations on a copy of production data
- Keep migrations small and focused
- Document complex migrations with comments

## Default Credentials

After seeding, you can log in with:

- **Email**: admin@example.com
- **Password**: admin123

**⚠️ Important**: Change these credentials in production!

## Troubleshooting

### Tables Already Exist

If you see "tables already exist" warnings:

- This is normal - the scripts are idempotent
- Existing tables are skipped
- You can safely run the scripts multiple times

### Connection Errors

Check your `.env` file:

```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=docdata_saas
DB_USER=docdata_saas
DB_PASSWORD=your_password
```

### Migration Errors

If a migration fails:

1. Check the error message
2. Fix the SQL in the migration file
3. Manually update `schema_migrations` table if needed
4. Re-run the migration

## Differences from Alembic

| Feature          | Alembic       | Our System  |
| ---------------- | ------------- | ----------- |
| Migration Format | Python code   | Plain SQL   |
| LLM-Friendly     | ❌ Complex    | ✅ Simple   |
| Setup Complexity | High          | Low         |
| Auto-generation  | Yes (complex) | No (manual) |
| Version Tracking | Yes           | Yes         |
| Rollback Support | Yes           | Manual      |

Our system prioritizes simplicity and LLM-friendliness over advanced features.
