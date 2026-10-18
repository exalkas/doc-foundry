# Backend for DocData SaaS

FastAPI backend application for document data extraction and management.

## Prerequisites

- Python 3.12+
- PostgreSQL database
- Virtual environment activated

## Setup

1. Install dependencies:

```powershell
pip install -r requirements.txt
```

2. Configure database credentials in `.env` file:

```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=docdata_saas
DB_USER=docdata_saas
DB_PASSWORD=your_password
```

3. Initialize database (creates tables and seeds initial data):

```powershell
python scripts/init_database.py
```

Or step by step:

- Create tables: `python scripts/create_tables.py`
- Seed data: `python scripts/seed_db.py`

## Running the Server

### Option 1: Using PowerShell script (Recommended)

```powershell
.\start_server.ps1
```

### Option 2: Using uvicorn directly

```powershell
# Activate virtual environment first
.\venv\Scripts\Activate.ps1

# Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Option 3: Using Python module

```powershell
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Server URLs

Once started, the server will be available at:

- **API Base**: http://localhost:8000
- **Interactive API Docs (Swagger)**: http://localhost:8000/api/docs
- **ReDoc Documentation**: http://localhost:8000/api/redoc
- **OpenAPI JSON**: http://localhost:8000/api/openapi.json
- **Health Check**: http://localhost:8000/health

## Development

- The `--reload` flag enables auto-reload on code changes
- Server runs on port 8000 by default
- Logs are output to console

## Testing

Run tests with:

```powershell
pytest
```

## Database Utilities

- **Test connection**: `python test_db_connection.py`
- **Update password**: `python update_db_password.py` (requires POSTGRES_PASSWORD env var)

  user credentials for app
  Email: admin@example.com
  Password: admin123

Run the worker: `python scripts/migrate.py migrate`
