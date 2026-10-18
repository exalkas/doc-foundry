Drafting the business requirements document. Reviewing a few more details, then providing the full document:

[4 tools called]

Business requirements document for the admin app:

```markdown
# Admin App Business Requirements Document

**Version:** 1.0  
**Date:** 2024  
**Status:** Draft  
**Project:** DocFoundry Admin Platform

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Admin Roles & Permissions](#admin-roles--permissions)
3. [Domain-by-Domain CRUD Matrix](#domain-by-domain-crud-matrix)
4. [Control & Correction Capabilities](#control--correction-capabilities)
5. [Business Rules & Constraints](#business-rules--constraints)
6. [Audit & Compliance](#audit--compliance)
7. [Security Requirements](#security-requirements)
8. [User Interface Requirements](#user-interface-requirements)

---

## Executive Summary

### Purpose
The Admin App is a separate, dedicated frontend application for platform administrators to manage, monitor, and control all aspects of the DocFoundry SaaS platform. It provides comprehensive oversight capabilities across workspaces, users, billing, affiliates, system operations, and customer support.

### Scope
This document defines:
- What administrators can **Create, Read, Update, Delete** (CRUD) across all domains
- What administrators can **control and correct** (override, fix, adjust)
- **Business rules** governing admin actions
- **Correction workflows** for common scenarios
- **Audit requirements** for compliance and accountability

### Key Principles
1. **Separation of Concerns**: Admin app is completely separate from user-facing app
2. **Principle of Least Privilege**: Admins can only perform actions necessary for platform management
3. **Audit Everything**: All admin actions must be logged with context
4. **Reversibility**: Critical actions should be reversible where possible
5. **Transparency**: Admins must provide reasons/notes for significant actions

---

## Admin Roles & Permissions

### Admin Role Definition
- **Role Name**: `admin` (stored in `users.role` enum)
- **Access Level**: Platform-wide, cross-tenant access
- **Authentication**: Same JWT-based auth as main app, but separate frontend
- **Authorization**: Backend validates `role == "admin"` for all admin endpoints

### Permission Model
- **Read-Only Access**: View-only access to all platform data
- **Full CRUD**: Create, read, update, delete capabilities (domain-specific)
- **Override Capabilities**: Ability to bypass normal business rules when necessary
- **System Control**: Ability to manage platform-level settings and operations

---

## Domain-by-Domain CRUD Matrix

### 1. Workspaces (Companies/Tenants)

| Operation | Allowed | Details | Constraints |
|-----------|---------|---------|-------------|
| **Create** | ❌ No | Workspaces created via user registration | N/A |
| **Read** | ✅ Yes | List all workspaces with filters (status, plan, date range) | Pagination required (max 100/page) |
| **Update** | ⚠️ Limited | Can update: `status`, `notes` (internal admin notes) | Cannot change: `name`, `owner_user_id`, `stripe_customer_id` |
| **Delete** | ❌ No | Soft-delete via suspension | Use suspend instead |

**Read Capabilities:**
- List all workspaces with pagination
- Filter by: `status` (active/suspended/trial/canceled), `plan`, `created_at` range
- View workspace details: name, owner, plan, status, member count, usage stats
- View workspace members and their roles
- View workspace subscription history

**Update Capabilities:**
- Change workspace `status` (active ↔ suspended)
- Add internal admin `notes` (not visible to workspace owner)
- Cannot modify: workspace name, owner, Stripe customer ID (use Stripe dashboard)

**Special Actions:**
- **Suspend**: Set status to `suspended` (requires reason/notes)
- **Unsuspend**: Restore to `active` status
- **Impersonate Owner**: Generate impersonation token to access workspace as owner

---

### 2. Users (Platform Users)

| Operation | Allowed | Details | Constraints |
|-----------|---------|---------|-------------|
| **Create** | ✅ Yes | Create admin users or support accounts | Must set `role` and `is_email_verified` |
| **Read** | ✅ Yes | List all users, view user details | Can filter by role, email, workspace membership |
| **Update** | ⚠️ Limited | Can update: `role`, `is_email_verified`, `is_active` (if exists) | Cannot change: `email`, `password_hash` |
| **Delete** | ❌ No | Soft-delete via deactivation | Use deactivation instead |

**Read Capabilities:**
- List all users with pagination
- Filter by: `role` (admin/user), `email`, `workspace_id`, `auth_provider`
- View user details: email, name, role, workspaces, subscription, last login
- View user's workspace memberships and roles
- View user's API keys and webhooks

**Create Capabilities:**
- Create new admin users (for onboarding new admins)
- Create support/test accounts
- Must set: `email`, `password_hash`, `role`, `is_email_verified=true`

**Update Capabilities:**
- Change user `role` (user ↔ admin) - **CRITICAL ACTION** (requires audit log)
- Set `is_email_verified=true` (for email verification issues)
- Cannot modify: `email` (use user's own account), `password_hash` (use password reset)

**Special Actions:**
- **Reset Password**: Trigger password reset email (via user's own account flow)
- **View Audit Logs**: See all actions performed by this user

---

### 3. Affiliates (Partner Program)

| Operation | Allowed | Details | Constraints |
|-----------|---------|---------|-------------|
| **Create** | ❌ No | Affiliates created via application flow | N/A |
| **Read** | ✅ Yes | List all affiliates, view details, stats | Filter by status, date range |
| **Update** | ✅ Yes | Update status, commission plan, notes | Status transitions must follow workflow |
| **Delete** | ❌ No | Use "block" status instead | N/A |

**Read Capabilities:**
- List all affiliates with pagination
- Filter by: `status` (pending/approved/rejected/blocked), `created_at` range
- View affiliate details: user info, slug, company, website, payment details
- View affiliate stats: clicks, signups, paying customers, earnings (pending/cleared/paid)
- View affiliate links and campaigns
- View all commissions for an affiliate
- View payout history

**Update Capabilities:**
- **Approve Affiliate**: Change status from `pending` → `approved`
  - Can assign commission plan (default: Standard 25%)
  - Can add notes
- **Reject Affiliate**: Change status from `pending` → `rejected`
  - Must provide reason/notes
- **Block Affiliate**: Change status to `blocked` (prevents new commissions)
  - Must provide reason
  - Existing cleared commissions still payable
- **Update Commission Plan**: Change affiliate's commission plan
  - Can upgrade/downgrade commission rate
  - Affects future commissions only
- **Update Notes**: Add internal admin notes (not visible to affiliate)

**Special Actions:**
- **Manual Commission Adjustment**: Create or modify commission records
  - Can add commission (e.g., bonus)
  - Can reduce commission (e.g., refund adjustment)
  - Must provide reason and amount
  - Creates audit log entry
- **Approve Payout**: Mark payout as approved and paid
  - Can add payment reference (transaction ID)
  - Can add notes
- **Reject Payout**: Reject payout request
  - Must provide reason
  - Commissions return to cleared status

---

### 4. Commissions (Affiliate Commissions)

| Operation | Allowed | Details | Constraints |
|-----------|---------|---------|-------------|
| **Create** | ✅ Yes | Manual commission creation (adjustments) | Must provide reason |
| **Read** | ✅ Yes | List all commissions, filter by affiliate/customer | Full access to commission records |
| **Update** | ✅ Yes | Update status, amount, notes | Status transitions must follow rules |
| **Delete** | ❌ No | Use "reversed" status instead | N/A |

**Read Capabilities:**
- List all commissions with pagination
- Filter by: `affiliate_id`, `customer_id`, `status`, `event_type`, date range
- View commission details: amount, currency, status, event type, dates
- View related subscription and payout info

**Create Capabilities:**
- **Manual Commission**: Create commission record manually
  - Must specify: `affiliate_id`, `customer_id`, `amount`, `reason`
  - Status defaults to `pending`
  - Creates audit log

**Update Capabilities:**
- **Adjust Amount**: Modify commission amount
  - Must provide reason
  - Creates audit log
  - Can only adjust `pending` or `cleared` commissions (not `paid`)
- **Change Status**: 
  - `pending` → `cleared` (bypass hold period)
  - `cleared` → `paid` (mark as paid without payout)
  - Any → `reversed` (reverse commission, e.g., refund)
- **Add Notes**: Add internal admin notes

**Business Rules:**
- Cannot modify `paid` commissions (must reverse and create new)
- Reversed commissions cannot be un-reversed
- Status transitions must be logical (cannot go backwards)

---

### 5. Payouts (Affiliate Payouts)

| Operation | Allowed | Details | Constraints |
|-----------|---------|---------|-------------|
| **Create** | ❌ No | Payouts created by affiliates | N/A |
| **Read** | ✅ Yes | List all payouts, view details | Filter by status, affiliate, date |
| **Update** | ✅ Yes | Update status, payment reference, notes | Status transitions must follow workflow |
| **Delete** | ❌ No | Use "rejected" status instead | N/A |

**Read Capabilities:**
- List all payouts with pagination
- Filter by: `status` (requested/approved/paid/rejected), `affiliate_id`, date range
- View payout details: amount, currency, payment method, status, dates
- View related commissions included in payout

**Update Capabilities:**
- **Approve Payout**: Change status `requested` → `approved`
  - Can add payment reference (transaction ID)
  - Can add notes
  - Marks related commissions as `paid`
- **Mark as Paid**: Change status `approved` → `paid`
  - Sets `processed_at` timestamp
  - Can add payment reference
- **Reject Payout**: Change status to `rejected`
  - Must provide reason
  - Returns commissions to `cleared` status
- **Update Payment Reference**: Add/update transaction ID or payment reference

**Business Rules:**
- Cannot approve payout if affiliate has insufficient cleared balance
- Rejected payouts cannot be re-approved (affiliate must create new request)
- Paid payouts cannot be modified (use notes only)

---

### 6. Subscriptions & Billing

| Operation | Allowed | Details | Constraints |
|-----------|---------|---------|-------------|
| **Create** | ❌ No | Subscriptions created via Stripe checkout | Use Stripe dashboard |
| **Read** | ✅ Yes | View all subscriptions, Stripe data | Full read access |
| **Update** | ⚠️ Limited | Can update: `notes` (internal) | Cannot modify Stripe data directly |
| **Delete** | ❌ No | Cancel via Stripe | Use Stripe dashboard or user's billing portal |

**Read Capabilities:**
- List all subscriptions with pagination
- Filter by: `status`, `plan_id`, `user_id`, date range
- View subscription details: plan, status, billing period, Stripe subscription ID
- View Stripe customer ID and payment method (last 4 digits)
- View subscription history for a user
- View usage vs. plan limits

**Update Capabilities:**
- **Add Notes**: Add internal admin notes about subscription
- **Cannot Modify**: Stripe subscription data (use Stripe dashboard)

**Special Actions:**
- **View Stripe Dashboard**: Link to Stripe customer/subscription in Stripe dashboard
- **View Billing Portal**: Generate billing portal session for user
- **View Usage Analytics**: See detailed usage breakdown for subscription period

**Business Rules:**
- All subscription modifications should go through Stripe (source of truth)
- Admin can view but not modify Stripe data directly
- For billing issues, use Stripe dashboard or contact Stripe support

---

### 7. Documents & Extractions

| Operation | Allowed | Details | Constraints |
|-----------|---------|---------|-------------|
| **Create** | ❌ No | Documents created by users | N/A |
| **Read** | ✅ Yes | View all documents, extraction results | Full read access for support |
| **Update** | ⚠️ Limited | Can update: `status` (for corrections) | Must log reason |
| **Delete** | ❌ No | Soft-delete not implemented | Use workspace owner deletion |

**Read Capabilities:**
- List all documents with pagination
- Filter by: `workspace_id`, `project_id`, `status`, `source`, date range
- View document details: name, file path, status, extraction results
- View extraction results: extracted data, confidence scores, logs
- View extraction logs: processing history, errors, warnings
- Download original document (for support purposes)

**Update Capabilities:**
- **Retry Extraction**: Trigger reprocessing of failed document
  - Resets status to `pending`
  - Creates new job
  - Must log reason (e.g., "Admin retry after template fix")
- **Update Status**: Manually change status (rare, for corrections)
  - Must provide reason
  - Creates audit log

**Special Actions:**
- **Reprocess Document**: Force reprocessing via job queue
- **View Extraction Logs**: See detailed processing logs
- **Download Document**: Access original file (for support)

**Business Rules:**
- Cannot delete documents (data retention policy)
- Retry should be used sparingly (investigate root cause first)
- Document access logged for compliance

---

### 8. Templates (Extraction Templates)

| Operation | Allowed | Details | Constraints |
|-----------|---------|---------|-------------|
| **Create** | ❌ No | Templates created by workspace owners | N/A |
| **Read** | ✅ Yes | View all templates across workspaces | Full read access |
| **Update** | ⚠️ Limited | Can update: `notes` (internal) | Cannot modify template schema |
| **Delete** | ❌ No | Deletion handled by workspace owner | N/A |

**Read Capabilities:**
- List all templates with pagination
- Filter by: `workspace_id`, `project_id`, date range
- View template details: name, field schema, validation rules
- View template usage stats: success rate, usage count, last run
- View template library entries (public templates)

**Update Capabilities:**
- **Add Notes**: Add internal admin notes about template
- **Cannot Modify**: Template schema (workspace owner's responsibility)

**Special Actions:**
- **View Template Library**: See public templates available to all workspaces
- **View Usage Stats**: See how often template is used and success rate

---

### 9. Projects (Workspace Organization)

| Operation | Allowed | Details | Constraints |
|-----------|---------|---------|-------------|
| **Create** | ❌ No | Projects created by workspace members | N/A |
| **Read** | ✅ Yes | View all projects across workspaces | Full read access |
| **Update** | ⚠️ Limited | Can update: `notes` (internal) | Cannot modify project data |
| **Delete** | ❌ No | Deletion handled by workspace owner | N/A |

**Read Capabilities:**
- List all projects with pagination
- Filter by: `workspace_id`, date range
- View project details: name, document count, template count
- View project's documents and templates

**Update Capabilities:**
- **Add Notes**: Add internal admin notes about project

---

### 10. API Keys (Customer Integrations)

| Operation | Allowed | Details | Constraints |
|-----------|---------|---------|-------------|
| **Create** | ❌ No | API keys created by workspace owners | N/A |
| **Read** | ✅ Yes | View all API keys across workspaces | Can see key prefix, not full key |
| **Update** | ⚠️ Limited | Can revoke API keys | Cannot modify key details |
| **Delete** | ❌ No | Use revoke instead | N/A |

**Read Capabilities:**
- List all API keys with pagination
- Filter by: `workspace_id`, `status` (active/revoked), date range
- View API key details: name, prefix, scopes, expiration, last used
- View API key usage stats: request count, last used date

**Update Capabilities:**
- **Revoke API Key**: Set status to `revoked`
  - Must provide reason
  - Creates audit log
  - Key immediately becomes invalid
- **Cannot View**: Full API key value (security - keys are hashed)

**Business Rules:**
- Cannot view full API key (only prefix for identification)
- Revocation is permanent (cannot un-revoke)
- Revocation reason required for audit

---

### 11. Webhooks (Customer Integrations)

| Operation | Allowed | Details | Constraints |
|-----------|---------|---------|-------------|
| **Create** | ❌ No | Webhooks created by workspace owners | N/A |
| **Read** | ✅ Yes | View all webhooks, deliveries, status | Full read access |
| **Update** | ⚠️ Limited | Can retry failed deliveries | Cannot modify webhook config |
| **Delete** | ❌ No | Deletion handled by workspace owner | N/A |

**Read Capabilities:**
- List all webhooks with pagination
- Filter by: `workspace_id`, `status`, date range
- View webhook details: URL, events, signing secret (masked), status
- View webhook delivery history: success/failure rates, last delivery
- View failed deliveries: error messages, retry count

**Update Capabilities:**
- **Retry Failed Delivery**: Manually retry a failed webhook delivery
  - Resets delivery status
  - Creates new delivery attempt
  - Must log reason
- **Cannot Modify**: Webhook configuration (workspace owner's responsibility)

**Special Actions:**
- **View Delivery Logs**: See all delivery attempts for a webhook
- **View Payload**: See webhook payload (for debugging, sanitized)

---

### 12. Jobs (Background Processing)

| Operation | Allowed | Details | Constraints |
|-----------|---------|---------|-------------|
| **Create** | ❌ No | Jobs created by system | N/A |
| **Read** | ✅ Yes | View all jobs, status, errors | Full read access |
| **Update** | ✅ Yes | Can reprocess failed jobs | Must log reason |
| **Delete** | ❌ No | Jobs retained for audit | N/A |

**Read Capabilities:**
- List all jobs with pagination
- Filter by: `type` (document_extraction/webhook_delivery), `status`, date range
- View job details: type, status, attempts, error messages, payload
- View job queue depth and processing stats

**Update Capabilities:**
- **Reprocess Job**: Reset failed job to `queued` status
  - Resets `attempts` to 0
  - Clears `last_error`
  - Sets `scheduled_at` to now
  - **Must provide reason** (e.g., "Template fixed", "Temporary error resolved")
  - Creates audit log

**Business Rules:**
- Can only reprocess `failed` jobs (not `succeeded` or `processing`)
- Reprocessing resets attempt counter
- Reason required for audit trail
- Should investigate root cause before reprocessing

---

### 13. System Metrics & Health

| Operation | Allowed | Details | Constraints |
|-----------|---------|---------|-------------|
| **Create** | ❌ No | Metrics generated by system | N/A |
| **Read** | ✅ Yes | View all system metrics | Real-time and historical |
| **Update** | ❌ No | Metrics are read-only | N/A |
| **Delete** | ❌ No | Metrics retained for analysis | N/A |

**Read Capabilities:**
- **Queue Depth**: Current number of queued jobs
- **Processing Stats**: Average processing time, jobs per day
- **Error Rates**: Errors in last 24 hours, error trends
- **Usage Stats**: Total documents processed, pages processed (platform-wide)
- **System Health**: Database connection status, worker status

**Metrics Available:**
- Queue depth (real-time)
- Average processing time (last 24h, 7d, 30d)
- Daily documents processed (trend)
- Errors last 24 hours
- Active workspaces count
- Active subscriptions count
- Platform MRR (Monthly Recurring Revenue)

---

### 14. Audit Logs (Compliance & Accountability)

| Operation | Allowed | Details | Constraints |
|-----------|---------|---------|-------------|
| **Create** | ❌ No | Logs created by system | N/A |
| **Read** | ✅ Yes | View all audit logs | Full read access |
| **Update** | ❌ No | Logs are immutable | N/A |
| **Delete** | ❌ No | Logs retained for compliance | N/A |

**Read Capabilities:**
- List all audit logs with pagination
- Filter by: `workspace_id`, `user_id`, `actor_type`, `event_type`, date range
- View log details: actor, action, target, metadata, timestamp
- Export logs for compliance (CSV/JSON)

**Log Types:**
- **User Actions**: Login, logout, create, update, delete
- **Admin Actions**: All admin CRUD operations
- **System Events**: Job processing, webhook delivery, errors
- **Security Events**: Failed login attempts, API key revocations

**Business Rules:**
- Audit logs are immutable (cannot be modified or deleted)
- Retention period: Minimum 1 year (configurable)
- Export capability for compliance audits

---

## Control & Correction Capabilities

### Workspace Management

#### Suspend Workspace
**When to Use:**
- Abuse detected (high usage spikes, quota abuse)
- Payment issues (chargeback, fraudulent payment)
- Terms of service violation
- Security concerns

**Workflow:**
1. Admin reviews workspace (usage analytics, abuse detection)
2. Admin clicks "Suspend" button
3. **Required**: Enter reason (free text, min 20 chars)
4. System updates `workspace.status` to `suspended`
5. System sends email notification to workspace owner
6. System creates audit log entry
7. Workspace owner cannot access workspace until unsuspended

**Reversibility:** Yes - Admin can unsuspend workspace

#### Unsuspend Workspace
**When to Use:**
- Issue resolved (payment received, abuse addressed)
- False positive (suspended by mistake)

**Workflow:**
1. Admin reviews suspension reason and current status
2. Admin clicks "Unsuspend" button
3. **Optional**: Add notes explaining resolution
4. System updates `workspace.status` to `active`
5. System creates audit log entry
6. Workspace owner regains access

#### Impersonate Workspace Owner
**When to Use:**
- Customer support (debugging user's issue)
- Testing workspace-specific features
- Investigating reported bugs

**Workflow:**
1. Admin selects workspace
2. Admin clicks "Impersonate Owner"
3. System generates impersonation JWT token
4. Admin uses token to access workspace as owner
5. All actions logged with `actor_type=admin` and `impersonation=true`
6. Token expires after 1 hour (configurable)

**Security:**
- Impersonation tokens are clearly marked
- All actions during impersonation are logged
- Token has shorter expiration than normal tokens

---

### Affiliate Management

#### Approve Affiliate Application
**When to Use:**
- Affiliate application reviewed and approved
- Affiliate meets program requirements

**Workflow:**
1. Admin reviews affiliate application (company, website, intended audience)
2. Admin clicks "Approve"
3. **Optional**: Assign custom commission plan (default: Standard 25%)
4. **Optional**: Add internal notes
5. System updates `affiliate.status` to `approved`
6. System sends approval email to affiliate
7. System creates audit log entry
8. Affiliate gains access to affiliate dashboard

**Business Rules:**
- Can only approve `pending` affiliates
- First 20 affiliates get early access rate (25%, may be discontinued later)
- Commission plan assignment affects future commissions only

#### Reject Affiliate Application
**When to Use:**
- Affiliate doesn't meet program requirements
- Suspicious application (fraud indicators)
- Incomplete application

**Workflow:**
1. Admin reviews affiliate application
2. Admin clicks "Reject"
3. **Required**: Enter rejection reason (free text, min 20 chars)
4. System updates `affiliate.status` to `rejected`
5. System sends rejection email to affiliate (includes reason)
6. System creates audit log entry

**Business Rules:**
- Rejection reason is sent to affiliate (transparency)
- Rejected affiliates cannot reapply (status is permanent)
- Can manually change status to `pending` if rejection was mistake

#### Block Affiliate
**When to Use:**
- Fraud detected (self-referrals, fake signups)
- Terms violation
- High refund rate (>30% of referred customers)

**Workflow:**
1. Admin reviews affiliate performance and fraud indicators
2. Admin clicks "Block"
3. **Required**: Enter blocking reason (free text, min 20 chars)
4. System updates `affiliate.status` to `blocked`
5. System prevents new commissions (existing cleared commissions still payable)
6. System sends notification email to affiliate
7. System creates audit log entry

**Business Rules:**
- Blocked affiliates cannot earn new commissions
- Existing `cleared` commissions remain payable (fairness)
- `pending` commissions can be reversed at admin discretion

#### Manual Commission Adjustment
**When to Use:**
- Bonus commission (promotional, referral bonus)
- Refund adjustment (customer refunded, commission should be reduced)
- Correction (calculation error, missing commission)

**Workflow:**
1. Admin navigates to affiliate's commission list
2. Admin clicks "Adjust Commission" or "Add Commission"
3. **Required**: Enter amount (positive for bonus, negative for reduction)
4. **Required**: Enter reason (free text, min 20 chars)
5. **Optional**: Link to specific subscription/customer
6. System creates commission record with `status=pending`
7. System creates audit log entry with full details
8. Commission follows normal hold period (unless admin clears immediately)

**Business Rules:**
- Positive amounts = bonus/addition
- Negative amounts = reduction/adjustment
- Reason required for audit trail
- Can clear immediately (bypass hold period) if needed

---

### Job Management

#### Reprocess Failed Job
**When to Use:**
- Temporary error resolved (network issue, service outage)
- Template fixed (extraction template updated)
- Root cause identified and fixed

**Workflow:**
1. Admin views failed job details (error message, attempts, payload)
2. Admin investigates root cause (checks logs, template, document)
3. Admin fixes underlying issue (if applicable)
4. Admin clicks "Reprocess Job"
5. **Required**: Enter reason (free text, min 20 chars, e.g., "Template schema fixed", "Network issue resolved")
6. System resets job: `status=queued`, `attempts=0`, clears `last_error`
7. System sets `scheduled_at=now()`
8. System creates audit log entry
9. Worker picks up job and processes

**Business Rules:**
- Can only reprocess `failed` jobs (not `succeeded` or `processing`)
- Reprocessing resets attempt counter (job can fail again)
- Reason required for audit trail
- Should investigate root cause before reprocessing (not just retry blindly)

---

### Document Management

#### Retry Document Extraction
**When to Use:**
- Document failed extraction (template issue, OCR error)
- Template updated and should be re-applied
- Temporary processing error resolved

**Workflow:**
1. Admin views document details (status, extraction results, logs)
2. Admin identifies issue (template mismatch, OCR failure, etc.)
3. Admin fixes underlying issue (if applicable, e.g., updates template)
4. Admin clicks "Retry Extraction"
5. **Required**: Enter reason (free text, min 20 chars)
6. System creates new extraction job
7. System updates document `status=pending`
8. System creates audit log entry
9. Worker processes document with updated template/config

**Business Rules:**
- Creates new job (doesn't modify existing job)
- Reason required for audit trail
- Should fix root cause before retrying (not just retry)

---

### Webhook Management

#### Retry Failed Webhook Delivery
**When to Use:**
- Webhook delivery failed (endpoint down, timeout)
- Endpoint now available
- Temporary network issue resolved

**Workflow:**
1. Admin views failed webhook delivery (error, retry count, payload)
2. Admin verifies endpoint is now available (if possible)
3. Admin clicks "Retry Delivery"
4. **Required**: Enter reason (free text, min 20 chars)
5. System creates new delivery attempt
6. System resets retry count (or increments appropriately)
7. System creates audit log entry
8. Worker attempts delivery

**Business Rules:**
- Respects webhook retry policy (max attempts)
- Reason required for audit trail
- Should verify endpoint availability before retrying

---

### API Key Management

#### Revoke API Key
**When to Use:**
- Security incident (key compromised, leaked)
- Workspace suspended (prevent API access)
- Customer request (key rotation)

**Workflow:**
1. Admin views API key details (prefix, scopes, last used)
2. Admin clicks "Revoke API Key"
3. **Required**: Enter revocation reason (free text, min 20 chars)
4. System updates `api_key.status` to `revoked`
5. System creates audit log entry
6. API key immediately becomes invalid (all requests rejected)
7. Workspace owner receives notification (if not suspended)

**Business Rules:**
- Revocation is permanent (cannot un-revoke)
- Reason required for audit trail
- Workspace owner can create new API key after revocation

---

## Business Rules & Constraints

### General Rules

1. **Audit Trail Requirement**
   - All admin actions that modify data MUST create audit log entry
   - Audit log must include: admin user ID, action type, target entity, reason/notes, timestamp
   - Audit logs are immutable (cannot be modified or deleted)

2. **Reason/Notes Requirement**
   - Critical actions require reason/notes (min 20 characters):
     - Suspend/unsuspend workspace
     - Approve/reject/block affiliate
     - Manual commission adjustment
     - Reprocess job
     - Retry document/webhook
     - Revoke API key
   - Optional actions can have notes:
     - View operations (for tracking)
     - Update internal notes fields

3. **Reversibility**
   - Actions that should be reversible:
     - Suspend workspace → Unsuspend
     - Approve affiliate → Block (if needed)
     - Clear commission → Reverse (if needed)
   - Actions that are NOT reversible:
     - Reject affiliate (can manually change status if mistake)
     - Revoke API key (permanent)
     - Delete operations (soft-delete where possible)

4. **Data Integrity**
   - Cannot modify Stripe data directly (use Stripe dashboard)
   - Cannot modify user passwords (use password reset flow)
   - Cannot delete critical data (use status flags instead)

5. **Access Control**
   - Admin role checked on every admin endpoint
   - Impersonation tokens clearly marked in audit logs
   - Admin actions logged with admin user ID

### Domain-Specific Rules

#### Workspaces
- **Suspend Rule**: Can only suspend `active` workspaces (not already suspended)
- **Unsuspend Rule**: Can only unsuspend `suspended` workspaces
- **Impersonation Rule**: Cannot impersonate if workspace is suspended
- **Status Transitions**: `active` ↔ `suspended` (cannot set to `trial` or `canceled`)

#### Affiliates
- **Status Workflow**: `pending` → `approved` or `rejected` → (can block `approved`)
- **Commission Plan**: Can only assign active commission plans
- **Payout Approval**: Can only approve if affiliate has sufficient cleared balance
- **Block Rule**: Blocked affiliates cannot earn new commissions, but existing cleared commissions remain payable

#### Commissions
- **Status Workflow**: `pending` → `cleared` → `paid` (or `reversed` at any point)
- **Amount Adjustment**: Can only adjust `pending` or `cleared` commissions (not `paid`)
- **Reversal Rule**: Reversed commissions cannot be un-reversed (create new commission if needed)

#### Jobs
- **Reprocess Rule**: Can only reprocess `failed` jobs (not `succeeded`, `processing`, or `queued`)
- **Attempt Limit**: Reprocessing resets attempt counter (job can fail again, respect max attempts)

#### Documents
- **Retry Rule**: Can retry `failed` documents (creates new job)
- **Status Rule**: Cannot manually set status to `completed` (must go through processing)

---

## Audit & Compliance

### Audit Log Requirements

#### What Gets Logged
1. **All Admin CRUD Operations**
   - Create: New admin users, manual commissions
   - Read: Sensitive data access (full user details, payment info)
   - Update: Status changes, adjustments, corrections
   - Delete: (Soft-deletes logged)

2. **All Control Actions**
   - Workspace suspend/unsuspend
   - Affiliate approve/reject/block
   - Commission adjustments
   - Job reprocessing
   - Document retries
   - Webhook retries
   - API key revocations

3. **Access Events**
   - Admin login/logout
   - Impersonation start/end
   - Sensitive data views (full API keys, payment details)

#### Audit Log Fields
- `id`: Unique log entry ID
- `admin_user_id`: Admin who performed action (UUID)
- `action_type`: Type of action (e.g., "workspace_suspend", "affiliate_approve")
- `target_type`: Entity type (e.g., "workspace", "affiliate", "commission")
- `target_id`: Entity ID (UUID)
- `description`: Human-readable description
- `reason`: Reason/notes provided by admin (if required)
- `metadata`: JSON with additional context (old values, new values, etc.)
- `ip_address`: Admin's IP address (hashed for privacy)
- `user_agent`: Admin's user agent (hashed)
- `created_at`: Timestamp

#### Audit Log Retention
- **Minimum Retention**: 1 year
- **Recommended Retention**: 7 years (for compliance)
- **Export Format**: CSV, JSON
- **Search Capabilities**: Filter by admin, action type, target, date range

### Compliance Requirements

1. **GDPR Compliance**
   - Admin access to user data logged
   - Data export capability for user requests
   - Right to be forgotten (soft-delete, anonymize)

2. **SOC 2 Compliance**
   - All admin actions logged
   - Access controls enforced
   - Regular access reviews

3. **Financial Compliance**
   - Commission adjustments logged with reasons
   - Payout approvals logged with payment references
   - Financial data access logged

---

## Security Requirements

### Authentication & Authorization

1. **Admin Authentication**
   - Same JWT-based auth as main app
   - Admin role checked on every request
   - Session timeout: 8 hours (configurable)
   - Impersonation tokens: 1 hour expiration

2. **Authorization**
   - Backend validates `role == "admin"` for all admin endpoints
   - Frontend checks role but backend is source of truth
   - Failed authorization attempts logged

3. **Access Control**
   - Admin app separate from user app (different frontend)
   - Admin endpoints under `/api/admin/*` prefix
   - CORS configured for admin app domain only

### Data Protection

1. **Sensitive Data**
   - Payment details: Only last 4 digits visible, full details masked
   - API keys: Only prefix visible, full key never exposed
   - Passwords: Never visible, cannot be reset by admin (use user flow)

2. **Data Access**
   - Admin access to customer data logged
   - Impersonation clearly marked in audit logs
   - Export capabilities for compliance

3. **Audit Log Security**
   - Audit logs immutable (cannot be modified or deleted)
   - Audit log access restricted to admins only
   - Audit log exports logged

---

## User Interface Requirements

### Navigation Structure

```

Admin App
├── Dashboard (Overview)
│   ├── System Metrics
│   ├── Recent Activity
│   └── Quick Actions
├── Workspaces
│   ├── List (with filters)
│   ├── Detail View
│   └── Suspend/Unsuspend
├── Users
│   ├── List (with filters)
│   ├── Detail View
│   └── Role Management
├── Affiliates
│   ├── Applications (Pending)
│   ├── Active Affiliates
│   ├── Commissions
│   └── Payouts
├── Billing
│   ├── Subscriptions
│   └── Usage Analytics
├── Support
│   ├── Documents
│   ├── Jobs
│   └── Webhooks
└── System
    ├── Audit Logs
    └── Settings

```

### Key UI Components

1. **Data Tables**
   - Pagination (max 100 rows/page)
   - Sorting (all columns)
   - Filtering (status, date range, search)
   - Export (CSV, JSON)

2. **Action Modals**
   - Confirmation dialogs for critical actions
   - Reason/notes input (required fields marked)
   - Preview of changes before confirmation

3. **Audit Trail Display**
   - Timeline view of actions
   - Filter by admin, action type, date
   - Export capability

4. **Dashboard Widgets**
   - System health indicators
   - Recent admin actions
   - Pending approvals (affiliates, payouts)
   - Queue depth and error rates

### Responsive Design
- Desktop-first (admins typically use desktop)
- Mobile support for on-call scenarios
- Tablet support for presentations

---

## Implementation Notes

### Backend Endpoints Already Implemented

The following admin endpoints are already implemented in the backend:

- `/api/admin/workspaces` - List workspaces
- `/api/admin/workspaces/{id}/suspend` - Suspend workspace
- `/api/admin/workspaces/{id}/unsuspend` - Unsuspend workspace
- `/api/admin/workspaces/{id}/impersonate-owner` - Impersonate owner
- `/api/admin/workspaces/{id}/usage-analytics` - Usage analytics
- `/api/admin/workspaces/{id}/abuse-detection` - Abuse detection
- `/api/admin/audit-logs` - List audit logs
- `/api/admin/jobs/{id}/reprocess` - Reprocess job
- `/api/admin/affiliates` - List affiliates (from admin_affiliates.py)
- `/api/admin/affiliates/{id}/approve` - Approve affiliate
- `/api/admin/affiliates/{id}/reject` - Reject affiliate
- `/api/admin/affiliates/{id}/block` - Block affiliate
- `/api/admin/commissions` - List commissions
- `/api/admin/commissions/{id}/adjust` - Adjust commission
- `/api/admin/payouts` - List payouts
- `/api/admin/payouts/{id}/approve` - Approve payout
- `/api/admin/payouts/{id}/reject` - Reject payout

### Missing Endpoints (To Be Implemented)

The following endpoints may need to be added:

- `/api/admin/users` - List users
- `/api/admin/users/{id}` - Get user details
- `/api/admin/users/{id}/update-role` - Update user role
- `/api/admin/subscriptions` - List subscriptions
- `/api/admin/subscriptions/{id}` - Get subscription details
- `/api/admin/documents` - List documents (with filters)
- `/api/admin/documents/{id}/retry` - Retry document extraction
- `/api/admin/templates` - List templates
- `/api/admin/api-keys` - List API keys
- `/api/admin/api-keys/{id}/revoke` - Revoke API key
- `/api/admin/webhooks` - List webhooks
- `/api/admin/webhook-deliveries/{id}/retry` - Retry webhook delivery
- `/api/admin/metrics` - System metrics (may already exist)

---

## Appendix: CRUD Matrix Summary

| Domain | Create | Read | Update | Delete | Special Actions |
|--------|--------|------|--------|--------|-----------------|
| Workspaces | ❌ | ✅ | ⚠️ Limited | ❌ | Suspend, Unsuspend, Impersonate |
| Users | ✅ | ✅ | ⚠️ Limited | ❌ | Update Role, Reset Password |
| Affiliates | ❌ | ✅ | ✅ | ❌ | Approve, Reject, Block |
| Commissions | ✅ | ✅ | ✅ | ❌ | Adjust, Reverse |
| Payouts | ❌ | ✅ | ✅ | ❌ | Approve, Reject, Mark Paid |
| Subscriptions | ❌ | ✅ | ⚠️ Limited | ❌ | View Stripe Dashboard |
| Documents | ❌ | ✅ | ⚠️ Limited | ❌ | Retry Extraction |
| Templates | ❌ | ✅ | ⚠️ Limited | ❌ | View Stats |
| Projects | ❌ | ✅ | ⚠️ Limited | ❌ | View Details |
| API Keys | ❌ | ✅ | ⚠️ Limited | ❌ | Revoke |
| Webhooks | ❌ | ✅ | ⚠️ Limited | ❌ | Retry Delivery |
| Jobs | ❌ | ✅ | ✅ | ❌ | Reprocess |
| System Metrics | ❌ | ✅ | ❌ | ❌ | View Dashboard |
| Audit Logs | ❌ | ✅ | ❌ | ❌ | Export |

**Legend:**
- ✅ Full access
- ⚠️ Limited access (specific fields/actions only)
- ❌ Not allowed

---

**Document End**
```

This document covers:

1. CRUD matrices for all domains
2. Business rules and constraints
3. Correction workflows with step-by-step processes
4. Audit and compliance requirements

Save this as `generated_apps/docdata_saas/docs/admin_app_business_requirements.md`. Should I create any additional supporting documents or refine any sections?
