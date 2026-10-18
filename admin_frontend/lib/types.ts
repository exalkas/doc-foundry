/**
 * TypeScript types for admin app
 */

export interface User {
  id: string;
  email: string;
  full_name?: string;
  role: "admin" | "owner" | "member" | "readonly";
  is_email_verified: boolean;
  workspaces_count?: number;
  last_login?: string;
}

export interface Workspace {
  id: string;
  name: string;
  owner_email?: string;
  plan?: string;
  status: "active" | "suspended" | "trial" | "canceled";
  created_at: string;
  updated_at?: string;
}

// Usage Analytics Types
export interface UsageHistory {
  date: string;
  documents: number;
  pages: number;
}

export interface UsageBreakdown {
  by_project?: Record<string, number>;
  by_template?: Record<string, number>;
  by_source?: Record<string, number>;
}

export interface UsagePeriod {
  start: string;
  end: string;
  usage: {
    total_documents: number;
    total_pages: number;
    by_project?: Record<string, number>;
    by_template?: Record<string, number>;
  };
}

export interface UsageAnalytics {
  workspace_id: string;
  current_period: UsagePeriod;
  breakdown: UsageBreakdown;
  history: UsageHistory[];
}

// Abuse Detection Types
export interface Violation {
  type: string;
  severity: "low" | "medium" | "high";
  description: string;
  threshold?: number;
  usage?: number;
  limit?: number;
}

export interface AbuseDetection {
  workspace_id: string;
  violations: Violation[];
  risk_score: number;
  recommendations: string[];
}

// Affiliate Types
export interface AffiliateStats {
  total_clicks: number;
  total_signups: number;
  paying_customers: number;
  total_earned: number;
  pending_earned: number;
  cleared_earned: number;
  paid_earned: number;
  mrr_generated: number;
}

export interface Affiliate {
  id: string;
  user_id: string;
  user_email: string;
  slug: string;
  status: "pending" | "approved" | "rejected" | "blocked";
  commission_plan_id: string;
  company_name?: string;
  website?: string;
  payment_method_type?: string;
  country?: string;
  tax_id?: string;
  notes?: string;
  created_at: string;
  updated_at?: string;
  stats?: AffiliateStats;
}

// Commission Types
export interface Commission {
  id: string;
  affiliate_id: string;
  customer_id: string;
  subscription_id: string;
  event_type: "initial" | "recurring" | "upgrade" | "downgrade";
  amount: number;
  currency: string;
  status: "pending" | "cleared" | "paid" | "reversed";
  event_date: string;
  cleared_at?: string;
  notes?: string;
}

// Payout Types
export interface Payout {
  id: string;
  affiliate_id: string;
  amount: number;
  currency: string;
  status: "requested" | "approved" | "paid" | "rejected";
  requested_at: string;
  processed_at?: string;
  payment_method?: string;
  payment_reference?: string;
  notes?: string;
}

// Coupon Types
export interface Coupon {
  id: string;
  code: string;
  discount_type: "percentage" | "fixed";
  discount_value: number;
  duration_type: "once" | "first_n_months" | "until_date";
  duration_months?: number;
  expires_at?: string;
  max_redemptions?: number;
  max_redemptions_per_customer: number;
  eligible_plans: string[];
  affiliate_id?: string;
  affiliate_name?: string;
  status: "active" | "paused" | "expired";
  stackable: boolean;
  allow_lifetime_discount: boolean;
  metadata_json: Record<string, any>;
  redemption_count: number;
  created_at: string;
  updated_at: string;
}

export interface CouponRedemption {
  id: string;
  coupon_id: string;
  coupon_code: string;
  customer_id: string;
  customer_email?: string;
  subscription_id?: string;
  used_at: string;
  discount_applied: number;
}

// System Types
export interface SystemMetrics {
  queue_depth?: number;
  avg_processing_time?: number;
  daily_docs_processed?: number;
  errors_last_24h?: number;
}

export interface ApiErrorResponse {
  detail: string;
  code?: string;
}

// Pagination Types
export interface PaginationParams {
  page?: number;
  page_size?: number;
}

/**
 * Paginated API response wrapper
 *
 * Note: Backend API must return responses in this format for pagination to work.
 * If backend doesn't support this yet, the hooks will handle both formats.
 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// Phase 3: Support Features Types

// Document Types
export type DocumentStatus = "queued" | "processing" | "completed" | "failed";

export interface Document {
  id: string;
  workspace_id: string;
  workspace_name?: string;
  project_id?: string;
  project_name?: string;
  name: string;
  status: DocumentStatus;
  file_name?: string;
  file_size?: number;
  file_type?: string;
  template_id?: string;
  template_name?: string;
  created_at: string;
  updated_at?: string;
  completed_at?: string;
  extraction_results?: Record<string, any>;
  error_message?: string;
}

// Job Types
export type JobType =
  | "document_extraction"
  | "webhook_delivery"
  | "email_send"
  | "other";
export type JobStatus = "queued" | "processing" | "completed" | "failed";

export interface Job {
  id: string;
  type: JobType;
  status: JobStatus;
  attempts: number;
  max_attempts?: number;
  error?: string;
  error_details?: Record<string, any>;
  created_at: string;
  updated_at?: string;
  scheduled_at?: string;
  started_at?: string;
  completed_at?: string;
  workspace_id?: string;
  document_id?: string;
  webhook_id?: string;
}

// Webhook Types
export type WebhookStatus = "active" | "inactive" | "failed";

export interface Webhook {
  id: string;
  workspace_id: string;
  workspace_name?: string;
  url: string;
  events: string[];
  status: WebhookStatus;
  secret?: string;
  last_delivery?: string;
  last_delivery_status?: string;
  created_at: string;
  updated_at?: string;
}

export type WebhookDeliveryStatus = "pending" | "success" | "failed";

export interface WebhookDelivery {
  id: string;
  webhook_id: string;
  webhook_url?: string;
  event_type: string;
  status: WebhookDeliveryStatus;
  status_code?: number;
  attempt_count: number;
  max_attempts?: number;
  last_error?: string;
  payload?: Record<string, any>;
  response_body?: string;
  created_at: string;
  updated_at?: string;
  delivered_at?: string;
}

// Subscription Types
export type SubscriptionStatus =
  | "active"
  | "canceled"
  | "past_due"
  | "trialing"
  | "incomplete"
  | "incomplete_expired";
export type BillingPeriod = "month" | "year";

export interface Subscription {
  id: string;
  user_id: string;
  user_email?: string;
  workspace_id?: string;
  workspace_name?: string;
  plan: string;
  status: SubscriptionStatus;
  billing_period: BillingPeriod;
  amount: number;
  currency: string;
  stripe_subscription_id?: string;
  stripe_customer_id?: string;
  current_period_start?: string;
  current_period_end?: string;
  cancel_at_period_end?: boolean;
  canceled_at?: string;
  created_at: string;
  updated_at?: string;
  billing_history?: BillingHistoryItem[];
  usage_vs_limits?: UsageVsLimits;
}

export interface BillingHistoryItem {
  id: string;
  amount: number;
  currency: string;
  status: "paid" | "pending" | "failed";
  invoice_url?: string;
  created_at: string;
}

export interface UsageVsLimits {
  documents_used: number;
  documents_limit: number;
  pages_used: number;
  pages_limit: number;
  projects_used?: number;
  projects_limit?: number;
}

// API Key Types
export type ApiKeyStatus = "active" | "revoked";

export interface ApiKey {
  id: string;
  workspace_id: string;
  workspace_name?: string;
  name: string;
  prefix: string;
  scopes: string[];
  status: ApiKeyStatus;
  last_used?: string;
  expires_at?: string;
  created_at: string;
  updated_at?: string;
}
