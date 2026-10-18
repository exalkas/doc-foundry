/**
 * App constants
 */

export const APP_NAME = "DocFoundry";
export const APP_TAGLINE = "Forge any document into clean, usable data.";

export const ROUTES = {
  HOME: "/",
  LOGIN: "/login",
  REGISTER: "/register",
  DASHBOARD: "/app",
  ONBOARDING: "/app/onboarding",
  PROJECTS: "/app/projects",
  UPLOAD: "/app/upload",
  TEMPLATES: "/app/templates",
  TEMPLATE_LIBRARY: "/app/template-library",
  DOCUMENTS: "/app/documents",
  SETTINGS: "/app/settings",
  API_KEYS: "/app/settings/api-keys",
  WEBHOOKS: "/app/settings/webhooks",
  USAGE_BILLING: "/app/settings/usage-billing",
  INTEGRATIONS: "/app/integrations",
  NOTIFICATIONS: "/app/notifications",
  ADMIN: "/admin",
} as const;

export const USER_ROLES = {
  ADMIN: "admin",
  OWNER: "owner",
  MEMBER: "member",
  READONLY: "readonly",
} as const;

export const DOCUMENT_STATUS = {
  PENDING: "pending",
  QUEUED: "queued",
  PROCESSING: "processing",
  SUCCEEDED: "succeeded",
  FAILED: "failed",
  NEEDS_REVIEW: "needs_review",
} as const;

export const EXPORT_FORMATS = {
  JSON: "json",
  CSV: "csv",
  EXCEL: "excel",
} as const;

export const TEMPLATE_CATEGORIES = {
  ACCOUNTING_FINANCE: "accounting_finance",
  LOGISTICS: "logistics",
  ECOMMERCE: "ecommerce",
  HR_LEGAL: "hr_legal",
} as const;

export const TEMPLATE_CATEGORY_LABELS: Record<string, string> = {
  accounting_finance: "Accounting & Finance",
  logistics: "Logistics",
  ecommerce: "E-commerce",
  hr_legal: "HR & Legal",
};
