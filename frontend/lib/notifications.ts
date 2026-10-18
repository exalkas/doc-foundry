import { ApiClientError } from "./api-client";

type Operation =
  | "create"
  | "update"
  | "delete"
  | "upload"
  | "test"
  | "complete"
  | "match"
  | "extract"
  | "save";
type Resource =
  | "template"
  | "document"
  | "project"
  | "api-key"
  | "webhook"
  | "settings"
  | "workspace"
  | "onboarding";

const successMessages: Record<Operation, Record<Resource, string>> = {
  create: {
    template: "Template created successfully",
    document: "Document uploaded successfully",
    project: "Project created successfully",
    "api-key": "API key created successfully",
    webhook: "Webhook created successfully",
    settings: "Settings saved successfully",
    workspace: "Workspace created successfully",
    onboarding: "Onboarding completed successfully",
  },
  update: {
    template: "Template updated successfully",
    document: "Document updated successfully",
    project: "Project updated successfully",
    "api-key": "API key updated successfully",
    webhook: "Webhook updated successfully",
    settings: "Settings updated successfully",
    workspace: "Workspace updated successfully",
    onboarding: "Onboarding updated successfully",
  },
  delete: {
    template: "Template deleted successfully",
    document: "Document deleted successfully",
    project: "Project deleted successfully",
    "api-key": "API key deleted successfully",
    webhook: "Webhook deleted successfully",
    settings: "Settings deleted successfully",
    workspace: "Workspace deleted successfully",
    onboarding: "Onboarding deleted successfully",
  },
  upload: {
    template: "Template uploaded successfully",
    document: "Document uploaded successfully",
    project: "Project uploaded successfully",
    "api-key": "API key uploaded successfully",
    webhook: "Webhook uploaded successfully",
    settings: "Settings uploaded successfully",
    workspace: "Workspace uploaded successfully",
    onboarding: "Onboarding uploaded successfully",
  },
  test: {
    template: "Template test completed successfully",
    document: "Document test completed successfully",
    project: "Project test completed successfully",
    "api-key": "API key test completed successfully",
    webhook: "Webhook test completed successfully",
    settings: "Settings test completed successfully",
    workspace: "Workspace test completed successfully",
    onboarding: "Onboarding test completed successfully",
  },
  complete: {
    template: "Template completed successfully",
    document: "Document completed successfully",
    project: "Project completed successfully",
    "api-key": "API key completed successfully",
    webhook: "Webhook completed successfully",
    settings: "Settings completed successfully",
    workspace: "Workspace completed successfully",
    onboarding: "Onboarding completed successfully",
  },
  match: {
    template: "Template matched successfully",
    document: "Document matched successfully",
    project: "Project matched successfully",
    "api-key": "API key matched successfully",
    webhook: "Webhook matched successfully",
    settings: "Settings matched successfully",
    workspace: "Workspace matched successfully",
    onboarding: "Onboarding matched successfully",
  },
  extract: {
    template: "Extraction started successfully",
    document: "Extraction started successfully",
    project: "Extraction started successfully",
    "api-key": "Extraction started successfully",
    webhook: "Extraction started successfully",
    settings: "Extraction started successfully",
    workspace: "Extraction started successfully",
    onboarding: "Extraction started successfully",
  },
  save: {
    template: "Changes saved successfully",
    document: "Changes saved successfully",
    project: "Changes saved successfully",
    "api-key": "Changes saved successfully",
    webhook: "Changes saved successfully",
    settings: "Changes saved successfully",
    workspace: "Changes saved successfully",
    onboarding: "Changes saved successfully",
  },
};

const errorMessages: Record<Operation, Record<Resource, string>> = {
  create: {
    template: "Failed to create template",
    document: "Failed to upload document",
    project: "Failed to create project",
    "api-key": "Failed to create API key",
    webhook: "Failed to create webhook",
    settings: "Failed to save settings",
    workspace: "Failed to create workspace",
    onboarding: "Failed to complete onboarding",
  },
  update: {
    template: "Failed to update template",
    document: "Failed to update document",
    project: "Failed to update project",
    "api-key": "Failed to update API key",
    webhook: "Failed to update webhook",
    settings: "Failed to update settings",
    workspace: "Failed to update workspace",
    onboarding: "Failed to update onboarding",
  },
  delete: {
    template: "Failed to delete template",
    document: "Failed to delete document",
    project: "Failed to delete project",
    "api-key": "Failed to delete API key",
    webhook: "Failed to delete webhook",
    settings: "Failed to delete settings",
    workspace: "Failed to delete workspace",
    onboarding: "Failed to delete onboarding",
  },
  upload: {
    template: "Failed to upload template",
    document: "Failed to upload document",
    project: "Failed to upload project",
    "api-key": "Failed to upload API key",
    webhook: "Failed to upload webhook",
    settings: "Failed to upload settings",
    workspace: "Failed to upload workspace",
    onboarding: "Failed to upload onboarding",
  },
  test: {
    template: "Template test failed",
    document: "Document test failed",
    project: "Project test failed",
    "api-key": "API key test failed",
    webhook: "Webhook test failed",
    settings: "Settings test failed",
    workspace: "Workspace test failed",
    onboarding: "Onboarding test failed",
  },
  complete: {
    template: "Failed to complete template",
    document: "Failed to complete document",
    project: "Failed to complete project",
    "api-key": "Failed to complete API key",
    webhook: "Failed to complete webhook",
    settings: "Failed to complete settings",
    workspace: "Failed to complete workspace",
    onboarding: "Failed to complete onboarding",
  },
  match: {
    template: "Failed to match template",
    document: "Failed to match document",
    project: "Failed to match project",
    "api-key": "Failed to match API key",
    webhook: "Failed to match webhook",
    settings: "Failed to match settings",
    workspace: "Failed to match workspace",
    onboarding: "Failed to match onboarding",
  },
  extract: {
    template: "Failed to start extraction",
    document: "Failed to start extraction",
    project: "Failed to start extraction",
    "api-key": "Failed to start extraction",
    webhook: "Failed to start extraction",
    settings: "Failed to start extraction",
    workspace: "Failed to start extraction",
    onboarding: "Failed to start extraction",
  },
  save: {
    template: "Failed to save changes",
    document: "Failed to save changes",
    project: "Failed to save changes",
    "api-key": "Failed to save changes",
    webhook: "Failed to save changes",
    settings: "Failed to save changes",
    workspace: "Failed to save changes",
    onboarding: "Failed to save changes",
  },
};

/**
 * Get success message for an operation and resource
 */
export function getSuccessMessage(
  operation: Operation,
  resource: Resource
): string {
  return (
    successMessages[operation]?.[resource] || "Operation completed successfully"
  );
}

/**
 * Get error message from an error object
 */
export function getErrorMessage(
  error: unknown,
  operation: Operation,
  resource: Resource
): string {
  // Try to extract user-friendly error message from API response
  if (error instanceof ApiClientError) {
    // Check if error has a detail field (from FastAPI) - could be in details.detail or details.message
    if (error.details) {
      if (typeof error.details === "object") {
        if ("detail" in error.details && error.details.detail) {
          return String(error.details.detail);
        }
        if ("message" in error.details && error.details.message) {
          return String(error.details.message);
        }
      }
    }
    // Check if error has a message field
    if (error.message) {
      return error.message;
    }
  }

  // Check if it's a standard Error with message
  if (error instanceof Error) {
    // If it's a network error, provide a user-friendly message
    if (
      error.message.includes("fetch") ||
      error.message.includes("network") ||
      error.message.includes("Failed to fetch")
    ) {
      return "Network error. Please check your connection and try again.";
    }
    return error.message;
  }

  // Fallback to operation-specific error message
  return (
    errorMessages[operation]?.[resource] ||
    "An error occurred. Please try again."
  );
}
