## 1. High-Level Architecture

**Overall style:** API-first multi-tenant SaaS, single Postgres database with row-level tenant scoping via `workspace_id`.  
**Runtime:** Containerized FastAPI backend + Next.js frontend, fronted by Nginx; “serverless-like” scaling achieved via stateless backend and async/background workers (still under Docker Compose in this initial setup).  
**Document processing:** Local filesystem storage plus job queue (DB-backed) for extractions and webhook delivery.

### Components

1. **Frontend (Next.js 14+ App Router, TS)**

   - UI: Tailwind + shadcn + Lucide.
   - SSR/ISR for marketing pages, mostly client-side + SSR for dashboard.
   - Auth via JWT cookies (HTTPOnly) with CSRF protection.
   - Multi-workspace support (workspace switcher, brand overrides).

2. **Backend API (FastAPI + SQLAlchemy, Postgres)**

   - Modules: `auth`, `workspaces`, `projects`, `templates`, `documents`, `extractions`, `apikeys`, `webhooks`, `usage_billing`, `admin`, `notifications`, `audit`.
   - REST API under `/api`.
   - JWT-based auth for user sessions; HMAC-style API key auth for `/api/v1` programmatic endpoints.
   - Document processing service orchestrating OCR/extraction (implementation of actual ML/AI engine can be pluggable/injected).

3. **Job/Worker System**

   - DB-backed `jobs` table as simple queue.
   - Separate FastAPI/async worker process (same codebase, different entrypoint) for:
     - `document_extraction` jobs.
     - `webhook_delivery` jobs (with retry policies).
   - Scheduled polling loop (e.g., `asyncio` or simple cron-like process) to fetch queued jobs.

4. **Storage**

   - **Local file storage** for uploaded documents & generated exports:
     - e.g. `/data/storage/{workspace_id}/{project_id}/{document_id}/{original|exports/...}`
   - Local ephemeral paths assumed backed by persistent volumes in Docker Compose.

5. **Reverse Proxy / Web Server**

   - Nginx:
     - Routes `/` and `/app/*` to Next.js container.
     - Routes `/api/*` and `/admin/*` to FastAPI container.
     - Serves static assets from Next.js build.
     - TLS termination (in prod, via Let’s Encrypt / external load balancer).

6. **Integrations**
   - Resend for email (transactional notifications, verification, password reset).
   - Stripe for subscriptions and billing portal.
   - Webhooks for outbound integrations (Zapier/Make/n8n).
   - No custom Zapier/Make/n8n apps initially—guides only.

---

## 2. Frontend Architecture

### Structure

- Monorepo single Next.js app with:
  - `app/(marketing)` – marketing site, signup, pricing.
  - `app/(auth)` – login, register, password reset flows.
  - `app/app/*` – authenticated dashboard (S_dashboard_main, projects, templates, documents, settings).
  - `app/admin` – admin panel (gated by `admin` role).
- Global layout includes:
  - Workspace switcher and branding (logo, primary color) from `/api/workspaces/current`.
  - Top nav with usage summary in some pages.

### Key UI Modules

- **Auth pages:** `/login`, `/register`, `/verify-email`, `/reset-password`.
- **Dashboard main:** `/app` – usage summary, recent projects, latest extractions.
- **Projects:** `/app/projects`, `/app/projects/[projectId]`.
- **Document upload:** `/app/upload`.
- **Template editor:** `/app/templates/[templateId]/edit` with JSON preview.
- **Extraction preview:** `/app/documents/[documentId]`.
- **Settings:**
  - API keys: `/app/settings/api-keys`.
  - Webhooks: `/app/settings/webhooks`.
  - Usage & Billing: `/app/settings/usage-billing`.
  - Branding: `/app/settings/branding` (from workspace fields).
- **Integrations docs:** `/app/integrations`.

**Data fetching:**

- Use Next.js Route Handlers for SSR where appropriate (e.g., usage, project lists) but primarily call FastAPI with cookies.
- React Query (or similar) on client for interactive screens (upload, editor, previews).

---

## 3. Backend Service / Module Decomposition

Single FastAPI app, logically decomposed:

1. **Auth & Identity Module**

   - Email/password, Google OAuth.
   - JWT cookie issuance & validation.
   - Email verification tokens, password reset tokens.
   - 2FA optional (can be TOTP-based; add `user_2fa_secret` later).
   - Endpoints: `E_auth_login`, `E_auth_register`, `E_me`, plus verification/password reset.

2. **Workspace & Membership Module**

   - Workspaces CRUD (mostly owner/admin).
   - Workspace branding (logo, primary_color, custom_domain).
   - Workspace members (invite via email, role assignment).
   - Enforce multi-tenancy: every resource tied to `workspace_id` and filtered by current workspace context.

3. **Projects Module**

   - CRUD within workspace.
   - Aggregations: document count, template count.

4. **Templates Module**

   - CRUD and versioning fields (success/fail metrics, last_run_at).
   - Field schema (`json` with validation rules, data types).
   - Ability to run “test extraction” on a test document (synchronous or queued but awaited).

5. **Documents & Extractions Module**

   - Document upload (multipart), local storage.
   - Creation of `Document` row + enqueue `document_extraction` job.
   - Extraction results and logs (one-to-many).
   - Retry logic: create new job + new `ExtractionResult` version.
   - Export handling: JSON/CSV/Excel generation (locally), returning signed/opaque URL.

6. **Job Queue Module**

   - Job creation, picking, locking, retries.
   - Types:
     - `document_extraction`: orchestrates OCR, runs template over text, writes `ExtractionResult`, `ExtractionLog`, updates `Document.status`, updates usage counters.
     - `webhook_delivery`: sends HTTP requests with retry policies (backoff), records `WebhookDelivery`.
   - Schedules follow-up jobs when needed (webhook on extraction completed).

7. **API Keys & Public API Module**

   - Manage `ApiKey` records.
   - HMAC or opaque token pattern: API key = `prefix_random`, only hash stored.
   - API key scopes (e.g. `documents:write`, `templates:read`).
   - Public endpoint `/api/v1/documents:extract` using only API key header (no cookies).
   - Tracks `last_used_at`, logs audit events.

8. **Webhooks Module**

   - `WebhookConfig` CRUD, per-workspace.
   - Events: `template_run`, `document_completed`, `webhook_failures_exceeded`, etc.
   - Webhook signing using secret (e.g., `X-DocFoundry-Signature` HMAC of payload).
   - Webhook logs (`WebhookDelivery`), and manual retry endpoint -> enqueues `webhook_delivery` job.

9. **Usage & Billing Module**

   - `UsageRecord` daily aggregates; incremented by workers.
   - Stripe webhook handler (subscription_created, updated, canceled).
   - Control plan limits (pages/documents/month, team size, templates).
   - Triggers notifications for 80% and 100% usage.
   - **Billing Model**: Subscriptions are per-user, not per-workspace. A user has one subscription that covers usage across all their workspaces. Usage is aggregated across all workspaces when checking limits and calculating billing.

10. **Notifications Module**

    - Abstraction for sending emails (Resend) + in-app notifications table (not yet specified, can extend).
    - Sends:
      - welcome, email verification, password reset.
      - billing and usage alerts.
      - API key/webhook-related notifications.

11. **Audit Logging Module**

    - Writes `AuditLog` for key events (login/logout/create/update/delete/template_run/api_key_used/webhook_sent).
    - Admin panel queries with filtering.

12. **Admin Module**
    - Workspaces overview, impersonation (optional via special admin JWT).
    - System metrics from DB (queue depth, jobs per day, error counts).

---

## 4. Database Schema Mapping

Each YAML entity → Postgres table (SQLAlchemy models). Key points:

### Multi-tenancy Pattern

- All tenant-owned entities include `workspace_id`:
  - `projects`, `templates`, `documents`, `extraction_results`, `extraction_logs`,
    `api_keys`, `webhook_configs`, `webhook_deliveries`, `usage_records`, `audit_logs` (optional for system events).
- Use composite (workspace_id, id) indexes for most tables.
- Optional Postgres Row-Level Security (RLS) if you later expose via other tools; initially controlled in app layer.

### Tables (overview)

I’ll stay concise; each field from your YAML maps directly:

- `users`
- `workspaces`
- `workspace_members`
- `subscriptions`
- `usage_records`
- `projects`
- `templates`
- `documents`
- `extraction_results`
- `extraction_logs`
- `jobs`
- `api_keys`
- `webhook_configs`
- `webhook_deliveries`
- `audit_logs`

Additional helpful columns (implementation detail, not changing conceptual model):

- `deleted_at` (soft-delete) on multi-tenant resources.
- `version` or `revision` on templates (if you want explicit versioning later).

---

## 5. API Surface Summary

From your spec plus a few necessary additions, grouped by domain:

### Auth

- `POST /api/auth/login` – email/password login, sets JWT cookie.
- `POST /api/auth/register` – create user + initial workspace.
- `GET /api/auth/me` – current user, workspaces, active workspace.
- Additional (not in YAML but recommended):
  - `POST /api/auth/logout`
  - `POST /api/auth/verify-email`
  - `POST /api/auth/request-password-reset`
  - `POST /api/auth/reset-password`
  - `POST /api/auth/google` (OAuth callback/one-tap).

### Workspaces & Members

- `GET /api/workspaces` – list user’s workspaces.
- `POST /api/workspaces` – create workspace (admin/owner).
- `GET /api/workspaces/current` – current workspace detail (branding, plan).
- `PATCH /api/workspaces/current` – update branding (owner).
- `GET /api/workspaces/current/members`
- `POST /api/workspaces/current/invite` – invite via email.
- `PATCH /api/workspaces/current/members/:memberId` – role changes.
- `DELETE /api/workspaces/current/members/:memberId`

### Projects

- `GET /api/projects` – `E_projects_list`.
- `POST /api/projects` – `E_projects_create`.
- `GET /api/projects/:projectId`
- `PATCH /api/projects/:projectId`
- `DELETE /api/projects/:projectId`

### Templates

- `GET /api/templates` – `E_templates_list`.
- `POST /api/templates` – `E_templates_create`.
- `GET /api/templates/:templateId`
- `PUT /api/templates/:templateId` – `E_templates_update`.
- `DELETE /api/templates/:templateId`.
- `POST /api/templates/:templateId/test` – run test extraction on `test_document_id`.

### Documents & Extractions

- `POST /api/documents` – `E_documents_upload` (multipart).
- `GET /api/documents/:documentId` – `E_documents_get`.
- `POST /api/documents/:documentId/retry` – `E_documents_retry`.
- `GET /api/documents/:documentId/export` – `E_extractions_export` (returns `download_url`).
- `GET /api/documents` – list/filter by project, status.

### API Keys

- `GET /api/api-keys` – `E_api_keys_list`.
- `POST /api/api-keys` – `E_api_keys_create`.
- `POST /api/api-keys/:apiKeyId/revoke` – `E_api_keys_revoke`.

### Webhooks

- `GET /api/webhooks` – `E_webhooks_get`.
- `POST /api/webhooks` – `E_webhooks_upsert` (create or update by ID in body).
- `POST /api/webhooks/test` – `E_webhooks_test`.
- `GET /api/webhooks/:webhookId/deliveries` – list deliveries with status.
- `POST /api/webhook-deliveries/:deliveryId/retry` – enqueue retry.

### Usage & Billing

- `GET /api/usage/summary` – `E_usage_summary`.
- `GET /api/usage/daily` – returns timeseries for charts.
- `POST /api/billing/checkout-session` – new subscription/upgrade.
- `POST /api/billing/portal-session` – Stripe billing portal.
- `POST /api/billing/stripe-webhook` – Stripe events (no auth, secret-based).

### Public Programmatic API (API key auth)

- Base path: `/api/v1`
- `POST /api/v1/documents:extract` – `E_public_extract_via_api_key`.
  - Headers: `Authorization: Bearer <api_key>`
  - Body: `template_id`, `file` (multipart), optional `callback_url`.
  - Response: `document_id`, `status` (e.g. `queued`).
- Potential future:
  - `GET /api/v1/documents/:id` – for polling-based integrations.
  - `GET /api/v1/templates` – read-only template list for integration tooling.

### Admin

- `GET /api/admin/workspaces` – paginated overview.
- `POST /api/admin/workspaces/:id/suspend`
- `POST /api/admin/workspaces/:id/unsuspend`
- `POST /api/admin/workspaces/:id/impersonate`
- `GET /api/admin/metrics` – queue depth, processing time stats.
- `GET /api/admin/audit-logs`

---

## 6. Security & Auth Model

- **Users:**
  - `users.role` has platform-level roles (`admin` vs normal).
  - Workspace-level roles via `workspace_members.role` (owner/member/readonly).
- **Session auth:**
  - HTTPOnly secure JWT cookie, short-lived access token + refresh token (or long-lived single token with rotation).
  - CSRF protection for browser calls (CSRF token in header or double-submit cookie).
- **API key auth:**
  - Only for `/api/v1/*`.
  - Store `key_hash` using strong hash (e.g., Argon2/bcrypt).
  - Prefix used for quick lookup.
  - Check `status`, `expires_at`, `scopes`.
- **Multi-tenant isolation:**
  - Every request resolves `current_workspace_id` via:
    - Workspace selector param/header, or
    - Default workspace for user.
  - Queries always filter by `workspace_id`.

---

## 7. Job Processing & Document Pipeline

1. **Upload:**

   - User uploads via UI or API.
   - FastAPI:
     - Saves file to `/data/storage/...`.
     - Inserts `documents` row `status='pending'`.
     - Adds `jobs` row:
       - `type='document_extraction'`
       - `payload` includes `document_id`, `template_id`, `workspace_id`.
       - `scheduled_at=now`, `max_attempts` (e.g., 5).

2. **Worker loop:**

   - Separate process (same Docker image) running:
     - `while True`: fetch `jobs` where `status='queued' and scheduled_at <= now`, lock row (FOR UPDATE SKIP LOCKED).
     - Set status `processing`.
     - Dispatch by `type`.

3. **Document extraction job:**

   - Load document, run OCR / parsing stack (external lib/service).
   - Apply `Template.field_schema` to map extracted fields, run validation.
   - Save `ExtractionResult` with incremented `version`.
   - Append `ExtractionLogs` (info/warnings/errors).
   - Update `Document.status` to `succeeded` or `failed`.
   - Update template `success_count` / `failure_count`.
   - Update `UsageRecord` for that workspace/date (upsert).
   - Enqueue webhook jobs for `document.completed` event.

4. **Webhook delivery job:**
   - For each subscribed `WebhookConfig`:
     - Build payload with document, extraction, etc.
     - Compute signature using `secret`.
     - Perform HTTP request.
     - Save/Update `WebhookDelivery` with status, status_code.
     - On failure, reschedule with backoff up to retry policy; fire `webhook_failures_exceeded` when threshold crossed (and notify).

---

## 8. Infrastructure & Deployment

### Containers (Docker Compose topology)

- `nginx` – reverse proxy and static assets.
- `frontend` – Next.js app:
  - `next build` then `next start` (or using standalone mode).
- `backend` – FastAPI app:
  - `uvicorn main:app`.
- `worker` – FastAPI worker entrypoint:
  - Same image as backend, but runs `python -m docdata.worker`.
- `db` – Postgres.
- `redis` (optional) – If you later move jobs off Postgres; initially can be omitted.
- Volumes:
  - `db_data` for Postgres.
  - `storage_data` for `/data/storage` (documents + exports).
  - `next_static` for compiled assets (or built within image).

### Nginx Routing

- `location /api` → `backend:8000`
- `location /admin` → `backend:8000` (or NextJS if you build admin as frontend).
- `location /_next`, `/static` → `frontend:3000`.
- `location /` → `frontend:3000`.

### Monitoring & Logging

- FastAPI + Uvicorn logs to stdout, collected by Docker.
- Request/response logging middleware (sanitizing sensitive data).
- Metrics:
  - Application-level metrics endpoint `/metrics` (Prometheus format) optional.
  - DB: use pg_stat tables or external tools.
- Error tracking: Sentry (optional).

---

## 9. Non-functional Considerations

- **Performance (TTFB 300ms, page load 2s):**

  - Use SSR/streaming for most dashboard views.
  - Indexes on `workspace_id`, foreign keys, and frequent query filters.
  - Background jobs keep heavy OCR work off request path.

- **Availability (99.9% target):**

  - Stateless services: multiple replicas feasible in future orchestrator.
  - Graceful restarts for worker processes.

- **Scalability:**

  - Simplest path: scale `backend` and `worker` containers horizontally; Postgres vertical scaling.
  - Migrate job queue to Redis or dedicated system (e.g., Celery/RQ) if DB queue becomes a bottleneck.

- **Security & Compliance:**
  - TLS everywhere; strict cookie flags.
  - Audit logs for key security/billing actions.
  - Webhook signature verification & documentation.

---

## 10. JSON Summary (Entities & API Endpoints)

```json
{
  "entities": [
    {
      "name": "User",
      "fields": [
        "id:uuid",
        "email:string",
        "password_hash:string",
        "full_name:string?",
        "role:enum(admin,owner,member,readonly)",
        "workspace_id:uuid?",
        "is_email_verified:boolean",
        "created_at:datetime",
        "updated_at:datetime",
        "last_login_at:datetime?",
        "auth_provider:enum(local,google)"
      ]
    },
    {
      "name": "Workspace",
      "fields": [
        "id:uuid",
        "name:string",
        "owner_user_id:uuid",
        "stripe_customer_id:string?",
        "created_at:datetime",
        "updated_at:datetime",
        "status:enum(active,suspended,trial,canceled)",
        "trial_ends_at:datetime?",
        "primary_color:string?",
        "logo_url:string?",
        "custom_domain:string?"
      ]
    },
    {
      "name": "WorkspaceMember",
      "fields": [
        "id:uuid",
        "workspace_id:uuid",
        "user_id:uuid",
        "role:enum(owner,member,readonly)",
        "invited_at:datetime",
        "joined_at:datetime?"
      ]
    },
    {
      "name": "Subscription",
      "fields": [
        "id:uuid",
        "workspace_id:uuid",
        "stripe_subscription_id:string",
        "plan_id:string",
        "status:enum(active,past_due,canceled,trialing)",
        "current_period_start:datetime",
        "current_period_end:datetime",
        "cancel_at_period_end:boolean",
        "created_at:datetime",
        "updated_at:datetime"
      ]
    },
    {
      "name": "UsageRecord",
      "fields": [
        "id:uuid",
        "workspace_id:uuid",
        "date:date",
        "documents_processed:int",
        "pages_processed:int",
        "created_at:datetime"
      ]
    },
    {
      "name": "Project",
      "fields": [
        "id:uuid",
        "workspace_id:uuid",
        "name:string",
        "description:string?",
        "created_by_user_id:uuid",
        "created_at:datetime",
        "updated_at:datetime"
      ]
    },
    {
      "name": "Template",
      "fields": [
        "id:uuid",
        "workspace_id:uuid",
        "project_id:uuid?",
        "name:string",
        "description:string?",
        "document_type:string?",
        "field_schema:json",
        "default_export_format:enum(json,csv,excel)",
        "created_by_user_id:uuid",
        "last_run_at:datetime?",
        "success_count:int",
        "failure_count:int",
        "created_at:datetime",
        "updated_at:datetime"
      ]
    },
    {
      "name": "Document",
      "fields": [
        "id:uuid",
        "workspace_id:uuid",
        "project_id:uuid?",
        "template_id:uuid?",
        "file_name:string",
        "file_type:string",
        "storage_path:string",
        "pages:int?",
        "status:enum(pending,processing,succeeded,failed)",
        "uploaded_by_user_id:uuid",
        "source:enum(ui,api)",
        "created_at:datetime",
        "updated_at:datetime",
        "last_error:string?"
      ]
    },
    {
      "name": "ExtractionResult",
      "fields": [
        "id:uuid",
        "document_id:uuid",
        "template_id:uuid",
        "workspace_id:uuid",
        "extracted_json:json",
        "version:int",
        "created_at:datetime"
      ]
    },
    {
      "name": "ExtractionLog",
      "fields": [
        "id:uuid",
        "document_id:uuid",
        "level:enum(info,warning,error)",
        "message:string",
        "metadata:json?",
        "created_at:datetime"
      ]
    },
    {
      "name": "Job",
      "fields": [
        "id:uuid",
        "type:enum(document_extraction,webhook_delivery)",
        "payload:json",
        "status:enum(queued,processing,succeeded,failed)",
        "attempts:int",
        "max_attempts:int",
        "last_error:string?",
        "scheduled_at:datetime",
        "created_at:datetime",
        "updated_at:datetime"
      ]
    },
    {
      "name": "ApiKey",
      "fields": [
        "id:uuid",
        "workspace_id:uuid",
        "name:string",
        "key_hash:string",
        "prefix:string",
        "scopes:json",
        "status:enum(active,revoked)",
        "expires_at:datetime?",
        "last_used_at:datetime?",
        "created_at:datetime"
      ]
    },
    {
      "name": "WebhookConfig",
      "fields": [
        "id:uuid",
        "workspace_id:uuid",
        "target_url:string",
        "secret:string",
        "events:json",
        "retry_policy:json",
        "enabled:boolean",
        "created_at:datetime",
        "updated_at:datetime"
      ]
    },
    {
      "name": "WebhookDelivery",
      "fields": [
        "id:uuid",
        "webhook_config_id:uuid",
        "workspace_id:uuid",
        "event_type:string",
        "payload:json",
        "status_code:int?",
        "delivery_status:enum(pending,succeeded,failed)",
        "attempt_count:int",
        "last_error:string?",
        "created_at:datetime",
        "updated_at:datetime"
      ]
    },
    {
      "name": "AuditLog",
      "fields": [
        "id:uuid",
        "workspace_id:uuid?",
        "user_id:uuid?",
        "actor_type:enum(user,system)",
        "event_type:string",
        "description:string",
        "metadata:json?",
        "created_at:datetime"
      ]
    }
  ],
  "api_endpoints": [
    {
      "id": "E_auth_login",
      "method": "POST",
      "path": "/api/auth/login",
      "description": "User login with email and password, returns JWT and user"
    },
    {
      "id": "E_auth_register",
      "method": "POST",
      "path": "/api/auth/register",
      "description": "Register new user and initial workspace"
    },
    {
      "id": "E_me",
      "method": "GET",
      "path": "/api/auth/me",
      "description": "Get current user, workspaces, and active workspace"
    },
    {
      "id": "E_projects_list",
      "method": "GET",
      "path": "/api/projects",
      "description": "List projects in current workspace"
    },
    {
      "id": "E_projects_create",
      "method": "POST",
      "path": "/api/projects",
      "description": "Create a new project in current workspace"
    },
    {
      "id": "E_templates_list",
      "method": "GET",
      "path": "/api/templates",
      "description": "List templates in current workspace"
    },
    {
      "id": "E_templates_create",
      "method": "POST",
      "path": "/api/templates",
      "description": "Create a new extraction template"
    },
    {
      "id": "E_templates_update",
      "method": "PUT",
      "path": "/api/templates/:templateId",
      "description": "Update an existing template"
    },
    {
      "id": "E_documents_upload",
      "method": "POST",
      "path": "/api/documents",
      "description": "Upload a document and enqueue extraction job"
    },
    {
      "id": "E_documents_get",
      "method": "GET",
      "path": "/api/documents/:documentId",
      "description": "Get document details, latest extraction result, and logs"
    },
    {
      "id": "E_documents_retry",
      "method": "POST",
      "path": "/api/documents/:documentId/retry",
      "description": "Retry document extraction via new job"
    },
    {
      "id": "E_extractions_export",
      "method": "GET",
      "path": "/api/documents/:documentId/export",
      "description": "Generate and return download URL for extraction export"
    },
    {
      "id": "E_api_keys_list",
      "method": "GET",
      "path": "/api/api-keys",
      "description": "List API keys for current workspace"
    },
    {
      "id": "E_api_keys_create",
      "method": "POST",
      "path": "/api/api-keys",
      "description": "Create a new API key and return plaintext once"
    },
    {
      "id": "E_api_keys_revoke",
      "method": "POST",
      "path": "/api/api-keys/:apiKeyId/revoke",
      "description": "Revoke an existing API key"
    },
    {
      "id": "E_webhooks_get",
      "method": "GET",
      "path": "/api/webhooks",
      "description": "List webhook configurations for current workspace"
    },
    {
      "id": "E_webhooks_upsert",
      "method": "POST",
      "path": "/api/webhooks",
      "description": "Create or update a webhook configuration"
    },
    {
      "id": "E_webhooks_test",
      "method": "POST",
      "path": "/api/webhooks/test",
      "description": "Send a test event to a configured webhook"
    },
    {
      "id": "E_usage_summary",
      "method": "GET",
      "path": "/api/usage/summary",
      "description": "Get current period usage and plan limits"
    },
    {
      "id": "E_public_extract_via_api_key",
      "method": "POST",
      "path": "/api/v1/documents:extract",
      "description": "Programmatic document extraction using API key auth"
    }
  ]
}
```
