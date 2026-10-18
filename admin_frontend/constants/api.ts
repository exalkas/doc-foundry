/**
 * API Configuration Constants
 * 
 * Centralized constants for API configuration to avoid magic numbers throughout the codebase.
 */

export const API_CONFIG = {
  /** Cache stale time for React Query (30 seconds) */
  STALE_TIME: 30 * 1000,
  
  /** Request timeout in milliseconds (30 seconds) */
  REQUEST_TIMEOUT: 30000,
  
  /** Minimum length for suspend reason */
  MIN_SUSPEND_REASON_LENGTH: 20,
  
  /** CSRF token expiration time in milliseconds (1 hour) */
  CSRF_TOKEN_EXPIRATION: 60 * 60 * 1000,
  
  /** Maximum retry attempts for failed requests */
  MAX_RETRIES: 3,
  
  /** Base delay for retry exponential backoff (milliseconds) */
  RETRY_BASE_DELAY: 1000,
} as const;

/**
 * Error Messages
 * 
 * Centralized error messages for consistent user-facing error handling.
 */
export const ERROR_MESSAGES = {
  NETWORK_ERROR: "Unable to connect to server. Please check your connection.",
  UNAUTHORIZED: "Your session has expired. Please log in again.",
  FORBIDDEN: "You don't have permission to perform this action.",
  NOT_FOUND: "The requested resource was not found.",
  SERVER_ERROR: "An unexpected server error occurred. Please try again later.",
  TIMEOUT: "The request took too long to complete. Please try again.",
  VALIDATION_ERROR: "Invalid request. Please check your input.",
  UNKNOWN_ERROR: "An unexpected error occurred.",
} as const;

/**
 * Get user-friendly error message from API error
 */
export function getErrorMessage(error: { status?: number; message?: string }): string {
  if (!error.status) {
    return error.message || ERROR_MESSAGES.UNKNOWN_ERROR;
  }
  
  switch (error.status) {
    case 400:
      return ERROR_MESSAGES.VALIDATION_ERROR;
    case 401:
      return ERROR_MESSAGES.UNAUTHORIZED;
    case 403:
      return ERROR_MESSAGES.FORBIDDEN;
    case 404:
      return ERROR_MESSAGES.NOT_FOUND;
    case 408:
      return ERROR_MESSAGES.TIMEOUT;
    case 500:
    case 502:
    case 503:
      return ERROR_MESSAGES.SERVER_ERROR;
    default:
      return error.message || ERROR_MESSAGES.UNKNOWN_ERROR;
  }
}
