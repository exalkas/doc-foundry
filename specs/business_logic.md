## 1. Core Business Model

### 1.1 Who is this for (so logic makes sense)

Target segments (because pricing/limits will differ):

1. **Solo devs / makers / agencies**
   - Use it as a backend OCR/parser for their products or client projects.
2. **SMEs & operations teams**
   - Use no-code integrations (Make/Zapier/n8n) + UI templates.
3. **Enterprise / ISVs**
   - Need SLAs, custom models, volume discounts, and team access.

The business logic must support:

- **Low-friction entry** : free tier + credit-based.
- **Usage-based scale** : price scales with pages / extractions.
- **Upgrade path** : per-seat or per-workspace for teams.

---

## 2. Key Concepts / Domain Model

Define these entities; all business logic hangs off them:

- **User** : individual account (email + password or SSO).
- **Workspace / Organization** :
- Owner: 1 user
- Members: many users
- Has: usage, API keys, webhooks.
- Note: Subscription and billing are per-user, not per-workspace.
- **Project** :
- Belongs to one workspace
- Contains documents, templates, logs.
- **Template** :
- Custom field mapping for a document type.
- Has: name, version, status, configuration, test docs.
- **Document** :
- Uploaded file, associated with project (and optionally template).
- Has extraction jobs + results.
- **Extraction Job** :
- A single processing run (one document + one template).
- State machine: `queued → processing → succeeded/failed/needs_review`.
- **Usage Record** :
- Tracks billable usage: pages processed, extractions, storage GB-months.
- **Subscription / Plan** :
- Defines limits, included usage, overage pricing, features.
- **API Key** :
- Bound to workspace; used for programmatic access.
- **Webhook Endpoint** :
- URL + secret; receives job events.
- **Integration Connection** :
- Zapier/Make/n8n config/credentials if needed.

---

## 3. Plans, Limits, and Pricing Logic

### 3.1 Plan Types

You can start with 4 plans:

1. **Free**
   - No credit card required.
   - Intended for testing, hobby devs, and evaluation.
2. **Starter**
   - Small businesses and serious devs.
3. **Pro**
   - Agencies and SMEs with regular needs.
4. **Enterprise**
   - Custom contract.

### 3.2 Plan Attributes

Each plan defines:

- **Monthly base price** (except Free).
- **Included pages / extractions** per month.

  Example:

  - Free: 100 pages / month
  - Starter: 5,000 pages / month
  - Pro: 50,000 pages / month

- **Overage price** :
- e.g. $X per 1,000 extra pages above included quota.
- **Max pages per document** (to avoid abuse).
- **Max file size** per document.
- **Max concurrent jobs** per workspace.
- **Retention period** for documents & logs.
- **Features** toggles:

  - Template count limit
  - Projects per workspace
  - Webhooks on/off
  - Priority queue on higher plans
  - Make/Zapier/n8n integration availability
  - SSO / custom branding for Enterprise only

### 3.3 Usage & Billing Logic

- Each **successful extraction job** :
  - Compute page count from the PDF/image (after OCR).
  - Billable usage = `number_of_pages` (or `1` if you want per-document billing).
- At the end of each day:
  - Aggregate usage per workspace into **DailyUsageRecord** .
- At the end of each billing cycle:

  - Sum all usage over included quota.
  - Calculate overage fee = `(max(0, total_pages - included_pages) / unit) * unit_price`.
  - Generate invoice / charge through Stripe.

  **Soft vs Hard Limits** :

- Free plan: **hard limit** (stop processing when quota reached).
- Paid plans: **soft limit** (allow overage with charge) or optional hard cap that user can enable.

---

## 4. Authentication, Workspaces & Roles

### 4.1 Roles

Inside each workspace:

- **Owner**
  - Manages billing, subscription, workspace-level settings.
  - Can invite/remove members.
- **Admin**
  - Manage projects, templates, API keys, webhooks.
- **Member**
  - Use templates, upload docs, view logs.
- **Read-only**
  - Only view logs, results, no changes.

### 4.2 Workspace Logic

- A user can belong to multiple workspaces.
- Every **request through API key** is scoped to exactly one workspace.
- Billing is per user, not per workspace. Workspaces are organizational units that help users organize their projects, templates, and documents. A user has one subscription that covers usage across all their workspaces.

---

## 5. Document Processing Lifecycle (Core Business Logic)

This is the heart of the product.

### 5.1 Upload Flow (UI)

1. User selects project + template (optional).
2. User uploads file:
   - Validate: file type, size, page count limits.
   - Store file in file storage (local FS initially, S3 compatible later).
3. System creates `Document` record in DB with:
   - `status = uploaded`
   - Metadata: filename, size, page count (if possible), mime type.
4. System enqueues an `ExtractionJob` with:
   - document_id, template_id (or auto-detect), workspace_id.
   - `status = queued`.

### 5.2 Upload Flow (API)

- Similar, but:
  - Client sends `multipart/form-data` or file URL.
  - Must include API key.
  - Optionally specify `template_id` or `auto_detect = true`.
- The business logic is the same: create `Document` + queue `ExtractionJob`.

### 5.3 Extraction Job State Machine

`ExtractionJob` states:

- `queued` → waiting in job queue.
- `processing` → worker picked it up.
- `succeeded` → extraction done.
- `failed` → error occurred (non-retriable or retries exhausted).
- `needs_review` → extraction done but with low confidence / validation rules failed.

**Transitions:**

1. **queued → processing**
   - Worker pulls job.
   - Re-check usage limits (if already over hard cap, fail job early).
2. **processing → succeeded**
   - OCR (if needed) + template application.
   - Post-processing rules (validation, type checking).
   - Store result in DB (JSON blob).
   - Record usage (pages).
   - Trigger events (webhook, Make/Zapier).
3. **processing → failed**
   - Non-recoverable error: corrupted file, unsupported format, engine failure.
4. **processing → needs_review**
   - Confidence below threshold OR validation rules fail.
   - User can open a **Review UI** , correct fields, and save.
   - After review, state can become `succeeded`.

### 5.4 Retry Logic

- Configurable per plan:
  - Free: 1 retry.
  - Starter/Pro: 3 retries.
- Retry on:
  - temporary engine errors, network timeouts, OCR timeouts.
- Exponential backoff: 1 min → 5 min → 15 min.
- After last failure: state = `failed`, send error notification (webhook + email if enabled).

---

## 6. Template & Extraction Logic (Business Rules)

### 6.1 Template Types

Support these types:

1. **Fixed-layout template**
   - For invoices, receipts, shipping docs with predictable structure.
   - Fields defined by:
     - Regex, anchor text (e.g. “Subtotal”), relative positions.
2. **Key-value / ML template**
   - For more flexible documents (contracts, CVs).
   - Use ML model to detect entities; user maps them to fields.
3. **Form template**
   - For standardized forms with fields in specific positions.

### 6.2 Template Fields

Each field in a template:

- Has:
  - `name` (user-facing)
  - `key` (JSON key)
  - `data_type` (string, number, date, enum, boolean, array)
  - `required` (boolean)
  - `validation_rules`:
    - Regex
    - Range (min/max)
    - Allowed values
  - `post_processing`:
    - Normalize dates, currencies, decimals, trimming, etc.

### 6.3 Template Versioning

- Editing a template creates a new version:
  - v1, v2, v3…
- Extraction jobs always reference a specific **template version** .
- You can “promote” a version to be the default.

### 6.4 Auto-Detection Logic

For API/automation usage:

- If `template_id` is not specified:
  - Use ML / heuristic to match document against existing templates:
    - Compare with sample docs’ embeddings.
    - If best match confidence > threshold → auto-assign template.
    - Else → mark job `needs_review` with “template not found” error.

---

## 7. Exporters & Delivery Logic

### 7.1 Export Formats

On each job completion:

- Store canonical result as **JSON** in DB.
- Derived exporters:
  - **JSON** : default API/webhook payload.
  - **CSV** : row per extraction; columns = fields.
  - **Excel** : same as CSV but XLSX.

Users can:

- Download result from UI.
- Fetch via API.
- Receive via webhooks/Make/Zapier/n8n.

### 7.2 Webhook Behavior

When job transitions to final state `succeeded`, `failed`, or `needs_review`:

- Send POST request to all **active webhook endpoints** for workspace/project that match:
  - event type filter (job.completed, job.failed, job.needs_review).
- Payload includes:
  - job_id, document_id, workspace_id, template_id, status, timestamps.
  - extracted_data (for succeeded/needs_review).
  - error details (for failed).

Retry webhook on:

- 5xx or timeout, with exponential backoff.
- Stop after N attempts; mark webhook_delivery as `failed`.

### 7.3 Make.com / Zapier / n8n

Business logic from your side:

- Each integration is essentially a **wrapper around webhooks + API** .
- Provide:
  - **Trigger** : “New extraction result” → fires on job completion.
  - **Action** : “Create extraction job” → upload file from URL or buffer.
- Keep quotas and usage logic exactly the same; just treat them as API calls with an integration label.

---

## 8. Usage Metering Logic

You need a clear, deterministic way to charge.

**Primary unit** : pages processed.

- For PDFs: actual page count.
- For images: each image = 1 page (or allow multi-page TIFF).
- For other file types: define rules.

**When to increment usage:**

- Only when job transitions to `succeeded` or `needs_review`.
- Failed jobs:
  - Free plan: count as used pages (prevents abuse).
  - Paid plans: configurable; you can choose not to charge for failures.

**What is shown in Dashboard:**

- Monthly usage vs plan quota.
- Breakdown by:
  - project
  - template
  - integration (API, UI, Zapier, Make, n8n)
- History of daily usage for last 90 days.

---

## 9. Subscription Logic

### 9.1 Trial

- Optional 7–14 day trial for paid plans:
  - Full features but with a **usage cap** .
  - After trial:
    - If user adds payment method → continue as paid.
    - If not → downgrade to Free.

### 9.2 Upgrades / Downgrades

- **Upgrade** (Free → Starter, Starter → Pro):
  - Apply immediately.
  - New limits and features activated.
  - Prorate billing if needed via Stripe.
- **Downgrade** :
- Enter `pending_downgrade` state.
- Takes effect at end of current billing period.
- Prevent downgrade if:
  - Current usage or features exceed target plan’s hard limits, _or_ :
  - Show warnings and tell user what will happen (some templates archived, webhooks disabled, etc.).

---

## 10. Admin Panel Business Logic

Internal admin side should support:

- Search workspaces, users, documents, jobs.
- Force plan changes or add bonus pages.
- View error rates and processing time.
- Manually reprocess a job with a different engine or template.
- Flag abusive accounts (too many uploads, suspicious activity).
- Configure global limits (max pages per job, max file size).
- Toggle “maintenance” mode for certain features.

---

## 11. Onboarding, Guidance & UX Logic

This is business-critical; otherwise users churn immediately.

### 11.1 First-Time User Flow

- When a new workspace is created:
  1. Create a **sample project** : “Getting Started”.
  2. Create **2–3 sample templates** :
     - Invoice (B2B)
     - Receipt
     - Simple contract
  3. Provide **sample documents** to test extraction immediately.
  4. Guide:
     - Step 1: upload example invoice.
     - Step 2: open template editor; tweak fields.
     - Step 3: see extraction logs.
     - Step 4: copy API key and run the first curl / Postman example.

### 11.2 In-App Assistant

- Provide docs & guides:
  - How to set up webhooks.
  - How to connect Make/Zapier/n8n.
  - How to debug extraction issues.
- Show “playbooks”:
  - “Send invoices to Google Sheets”
  - “Sync CV data to Airtable”
  - “Push packing lists to ERP”

---

## 12. High-Level “If-This-Then-That” Business Rules

To make it crystal clear, here are explicit rules:

1. **If** workspace usage ≥ quota and plan has hard cap

   → New extraction jobs are rejected with `402 Payment Required`-style error.

2. **If** workspace usage ≥ quota and plan allows overage

   → Continue processing, mark additional usage as overage for billing.

3. **If** a webhook endpoint responds with 2xx

   → Mark delivery `succeeded`.

4. **If** webhook repeatedly fails

   → Mark endpoint `disabled` and notify workspace owner via email.

5. **If** job’s extraction confidence < threshold OR validation fails

   → Mark job `needs_review` and notify relevant users depending on project notification settings.

6. **If** user is on Free plan and inactive for N days (e.g. 90)

   → Optionally archive documents (keep minimal metadata) to reduce storage costs.

7. **If** billing payment fails

   - Grace period (e.g. 7 days): show warnings, allow usage.
   - After grace period:
     - Downgrade to Free or “suspended” plan.
     - Block new extractions but keep historical data read-only.

---
