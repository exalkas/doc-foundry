import { z } from "zod";

/**
 * Zod schemas for runtime type validation
 * These schemas match the TypeScript types in lib/types.ts
 */

export const UserSchema = z.object({
  id: z.string(),
  email: z.string().email(),
  full_name: z.string().optional(),
  role: z.enum(["admin", "owner", "member", "readonly"]),
  is_email_verified: z.boolean(),
  workspaces_count: z.number().optional(),
  last_login: z.string().optional(),
});

export const WorkspaceSchema = z.object({
  id: z.string(),
  name: z.string(),
  owner_email: z.string().email().optional(),
  plan: z.string().optional(),
  status: z.enum(["active", "suspended", "trial", "canceled"]),
  created_at: z.string(),
  updated_at: z.string().optional(),
});

export const UsageHistorySchema = z.object({
  date: z.string(),
  documents: z.number(),
  pages: z.number(),
});

export const UsageBreakdownSchema = z.object({
  by_project: z.record(z.string(), z.number()).optional(),
  by_template: z.record(z.string(), z.number()).optional(),
  by_source: z.record(z.string(), z.number()).optional(),
});

export const UsagePeriodSchema = z.object({
  start: z.string(),
  end: z.string(),
  usage: z.object({
    total_documents: z.number(),
    total_pages: z.number(),
    by_project: z.record(z.string(), z.number()).optional(),
    by_template: z.record(z.string(), z.number()).optional(),
  }),
});

export const UsageAnalyticsSchema = z.object({
  workspace_id: z.string(),
  current_period: UsagePeriodSchema,
  breakdown: UsageBreakdownSchema,
  history: z.array(UsageHistorySchema),
});

export const ViolationSchema = z.object({
  type: z.string(),
  severity: z.enum(["low", "medium", "high"]),
  description: z.string(),
  threshold: z.number().optional(),
  usage: z.number().optional(),
  limit: z.number().optional(),
});

export const AbuseDetectionSchema = z.object({
  workspace_id: z.string(),
  violations: z.array(ViolationSchema),
  risk_score: z.number(),
  recommendations: z.array(z.string()),
});

export const AffiliateStatsSchema = z.object({
  total_clicks: z.number(),
  total_signups: z.number(),
  paying_customers: z.number(),
  total_earned: z.number(),
  pending_earned: z.number(),
  cleared_earned: z.number(),
  paid_earned: z.number(),
  mrr_generated: z.number(),
});

export const AffiliateSchema = z.object({
  id: z.string(),
  user_id: z.string(),
  user_email: z.string().email(),
  slug: z.string(),
  status: z.enum(["pending", "approved", "rejected", "blocked"]),
  commission_plan_id: z.string(),
  company_name: z.string().optional(),
  website: z.string().url().optional().or(z.literal("")),
  payment_method_type: z.string().optional(),
  country: z.string().optional(),
  tax_id: z.string().optional(),
  notes: z.string().optional(),
  created_at: z.string(),
  updated_at: z.string().optional(),
  stats: AffiliateStatsSchema.optional(),
});

export const CommissionSchema = z.object({
  id: z.string(),
  affiliate_id: z.string(),
  customer_id: z.string(),
  subscription_id: z.string(),
  event_type: z.enum(["initial", "recurring", "upgrade", "downgrade"]),
  amount: z.number(),
  currency: z.string(),
  status: z.enum(["pending", "cleared", "paid", "reversed"]),
  event_date: z.string(),
  cleared_at: z.string().optional(),
  notes: z.string().optional(),
});

export const PayoutSchema = z.object({
  id: z.string(),
  affiliate_id: z.string(),
  amount: z.number(),
  currency: z.string(),
  status: z.enum(["requested", "approved", "paid", "rejected"]),
  requested_at: z.string(),
  processed_at: z.string().optional(),
  payment_method: z.string().optional(),
  payment_reference: z.string().optional(),
  notes: z.string().optional(),
});

export const SystemMetricsSchema = z.object({
  queue_depth: z.number().optional(),
  avg_processing_time: z.number().optional(),
  daily_docs_processed: z.number().optional(),
  errors_last_24h: z.number().optional(),
});

export const ApiErrorResponseSchema = z.object({
  detail: z.string(),
  code: z.string().optional(),
});

// Array schemas for API responses
export const UsersArraySchema = z.array(UserSchema);
export const WorkspacesArraySchema = z.array(WorkspaceSchema);
export const AffiliatesArraySchema = z.array(AffiliateSchema);
export const CommissionsArraySchema = z.array(CommissionSchema);
export const PayoutsArraySchema = z.array(PayoutSchema);
