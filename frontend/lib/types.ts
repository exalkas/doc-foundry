/**
 * TypeScript types matching backend models
 */

export interface Project {
  id: string;
  workspace_id: string;
  name: string;
  description?: string;
  created_by_user_id: string;
  created_at: string;
  updated_at: string;
}

export interface Template {
  id: string;
  workspace_id: string;
  project_id?: string;
  name: string;
  description?: string;
  document_type?: string;
  field_schema: Record<string, any>;
  default_export_format: "json" | "csv" | "excel";
  created_by_user_id: string;
  last_run_at?: string;
  success_count: number;
  failure_count: number;
  created_at: string;
  updated_at: string;
  library_template_id?: string;
}

export interface LibraryTemplate {
  id: string;
  name: string;
  description?: string;
  category: string;
  document_type?: string;
  field_schema: Record<string, any>;
  default_export_format: "json" | "csv" | "excel";
  preview_image_url?: string;
  tags?: string[];
  usage_count: number;
  created_at: string;
  updated_at: string;
}

export interface Document {
  id: string;
  workspace_id: string;
  project_id?: string;
  template_id?: string;
  file_name: string;
  file_type: string;
  storage_path: string;
  pages?: number;
  status: "pending" | "processing" | "scanned" | "completed" | "failed";
  uploaded_by_user_id: string;
  source: "ui" | "api";
  created_at: string;
  updated_at: string;
  last_error?: string;
  raw_ocr_text?: string;
  raw_ocr_metadata?: Record<string, any>;
  ocr_language?: string;
}

export interface ExtractionResult {
  id: string;
  document_id: string;
  template_id: string;
  workspace_id: string;
  extracted_json: Record<string, any>;
  version: number;
  metadata?: {
    needs_review?: boolean;
    confidence?: number;
    field_confidences?: Record<string, number>;
    errors?: string[];
    warnings?: string[];
    engine?: string;
  };
  created_at: string;
}

export interface ExtractionLog {
  id: string;
  document_id: string;
  level: "info" | "warning" | "error";
  message: string;
  metadata?: Record<string, any>;
  created_at: string;
}

export interface ApiKey {
  id: string;
  workspace_id: string;
  name: string;
  prefix: string;
  scopes: string[];
  status: "active" | "revoked";
  expires_at?: string;
  last_used_at?: string;
  created_at: string;
}

export interface WebhookConfig {
  id: string;
  workspace_id: string;
  target_url: string;
  secret: string;
  events: string[];
  retry_policy: Record<string, any>;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface UsageRecord {
  id: string;
  workspace_id: string;
  date: string;
  documents_processed: number;
  pages_processed: number;
  created_at: string;
}

export interface Subscription {
  id: string;
  workspace_id: string;
  stripe_subscription_id: string;
  plan_id: string;
  status: "active" | "past_due" | "canceled" | "trialing";
  current_period_start: string;
  current_period_end: string;
  cancel_at_period_end: boolean;
  created_at: string;
  updated_at: string;
}

export interface WebhookDelivery {
  id: string;
  webhook_config_id: string;
  event_type: string;
  payload: Record<string, any>;
  delivery_status: "pending" | "succeeded" | "failed";
  response_status?: number;
  response_body?: string;
  created_at: string;
  delivered_at?: string;
}

export interface PaginationMeta {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface PaginatedDocumentsResponse {
  documents: Document[];
  pagination: PaginationMeta;
}

export interface OCRBlock {
  text: string;
  bbox: [number, number, number, number]; // [x, y, width, height]
  confidence: number;
  page: number;
}

export interface ExtractionMetadata {
  engine: string;
  confidence: number;
  page_count?: number;
  blocks?: OCRBlock[];
}

// Affiliate Types
export interface Affiliate {
  id: string;
  slug: string;
  status: "pending" | "approved" | "rejected" | "blocked";
  company_name?: string;
  website?: string;
  country?: string;
  created_at: string;
}

export interface AffiliateStats {
  affiliate_id: string;
  status: string;
  total_clicks: number;
  total_signups: number;
  paying_customers: number;
  total_earned: number;
  pending_earned: number;
  cleared_earned: number;
  paid_earned: number;
  mrr_generated: number;
}

export interface AffiliateLink {
  id: string;
  slug: string;
  destination_url: string;
  campaign_id?: string;
  created_at: string;
}

export interface Commission {
  id: string;
  customer_id: string;
  subscription_id?: string;
  event_type: string;
  amount: number;
  currency: string;
  status: string;
  event_date: string;
  cleared_at?: string;
}

export interface Customer {
  customer_id: string;
  email: string;
  plan_id?: string;
  status?: string;
  signup_date: string;
}

export interface Payout {
  id: string;
  amount: number;
  currency: string;
  status: string;
  requested_at: string;
  processed_at?: string;
  payment_method?: string;
}
