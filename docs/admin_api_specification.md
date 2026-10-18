# Admin API Specification

**Version:** 1.0  
**Date:** 2024  
**Status:** Draft  
**Project:** DocFoundry Admin Platform

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Base URL & Versioning](#base-url--versioning)
4. [Common Patterns](#common-patterns)
5. [Endpoints by Domain](#endpoints-by-domain)
6. [Error Responses](#error-responses)
7. [Rate Limiting](#rate-limiting)

---

## Overview

This document specifies the REST API endpoints available to administrators for managing the DocFoundry platform. All endpoints require admin authentication and are prefixed with `/api/admin`.

### API Design Principles

- **RESTful**: Follow REST conventions (GET for read, POST for actions, etc.)
- **Consistent**: Uniform request/response formats across all endpoints
- **Secure**: All endpoints require admin role verification
- **Audited**: All admin actions are logged for compliance

---

## Authentication

### Authentication Method

All admin endpoints require JWT-based authentication via HTTP-only cookies, same as the main application.

### Authorization

- **Required Role**: `admin` (stored in `users.role`)
- **Validation**: Backend validates `role == "admin"` on every request
- **Dependency**: Uses `require_global_admin` FastAPI dependency

### Authentication Flow

1. Admin logs in via `/api/auth/login` (same endpoint as regular users)
2. Backend sets HTTP-only cookie with JWT token
3. Admin app includes cookie in all requests
4. Backend validates token and checks `role == "admin"`

### Impersonation Tokens

Some endpoints return impersonation tokens for accessing workspaces as the owner:

- Token type: `TokenType.IMPERSONATION`
- Expiration: 1 hour (configurable)
- Usage: Use token to access main app as workspace owner
- Audit: All actions during impersonation are logged with `impersonation=true`

---

## Base URL & Versioning

- **Base URL**: `/api/admin`
- **Versioning**: No versioning currently (future: `/api/admin/v1`)
- **Content-Type**: `application/json` for requests and responses
- **Accept**: `application/json`

---

## Common Patterns

### Pagination

Most list endpoints support pagination:

**Query Parameters:**

- `page` (integer, default: 1, min: 1): Page number
- `page_size` (integer, default: 50, min: 1, max: 100): Items per page

**Response Format:**

```json
[
  { /* item 1 */ },
  { /* item 2 */ },
  ...
]
```

**Note**: Total count and pagination metadata may be added in future versions.

### Filtering

Many endpoints support filtering via query parameters:

- `status` (string): Filter by status enum value
- `from` (datetime, ISO 8601): Start date for date range filters
- `to` (datetime, ISO 8601): End date for date range filters
- `workspace_id` (UUID): Filter by workspace
- `affiliate_id` (UUID): Filter by affiliate

### Sorting

- Default: Most endpoints sort by `created_at DESC` (newest first)
- Custom sorting may be added in future versions

### Date Formats

All dates are in ISO 8601 format with timezone:

- Format: `YYYY-MM-DDTHH:mm:ss.sssZ`
- Example: `2024-01-15T10:30:00.000Z`

### UUID Formats

All UUIDs are in standard format:

- Format: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
- Example: `550e8400-e29b-41d4-a716-446655440000`

---

## Endpoints by Domain

### Workspaces

#### List Workspaces

**Endpoint:** `GET /api/admin/workspaces`

**Description:** List all workspaces with optional filtering and pagination.

**Query Parameters:**

- `status` (optional, string): Filter by workspace status (`active`, `suspended`, `trial`, `canceled`)
- `page` (optional, integer, default: 1): Page number
- `page_size` (optional, integer, default: 50, max: 100): Items per page

**Response:** `200 OK`

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Acme Corp",
    "status": "active",
    "created_at": "2024-01-15T10:30:00.000Z",
    "updated_at": "2024-01-20T14:22:00.000Z"
  }
]
```

**Error Responses:**

- `400 Bad Request`: Invalid status filter
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Not an admin
- `500 Internal Server Error`: Server error

---

#### Suspend Workspace

**Endpoint:** `POST /api/admin/workspaces/{workspace_id}/suspend`

**Description:** Suspend a workspace (prevents access, sends notification to owner).

**Path Parameters:**

- `workspace_id` (UUID): Workspace ID

**Query Parameters:**

- `reason` (optional, string): Reason for suspension (min 20 chars recommended)

**Response:** `200 OK`

```json
{
  "workspace_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "suspended",
  "message": "Workspace suspended. Reason: Payment issue"
}
```

**Error Responses:**

- `400 Bad Request`: Workspace already suspended
- `404 Not Found`: Workspace not found
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Not an admin
- `500 Internal Server Error`: Server error

**Business Rules:**

- Can only suspend `active` workspaces
- Sends email notification to workspace owner
- Creates audit log entry

---

#### Unsuspend Workspace

**Endpoint:** `POST /api/admin/workspaces/{workspace_id}/unsuspend`

**Description:** Restore a suspended workspace to active status.

**Path Parameters:**

- `workspace_id` (UUID): Workspace ID

**Response:** `200 OK`

```json
{
  "workspace_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "active",
  "message": "Workspace unsuspended successfully"
}
```

**Error Responses:**

- `400 Bad Request`: Workspace is not suspended
- `404 Not Found`: Workspace not found
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Not an admin
- `500 Internal Server Error`: Server error

**Business Rules:**

- Can only unsuspend `suspended` workspaces
- Creates audit log entry

---

#### Impersonate Workspace Owner

**Endpoint:** `POST /api/admin/workspaces/{workspace_id}/impersonate-owner`

**Description:** Generate an impersonation token to access workspace as owner.

**Path Parameters:**

- `workspace_id` (UUID): Workspace ID

**Response:** `200 OK`

```json
{
    "token": "EXAMPLE_TOKEN",
}
```

**Error Responses:**

- `404 Not Found`: Workspace not found or no active owner
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Not an admin
- `500 Internal Server Error`: Server error

**Business Rules:**

- Token expires in 1 hour
- All actions during impersonation are logged with `impersonation=true`
- Use token to access main app (not admin app)

---

#### Get Workspace Usage Analytics

**Endpoint:** `GET /api/admin/workspaces/{workspace_id}/usage-analytics`

**Description:** Get detailed usage analytics for a workspace.

**Path Parameters:**

- `workspace_id` (UUID): Workspace ID

**Query Parameters:**

- `days` (optional, integer, default: 90, min: 1, max: 365): Number of days for history

**Response:** `200 OK`

```json
{
  "workspace_id": "550e8400-e29b-41d4-a716-446655440000",
  "current_period": {
    "start": "2024-01-01T00:00:00.000Z",
    "end": "2024-02-01T00:00:00.000Z",
    "usage": {
      "total_documents": 150,
      "total_pages": 450,
      "by_project": {
        /* breakdown */
      },
      "by_template": {
        /* breakdown */
      }
    }
  },
  "breakdown": {
    "by_project": {
      /* project breakdown */
    },
    "by_template": {
      /* template breakdown */
    },
    "by_source": {
      /* UI vs API breakdown */
    }
  },
  "history": [
    {
      "date": "2024-01-15",
      "documents": 10,
      "pages": 30
    }
  ]
}
```

**Error Responses:**

- `404 Not Found`: Workspace not found
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Not an admin
- `500 Internal Server Error`: Server error

---

#### Detect Workspace Abuse

**Endpoint:** `GET /api/admin/workspaces/{workspace_id}/abuse-detection`

**Description:** Check for abuse patterns in a workspace (rapid usage spikes, quota abuse).

**Path Parameters:**

- `workspace_id` (UUID): Workspace ID

**Response:** `200 OK`

```json
{
  "workspace_id": "550e8400-e29b-41d4-a716-446655440000",
  "violations": [
    {
      "type": "rapid_usage_spike",
      "severity": "high",
      "description": "150 documents uploaded in the last hour",
      "threshold": 100
    },
    {
      "type": "quota_abuse",
      "severity": "medium",
      "description": "Using 98% of monthly quota",
      "usage": 9800,
      "limit": 10000
    }
  ],
  "risk_score": 0.5,
  "recommendations": [
    "Consider suspending workspace for review",
    "Monitor workspace activity closely"
  ]
}
```

**Error Responses:**

- `404 Not Found`: Workspace not found
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Not an admin
- `500 Internal Server Error`: Server error

---

### Affiliates

#### List Affiliates

**Endpoint:** `GET /api/admin/affiliates`

**Description:** List all affiliates with optional filtering and pagination.

**Query Parameters:**

- `status` (optional, string): Filter by status (`pending`, `approved`, `rejected`, `blocked`)
- `page` (optional, integer, default: 1): Page number
- `page_size` (optional, integer, default: 50, max: 100): Items per page

**Response:** `200 OK`

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "660e8400-e29b-41d4-a716-446655440001",
    "user_email": "affiliate@example.com",
    "slug": "john-doe",
    "status": "approved",
    "commission_plan_id": "770e8400-e29b-41d4-a716-446655440002",
    "company_name": "John's Agency",
    "website": "https://example.com",
    "payment_method_type": "paypal",
    "country": "US",
    "tax_id": "12-3456789",
    "notes": "High-performing affiliate",
    "created_at": "2024-01-15T10:30:00.000Z",
    "updated_at": "2024-01-20T14:22:00.000Z",
    "stats": {
      "total_clicks": 1500,
      "total_signups": 45,
      "paying_customers": 12,
      "total_earned": 1250.5,
      "pending_earned": 150.0,
      "cleared_earned": 800.0,
      "paid_earned": 300.5,
      "mrr_generated": 450.0
    }
  }
]
```

**Error Responses:**

- `400 Bad Request`: Invalid status filter
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Not an admin
- `500 Internal Server Error`: Server error

---

#### Get Affiliate Details

**Endpoint:** `GET /api/admin/affiliates/{affiliate_id}`

**Description:** Get detailed information about a specific affiliate.

**Path Parameters:**

- `affiliate_id` (UUID): Affiliate ID

**Response:** `200 OK`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "660e8400-e29b-41d4-a716-446655440001",
  "user_email": "affiliate@example.com",
  "slug": "john-doe",
  "status": "approved",
  "commission_plan_id": "770e8400-e29b-41d4-a716-446655440002",
  "company_name": "John's Agency",
  "website": "https://example.com",
  "payment_method_type": "paypal",
  "country": "US",
  "tax_id": "12-3456789",
  "notes": "High-performing affiliate",
  "created_at": "2024-01-15T10:30:00.000Z",
  "updated_at": "2024-01-20T14:22:00.000Z",
  "stats": {
    "total_clicks": 1500,
    "total_signups": 45,
    "paying_customers": 12,
    "total_earned": 1250.5,
    "pending_earned": 150.0,
    "cleared_earned": 800.0,
    "paid_earned": 300.5,
    "mrr_generated": 450.0
  }
}
```

**Error Responses:**

- `404 Not Found`: Affiliate not found
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Not an admin
- `500 Internal Server Error`: Server error

---

#### Approve Affiliate

**Endpoint:** `POST /api/admin/affiliates/{affiliate_id}/approve`

**Description:** Approve an affiliate application.

**Path Parameters:**

- `affiliate_id` (UUID): Affiliate ID

**Request Body:**

```json
{
  "notes": "Approved - meets all requirements"
}
```

**Response:** `200 OK`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "660e8400-e29b-41d4-a716-446655440001",
  "user_email": "affiliate@example.com",
  "slug": "john-doe",
  "status": "approved",
  "commission_plan_id": "770e8400-e29b-41d4-a716-446655440002",
  "company_name": "John's Agency",
  "website": "https://example.com",
  "payment_method_type": "paypal",
  "country": "US",
  "tax_id": "12-3456789",
  "notes": "Approved - meets all requirements",
  "created_at": "2024-01-15T10:30:00.000Z",
  "updated_at": "2024-01-20T14:22:00.000Z",
  "stats": {
    /* stats object */
  }
}
```

**Error Responses:**

- `400 Bad Request`: Invalid affiliate status (not pending)
- `404 Not Found`: Affiliate not found
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Not an admin
- `500 Internal Server Error`: Server error

**Business Rules:**

- Can only approve `pending` affiliates
- Sends approval email to affiliate
- Creates audit log entry

---

#### Reject Affiliate

**Endpoint:** `POST /api/admin/affiliates/{affiliate_id}/reject`

**Description:** Reject an affiliate application.

**Path Parameters:**

- `affiliate_id` (UUID): Affiliate ID

**Request Body:**

```json
{
  "notes": "Does not meet program requirements"
}
```

**Response:** `200 OK`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "rejected",
  "notes": "Does not meet program requirements"
  /* ... other fields ... */
}
```

**Error Responses:**

- `400 Bad Request`: Invalid affiliate status (not pending)
- `404 Not Found`: Affiliate not found
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Not an admin
- `500 Internal Server Error`: Server error

**Business Rules:**

- Can only reject `pending` affiliates
- Sends rejection email to affiliate (includes notes)
- Creates audit log entry

---

#### Block Affiliate

**Endpoint:** `POST /api/admin/affiliates/{affiliate_id}/block`

**Description:** Block an affiliate (prevents new commissions, existing cleared commissions remain payable).

**Path Parameters:**

- `affiliate_id` (UUID): Affiliate ID

**Request Body:**

```json
{
  "notes": "Fraud detected - self-referrals"
}
```

**Response:** `200 OK`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "blocked",
  "notes": "Fraud detected - self-referrals"
  /* ... other fields ... */
}
```

**Error Responses:**

- `400 Bad Request`: Invalid affiliate status
- `404 Not Found`: Affiliate not found
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Not an admin
- `500 Internal Server Error`: Server error

**Business Rules:**

- Can block `approved` affiliates
- Prevents new commissions
- Existing `cleared` commissions remain payable
- Creates audit log entry

---

### Commissions

#### List All Commissions

**Endpoint:** `GET /api/admin/affiliates/commissions/list`

**Description:** List all commissions across all affiliates with optional filtering.

**Query Parameters:**

- `affiliate_id` (optional, UUID): Filter by affiliate
- `status` (optional, string): Filter by status (`pending`, `cleared`, `paid`, `reversed`)
- `page` (optional, integer, default: 1): Page number
- `page_size` (optional, integer, default: 50, max: 100): Items per page

**Response:** `200 OK`

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "affiliate_id": "660e8400-e29b-41d4-a716-446655440001",
    "customer_id": "770e8400-e29b-41d4-a716-446655440002",
    "subscription_id": "880e8400-e29b-41d4-a716-446655440003",
    "event_type": "initial",
    "amount": 25.5,
    "currency": "EUR",
    "status": "cleared",
    "event_date": "2024-01-15T10:30:00.000Z",
    "cleared_at": "2024-02-15T10:30:00.000Z",
    "notes": "Initial subscription commission"
  }
]
```

**Error Responses:**

- `400 Bad Request`: Invalid status filter
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Not an admin
- `500 Internal Server Error`: Server error

---

#### Adjust Commission

**Endpoint:** `POST /api/admin/affiliates/commissions/{commission_id}/adjust`

**Description:** Manually adjust a commission amount (for corrections or bonuses).

**Path Parameters:**

- `commission_id` (UUID): Commission ID

**Request Body:**

```json
{
  "amount": 30.0,
  "reason": "Bonus commission for promotional campaign"
}
```

**Response:** `200 OK`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "amount": 30.0,
  "currency": "EUR",
  "notes": "[Admin Adjustment] Bonus commission for promotional campaign (was 25.50)"
}
```

**Error Responses:**

- `400 Bad Request`: Cannot adjust paid commissions
- `404 Not Found`: Commission not found
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Not an admin
- `500 Internal Server Error`: Server error

**Business Rules:**

- Can only adjust `pending` or `cleared` commissions (not `paid`)
- Reason required (min 20 chars)
- Creates audit log entry with old and new amounts

---

### Payouts

#### List All Payouts

**Endpoint:** `GET /api/admin/affiliates/payouts/list`

**Description:** List all payout requests across all affiliates.

**Query Parameters:**

- `status` (optional, string): Filter by status (`requested`, `approved`, `paid`, `rejected`)
- `page` (optional, integer, default: 1): Page number
- `page_size` (optional, integer, default: 50, max: 100): Items per page

**Response:** `200 OK`

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "affiliate_id": "660e8400-e29b-41d4-a716-446655440001",
    "amount": 500.0,
    "currency": "EUR",
    "status": "requested",
    "requested_at": "2024-01-15T10:30:00.000Z",
    "processed_at": null,
    "payment_method": "paypal",
    "payment_reference": null,
    "notes": null
  }
]
```

**Error Responses:**

- `400 Bad Request`: Invalid status filter
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Not an admin
- `500 Internal Server Error`: Server error

---

#### Approve Payout

**Endpoint:** `POST /api/admin/affiliates/payouts/{payout_id}/approve`

**Description:** Approve a payout request (marks commissions as paid, ready for external payment).

**Path Parameters:**

- `payout_id` (UUID): Payout ID

**Request Body:**

```json
{
  "payment_reference": "PAY-123456789",
  "notes": "Approved for payment via PayPal"
}
```

**Response:** `200 OK`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "approved",
  "processed_at": "2024-01-20T14:22:00.000Z"
}
```

**Error Responses:**

- `400 Bad Request`: Insufficient cleared commissions or payout not in requested status
- `404 Not Found`: Payout not found
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Not an admin
- `500 Internal Server Error`: Server error

**Business Rules:**

- Can only approve `requested` payouts
- Validates sufficient cleared commissions available
- Marks related commissions as `paid`
- Creates audit log entry

---

#### Mark Payout as Paid

**Endpoint:** `POST /api/admin/affiliates/payouts/{payout_id}/pay`

**Description:** Mark an approved payout as paid (after external payment completed).

**Path Parameters:**

- `payout_id` (UUID): Payout ID

**Request Body:**

```json
{
  "payment_reference": "PAY-123456789",
  "notes": "Payment completed via PayPal"
}
```

**Response:** `200 OK`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "paid",
  "processed_at": "2024-01-20T14:22:00.000Z"
}
```

**Error Responses:**

- `400 Bad Request`: Payout must be approved before marking as paid
- `404 Not Found`: Payout not found
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Not an admin
- `500 Internal Server Error`: Server error

**Business Rules:**

- Can only mark `approved` payouts as paid
- Payment reference should be transaction ID from payment provider
- Creates audit log entry

---

#### Reject Payout

**Endpoint:** `POST /api/admin/affiliates/payouts/{payout_id}/reject`

**Description:** Reject a payout request (returns commissions to cleared status).

**Path Parameters:**

- `payout_id` (UUID): Payout ID

**Request Body:**

```json
{
  "reason": "Insufficient documentation"
}
```

**Response:** `200 OK`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "rejected",
  "processed_at": "2024-01-20T14:22:00.000Z"
}
```

**Error Responses:**

- `400 Bad Request`: Payout not in requested status
- `404 Not Found`: Payout not found
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Not an admin
- `500 Internal Server Error`: Server error

**Business Rules:**

- Can only reject `requested` payouts
- Reason required (min 20 chars)
- Returns commissions to `cleared` status
- Creates audit log entry

---

### Jobs

#### Reprocess Job

**Endpoint:** `POST /api/admin/jobs/{job_id}/reprocess`

**Description:** Manually reprocess a failed job (resets status to queued).

**Path Parameters:**

- `job_id` (UUID): Job ID

**Response:** `200 OK`

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Job queued for reprocessing",
  "status": "queued"
}
```

**Error Responses:**

- `404 Not Found`: Job not found
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Not an admin
- `500 Internal Server Error`: Server error

**Business Rules:**

- Can only reprocess `failed` jobs
- Resets `attempts` to 0
- Clears `last_error`
- Sets `scheduled_at` to now
- Creates audit log entry (reason should be logged separately)

**Note**: Reason for reprocessing should be logged via audit log system, not in request body.

---

### Audit Logs

#### List Audit Logs

**Endpoint:** `GET /api/admin/audit-logs`

**Description:** List audit logs across all workspaces with optional filtering.

**Query Parameters:**

- `workspace_id` (optional, UUID): Filter by workspace
- `actor_type` (optional, string): Filter by actor type (`user`, `system`, `admin`)
- `from` (optional, datetime, ISO 8601): Start date
- `to` (optional, datetime, ISO 8601): End date
- `page` (optional, integer, default: 1): Page number
- `page_size` (optional, integer, default: 50, max: 100): Items per page

**Response:** `200 OK`

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "workspace_id": "660e8400-e29b-41d4-a716-446655440001",
    "user_id": "770e8400-e29b-41d4-a716-446655440002",
    "actor_type": "admin",
    "event_type": "workspace_suspend",
    "description": "Workspace suspended by admin",
    "metadata": {
      "workspace_id": "660e8400-e29b-41d4-a716-446655440001",
      "reason": "Payment issue",
      "admin_user_id": "770e8400-e29b-41d4-a716-446655440002"
    },
    "created_at": "2024-01-15T10:30:00.000Z"
  }
]
```

**Error Responses:**

- `400 Bad Request`: Invalid actor_type filter
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Not an admin
- `500 Internal Server Error`: Server error

---

## Error Responses

### Standard Error Format

All error responses follow this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

### HTTP Status Codes

- `200 OK`: Request succeeded
- `400 Bad Request`: Invalid request parameters or business rule violation
- `401 Unauthorized`: Not authenticated (missing or invalid token)
- `403 Forbidden`: Authenticated but not authorized (not an admin)
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error
- `503 Service Unavailable`: Database connection error or service unavailable

### Common Error Scenarios

#### 400 Bad Request Examples

```json
{
  "detail": "Invalid status: invalid_status_value"
}
```

```json
{
  "detail": "Workspace is already suspended"
}
```

```json
{
  "detail": "Insufficient cleared commissions. Available: 100.00 EUR"
}
```

#### 401 Unauthorized

```json
{
  "detail": "Not authenticated"
}
```

#### 403 Forbidden

```json
{
  "detail": "Admin access required"
}
```

#### 404 Not Found

```json
{
  "detail": "Workspace not found"
}
```

#### 500 Internal Server Error

```json
{
  "detail": "An error occurred"
}
```

#### 503 Service Unavailable

```json
{
  "detail": "Database connection failed"
}
```

---

## Rate Limiting

### Current Limits

- **Rate Limit**: Not currently implemented (may be added in future)
- **Recommended**: 100 requests per minute per admin user

### Rate Limit Headers (Future)

When rate limiting is implemented, responses will include:

- `X-RateLimit-Limit`: Maximum requests per window
- `X-RateLimit-Remaining`: Remaining requests in current window
- `X-RateLimit-Reset`: Unix timestamp when window resets

### Rate Limit Exceeded Response

```json
{
  "detail": "Rate limit exceeded. Please try again later."
}
```

Status Code: `429 Too Many Requests`

---

## Missing Endpoints (To Be Implemented)

The following endpoints are mentioned in the business requirements but not yet implemented in the backend:

### Users

- `GET /api/admin/users` - List all users
- `GET /api/admin/users/{user_id}` - Get user details
- `PATCH /api/admin/users/{user_id}/role` - Update user role

### Subscriptions

- `GET /api/admin/subscriptions` - List all subscriptions
- `GET /api/admin/subscriptions/{subscription_id}` - Get subscription details

### Documents

- `GET /api/admin/documents` - List all documents (with filters)
- `GET /api/admin/documents/{document_id}` - Get document details
- `POST /api/admin/documents/{document_id}/retry` - Retry document extraction

### Templates

- `GET /api/admin/templates` - List all templates
- `GET /api/admin/templates/{template_id}` - Get template details

### API Keys

- `GET /api/admin/api-keys` - List all API keys
- `POST /api/admin/api-keys/{api_key_id}/revoke` - Revoke API key

### Webhooks

- `GET /api/admin/webhooks` - List all webhooks
- `GET /api/admin/webhook-deliveries/{delivery_id}/retry` - Retry webhook delivery

### System Metrics

- `GET /api/admin/metrics` - Get system metrics (queue depth, processing stats, etc.)

---

## Appendix: Request/Response Examples

### Complete Workflow Example: Suspend Workspace

**1. List workspaces to find target:**

```http
GET /api/admin/workspaces?status=active&page=1&page_size=50
```

**2. Check for abuse:**

```http
GET /api/admin/workspaces/550e8400-e29b-41d4-a716-446655440000/abuse-detection
```

**3. Suspend workspace:**

```http
POST /api/admin/workspaces/550e8400-e29b-41d4-a716-446655440000/suspend?reason=Payment%20issue%20-%20chargeback%20detected
```

**4. Verify suspension:**

```http
GET /api/admin/workspaces/550e8400-e29b-41d4-a716-446655440000
```

---

### Complete Workflow Example: Approve Affiliate & Process Payout

**1. List pending affiliates:**

```http
GET /api/admin/affiliates?status=pending
```

**2. Review affiliate details:**

```http
GET /api/admin/affiliates/550e8400-e29b-41d4-a716-446655440000
```

**3. Approve affiliate:**

```http
POST /api/admin/affiliates/550e8400-e29b-41d4-a716-446655440000/approve
Content-Type: application/json

{
  "notes": "Approved - meets all requirements"
}
```

**4. Later: List payout requests:**

```http
GET /api/admin/affiliates/payouts/list?status=requested
```

**5. Approve payout:**

```http
POST /api/admin/affiliates/payouts/660e8400-e29b-41d4-a716-446655440001/approve
Content-Type: application/json

{
  "payment_reference": "PAY-123456789",
  "notes": "Approved for PayPal payment"
}
```

**6. After external payment: Mark as paid:**

```http
POST /api/admin/affiliates/payouts/660e8400-e29b-41d4-a716-446655440001/pay
Content-Type: application/json

{
  "payment_reference": "PAY-123456789",
  "notes": "Payment completed via PayPal"
}
```

---

**Document End**
