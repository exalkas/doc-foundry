/**
 * Centralized help content library
 *
 * Help content derived from business logic documentation.
 * Used by HelpIcon and HelpText components throughout the application.
 */

export interface HelpContent {
  short: string; // For tooltips (< 100 chars recommended)
  long?: string; // For expanded help sections
  link?: string; // Link to documentation
  related?: string[]; // Related help topic IDs
}

export type HelpTopicId =
  // Upload Page
  | "upload.project"
  | "upload.template"
  | "upload.priority"
  | "upload.file-limits"
  // API Keys
  | "api-keys.name"
  | "api-keys.scopes"
  | "api-keys.scope.documents:write"
  | "api-keys.scope.documents:read"
  | "api-keys.scope.templates:read"
  | "api-keys.scope.webhooks:manage"
  | "api-keys.expiration"
  | "api-keys.security"
  // Webhooks
  | "webhooks.target-url"
  | "webhooks.signing-secret"
  | "webhooks.events"
  | "webhooks.event.document.succeeded"
  | "webhooks.event.document.failed"
  | "webhooks.event.usage.threshold_80"
  | "webhooks.event.usage.threshold_100"
  | "webhooks.retry-policy"
  | "webhooks.setup"
  // Usage & Billing
  | "billing.usage-metrics"
  | "billing.plan-limits"
  | "billing.overage"
  | "billing.soft-hard-limits"
  | "billing.billing-cycle"
  | "billing.plan-comparison"
  // Templates
  | "templates.field-types"
  | "templates.validation-rules"
  | "templates.versioning"
  | "templates.auto-detection"
  // Projects
  | "projects.workspace"
  | "projects.roles"
  // Dashboard
  | "dashboard.extraction-states"
  | "dashboard.usage-breakdown";

const helpContent: Record<HelpTopicId, HelpContent> = {
  // Upload Page
  "upload.project": {
    short:
      "Organize documents by project. Optional but recommended for better organization.",
    long: "Projects help organize your documents, templates, and extraction jobs. Each project belongs to one workspace and can contain multiple documents and templates. You can create projects for different clients, document types, or workflows.",
  },
  "upload.template": {
    short:
      "Select a template to automatically extract data. Optional - can be applied later.",
    long: "Templates define which fields to extract from your documents. If you select a template during upload, extraction will start automatically. You can also upload without a template and apply one later, or use auto-detection to match documents to templates automatically.",
    related: ["templates.auto-detection"],
  },
  "upload.priority": {
    short:
      "High priority jobs are processed first. Available on Pro and Enterprise plans.",
    long: "When enabled, your document will be sent to the front of the processing queue. Priority processing is available on Pro and Enterprise plans. Free and Starter plans process documents in the order they are received.",
    related: ["billing.plan-comparison"],
  },
  "upload.file-limits": {
    short: "PDF, PNG, JPG up to 25 MB. Page limits vary by plan.",
    long: "Supported file types: PDF, PNG, JPG, and other image formats. Maximum file size is 25 MB per document. Maximum pages per document varies by plan (check your plan limits). Each page counts toward your monthly usage quota.",
    related: ["billing.plan-limits", "billing.usage-metrics"],
  },

  // API Keys
  "api-keys.name": {
    short: "A descriptive name helps identify where this API key is used.",
    long: "Give your API key a descriptive name that helps you remember where it's used (e.g., 'Zapier invoices workflow', 'Production app', 'Testing script'). This makes it easier to manage and revoke keys when needed.",
  },
  "api-keys.scopes": {
    short:
      "Scopes control what actions this API key can perform. Select only what's needed.",
    long: "API key scopes limit what operations the key can perform. Use the principle of least privilege - only grant the minimum permissions needed. You can create multiple keys with different scopes for different use cases.",
    related: [
      "api-keys.scope.documents:write",
      "api-keys.scope.documents:read",
      "api-keys.scope.templates:read",
      "api-keys.scope.webhooks:manage",
    ],
  },
  "api-keys.scope.documents:write": {
    short: "Allows creating documents and triggering extraction jobs via API.",
    long: "The documents:write scope allows the API key to upload documents, create extraction jobs, and modify document metadata. This is required for any automation that processes documents.",
  },
  "api-keys.scope.documents:read": {
    short: "Allows reading document data and extraction results.",
    long: "The documents:read scope allows the API key to retrieve document information, extraction results, and job status. Use this for read-only integrations that need to access processed data.",
  },
  "api-keys.scope.templates:read": {
    short: "Allows reading template configurations and field definitions.",
    long: "The templates:read scope allows the API key to retrieve template information, including field definitions and configurations. This is useful for integrations that need to know what fields are available.",
  },
  "api-keys.scope.webhooks:manage": {
    short: "Allows creating, updating, and deleting webhook endpoints.",
    long: "The webhooks:manage scope allows the API key to configure webhook endpoints. Use this for integrations that need to set up automated notifications when documents are processed.",
    related: ["webhooks.setup"],
  },
  "api-keys.expiration": {
    short:
      "Set expiration to automatically revoke keys after a period. Recommended for security.",
    long: "API keys can be set to expire automatically after 7, 30, or 90 days. Expired keys are automatically revoked and cannot be used. Setting an expiration is a security best practice, especially for keys used in development or testing environments.",
    related: ["api-keys.security"],
  },
  "api-keys.security": {
    short:
      "Store API keys securely. Never commit them to version control. Revoke compromised keys immediately.",
    long: "API keys provide full access to your workspace within their scope. Store them securely using environment variables or secret management tools. Never commit API keys to version control or share them publicly. If a key is compromised, revoke it immediately and create a new one. Rotate keys regularly, especially if team members leave.",
  },

  // Webhooks
  "webhooks.target-url": {
    short:
      "The URL where webhook events will be sent. Must be publicly accessible HTTPS endpoint.",
    long: "Your webhook endpoint URL must be publicly accessible over HTTPS. This is where we'll send POST requests when events occur. The endpoint should return a 2xx status code to acknowledge receipt. We'll retry failed deliveries based on your retry policy.",
    related: ["webhooks.retry-policy"],
  },
  "webhooks.signing-secret": {
    short:
      "Secret used to verify webhook signatures. Keep this secure and use it to validate requests.",
    long: "The signing secret is used to generate HMAC signatures for webhook payloads. Use this secret to verify that webhooks are actually coming from DocFoundry and haven't been tampered with. Include the signature in the X-DocFoundry-Signature header when verifying requests. Never expose this secret publicly.",
    related: ["webhooks.setup"],
  },
  "webhooks.events": {
    short:
      "Select which events trigger webhooks. Only selected events will be sent to your endpoint.",
    long: "Choose which events should trigger webhook deliveries. You can select multiple events. Only events you select will be sent to your webhook endpoint. This helps reduce unnecessary webhook calls and allows you to handle different event types separately.",
    related: [
      "webhooks.event.document.succeeded",
      "webhooks.event.document.failed",
      "webhooks.event.usage.threshold_80",
      "webhooks.event.usage.threshold_100",
    ],
  },
  "webhooks.event.document.succeeded": {
    short: "Triggered when a document extraction job completes successfully.",
    long: "This event is sent when an extraction job transitions to the 'succeeded' state. The webhook payload includes the extracted data, document metadata, and job information. Use this to automatically process successful extractions.",
  },
  "webhooks.event.document.failed": {
    short: "Triggered when a document extraction job fails permanently.",
    long: "This event is sent when an extraction job transitions to the 'failed' state after all retries are exhausted. The webhook payload includes error details and document metadata. Use this to monitor and handle processing failures.",
  },
  "webhooks.event.usage.threshold_80": {
    short: "Triggered when workspace usage reaches 80% of monthly quota.",
    long: "This event is sent when your workspace's monthly usage reaches 80% of your plan's quota. Use this to get early warning before hitting limits and plan upgrades if needed.",
    related: ["billing.plan-limits", "billing.overage"],
  },
  "webhooks.event.usage.threshold_100": {
    short: "Triggered when workspace usage reaches 100% of monthly quota.",
    long: "This event is sent when your workspace's monthly usage reaches 100% of your plan's quota. On free plans, this may block new processing. On paid plans, overage charges may apply.",
    related: ["billing.soft-hard-limits", "billing.overage"],
  },
  "webhooks.retry-policy": {
    short:
      "Exponential backoff retries failed deliveries with increasing delays. Recommended for reliability.",
    long: "When a webhook delivery fails (non-2xx response or timeout), we'll retry the delivery. Exponential backoff means retry delays increase exponentially (1 min, 5 min, 15 min) to avoid overwhelming your server. After maximum retries, the delivery is marked as failed and the webhook endpoint may be disabled. No retries means failed deliveries are not retried.",
  },
  "webhooks.setup": {
    short:
      "Webhooks notify your app when documents finish processing. Verify signatures for security.",
    long: "Webhooks allow you to receive real-time notifications when documents are processed. Set up a publicly accessible HTTPS endpoint, configure events, and use the signing secret to verify requests. Webhooks are retried on failure with exponential backoff. Test your webhook endpoint using the 'Send test event' button before going live.",
    related: [
      "webhooks.target-url",
      "webhooks.signing-secret",
      "webhooks.retry-policy",
    ],
  },

  // Usage & Billing
  "billing.usage-metrics": {
    short:
      "Usage is measured in pages processed. Only successful extractions count toward usage.",
    long: "Usage is measured in pages processed. Each page of a PDF or image counts as one page. Usage is only counted when an extraction job transitions to 'succeeded' or 'needs_review' state. Failed jobs don't count toward usage on paid plans (free plans count failures to prevent abuse). Usage resets at the start of each billing cycle.",
    related: ["dashboard.extraction-states"],
  },
  "billing.plan-limits": {
    short:
      "Each plan includes a monthly page quota. Overage charges apply on paid plans.",
    long: "Each plan includes a monthly quota of pages that can be processed. Free plans have hard limits (processing stops at quota). Paid plans allow overage with additional charges. Check your plan details for exact limits and overage pricing.",
    related: ["billing.soft-hard-limits", "billing.overage"],
  },
  "billing.overage": {
    short: "Paid plans allow usage beyond quota with per-page overage charges.",
    long: "On paid plans, you can process documents beyond your monthly quota. Overage is charged per 1,000 pages at the rate specified in your plan. Overage charges are calculated at the end of each billing cycle and added to your invoice. Free plans have hard limits and cannot exceed quota.",
    related: ["billing.plan-limits", "billing.soft-hard-limits"],
  },
  "billing.soft-hard-limits": {
    short:
      "Free plans have hard limits (processing stops). Paid plans allow overage.",
    long: "Free plans use hard limits - when you reach your monthly quota, new extraction jobs are rejected until the next billing cycle. Paid plans use soft limits - you can exceed your quota, and overage charges apply. Some paid plans allow you to optionally enable a hard cap if you want to prevent overage charges.",
    related: ["billing.plan-limits", "billing.overage"],
  },
  "billing.billing-cycle": {
    short:
      "Billing cycles are monthly. Usage resets at the start of each cycle.",
    long: "Billing cycles run monthly from your subscription start date. Usage is tracked per cycle and resets at the start of each new cycle. Overage charges are calculated and invoiced at the end of each cycle. You can view your current period dates in your subscription details.",
  },
  "billing.plan-comparison": {
    short:
      "Compare plans by features, limits, and pricing. Upgrade anytime to unlock more capacity.",
    long: "Plans differ in monthly quotas, overage pricing, features (webhooks, priority queue, integrations), and support levels. Free plans are for testing and evaluation. Starter plans suit small businesses. Pro plans are for agencies and SMEs. Enterprise plans offer custom pricing and SLAs. You can upgrade anytime - changes take effect immediately with prorated billing.",
  },

  // Templates
  "templates.field-types": {
    short:
      "Field types include string, number, date, enum, boolean, and array.",
    long: "Template fields support multiple data types: string (text), number (numeric values), date (with various formats), enum (predefined options), boolean (true/false), and array (lists of values). Choose the appropriate type for validation and post-processing.",
  },
  "templates.validation-rules": {
    short:
      "Validation rules ensure extracted data meets requirements (regex, ranges, allowed values).",
    long: "Validation rules help ensure extracted data is correct. You can define regex patterns, numeric ranges (min/max), allowed values for enums, and required field checks. If validation fails, the job is marked as 'needs_review' for manual correction.",
  },
  "templates.versioning": {
    short:
      "Editing a template creates a new version. Jobs reference specific versions.",
    long: "When you edit a template, a new version is created (v1, v2, v3, etc.). Extraction jobs always reference a specific template version, ensuring consistency. You can promote any version to be the default for new jobs. This allows you to test changes without affecting existing workflows.",
  },
  "templates.auto-detection": {
    short:
      "Auto-detection matches documents to templates using ML. Requires template_id to be omitted.",
    long: "When uploading without specifying a template, the system can automatically detect which template to use by comparing the document against existing templates using machine learning. If confidence is above the threshold, the template is auto-assigned. Otherwise, the job is marked as 'needs_review'.",
  },

  // Projects
  "projects.workspace": {
    short:
      "Projects belong to a workspace. Billing and usage are tracked per workspace.",
    long: "Projects are organized within workspaces (organizations). Each workspace has its own subscription, billing, usage tracking, API keys, and webhooks. A user can belong to multiple workspaces. Billing is per workspace, not per user.",
  },
  "projects.roles": {
    short:
      "Roles control access: Owner (billing), Admin (manage resources), Member (use), Read-only (view).",
    long: "Workspace roles control what users can do: Owner manages billing and workspace settings, Admin manages projects/templates/API keys, Member can use templates and upload documents, Read-only can only view results. Roles are assigned per workspace.",
  },

  // Dashboard
  "dashboard.extraction-states": {
    short: "Job states: queued → processing → succeeded/failed/needs_review.",
    long: "Extraction jobs progress through states: queued (waiting), processing (active), succeeded (complete), failed (error), or needs_review (low confidence/validation failed). Only succeeded and needs_review jobs count toward usage.",
    related: ["billing.usage-metrics"],
  },
  "dashboard.usage-breakdown": {
    short:
      "Usage can be viewed by project, template, or integration (API, UI, Zapier, Make, n8n).",
    long: "Usage metrics can be filtered and viewed by project, template, or integration type (API calls, UI uploads, Zapier/Make/n8n integrations). This helps you understand where your usage is coming from and optimize your workflows.",
  },
};

/**
 * Get help content for a topic
 */
export function getHelpContent(topicId: HelpTopicId): HelpContent {
  return helpContent[topicId] || { short: "Help content not available." };
}

/**
 * Get short help text (for tooltips)
 */
export function getHelpText(topicId: HelpTopicId): string {
  return getHelpContent(topicId).short;
}

/**
 * Get long help text (for expanded help)
 */
export function getHelpTextLong(topicId: HelpTopicId): string | undefined {
  return getHelpContent(topicId).long;
}

/**
 * Get related help topics
 */
export function getRelatedHelp(topicId: HelpTopicId): HelpTopicId[] {
  return getHelpContent(topicId).related || [];
}
