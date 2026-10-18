# Doc Foundry

Doc Foundry is a document extraction application for people who need to turn documents into structured, usable data. It combines document uploads, Google Cloud Vision OCR, extraction templates, background processing, and exports, with workspaces, billing, and an administration interface.

The project is under development. It contains a Python FastAPI backend with PostgreSQL and SQLAlchemy, a Next.js/React application, a separate Next.js administration application, and an Astro marketing site. Optional integrations include Google OAuth, Stripe, Resend, and OpenAI for extraction features.

## Repository layout

| Folder | Purpose |
| --- | --- |
| `backend/` | API, database models and migrations, OCR, extraction, background worker, and tests |
| `frontend/` | Main Next.js application, normally on port 3000 |
| `admin_frontend/` | Next.js administration application, on port 3001 |
| `marketing_site/` | Astro website, normally on port 4321 |
| `docs/` | Architecture, API, and implementation documentation |
| `specs/` | Product and branding specifications |

## Local development

Install Python 3.12+, Node.js with npm, and PostgreSQL. Set up a local PostgreSQL database and user before initializing the application. OCR requires a Google Cloud project with the Vision API enabled and appropriate credentials. Other services require their own credentials only when you use those integrations.

From the repository root, in PowerShell:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env` locally: set `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD`, and replace the example `SECRET_KEY`. Generate a new signing secret locally with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Never reuse the example settings for a public deployment.

For Google Vision, keep the service-account JSON **outside this repository** and set `GOOGLE_APPLICATION_CREDENTIALS` to its absolute local path in the environment of both the API and worker. See [Google Vision setup](backend/GOOGLE_VISION_SETUP.md) for integration details. Credential filenames and paths in older documentation are illustrative; no credential file is distributed with this repository.

Initialize the database using the existing scripts, then start the API:

```powershell
python scripts/init_database.py
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The initialization script can create and seed a database; use a dedicated development database. Review [database setup](backend/README_DATABASE.md) for configuration details and the SQL migrations in `backend/migrations/` when updating an existing database.

In another terminal, activate the same backend environment and start the worker:

```powershell
cd backend
.\venv\Scripts\Activate.ps1
python -m app.workers.job_processor
```

In separate terminals, install and run each web application:

```powershell
cd frontend
npm ci
npm run dev
```

Repeat those npm commands from `admin_frontend/` and `marketing_site/` to run those applications. The main frontend reads `NEXT_PUBLIC_BACKEND_URL`; the admin frontend reads `NEXT_PUBLIC_API_URL`. Configure local `.env.local` files if needed. Never place private API keys in variables beginning with `NEXT_PUBLIC_`.

API documentation is available at `http://localhost:8000/api/docs`. Detailed component setup notes are in the component README files. The Docker Compose file is an example scaffold, not a complete deployment configuration.

## Validation

Backend tests run from `backend/` with `pytest`; install the backend dependencies and configure a separate test database first. The database creation helper reads its PostgreSQL administrator password from `POSTGRES_PASSWORD`. Frontend build commands are `npm run build` within each web application; admin unit tests use `npm test` within `admin_frontend/`.

## Secrets and data

Local environments, database settings, Google service-account JSON, uploaded documents, generated output, logs, virtual environments, and build artifacts are excluded from this repository. Setup examples use placeholders. Use synthetic documents and fictional identities for examples and tests; do not add customer documents or database exports.

Before pushing changes, scan both the working tree and Git history with a secret scanner such as Gitleaks. If a credential is ever committed or exposed publicly, rotate it and remove it from history; deleting the file in a later commit is insufficient.

## Development plans

See [ROADMAP.md](ROADMAP.md) for proposed follow-up work. These proposals need owner prioritization and are not a claim of completed work or a committed schedule.

## History and license

This standalone repository starts from the existing local project. No tracked commits for this project were found in its containing repository; earlier development is not represented as fabricated or backdated commits.

Released under the [MIT License](LICENSE). Third-party dependencies retain their own licenses.
