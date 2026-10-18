/**
 * API client for backend calls
 */

import { getAuthToken } from "./auth";
import { API_CONFIG, getErrorMessage as getErrorMsg } from "@/constants/api";

/**
 * Browser: same-origin `/api/...` so Next.js rewrites proxy to FastAPI (no CORS).
 * Server (SSR/RSC): absolute backend URL for direct server-to-API calls.
 */
export function getApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    return "";
  }
  return (
    process.env.BACKEND_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000"
  );
}

// CSRF token cache with expiration
interface CsrfTokenCache {
  token: string;
  expiresAt: number;
}

let csrfTokenCache: CsrfTokenCache | null = null;
let csrfTokenPromise: Promise<string> | null = null;

export interface ApiError {
  message: string;
  code?: string;
  details?: any;
}

export class ApiClientError extends Error {
  code?: string;
  details?: any;
  status?: number;

  constructor(message: string, status?: number, code?: string, details?: any) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

/**
 * Get CSRF token from backend
 */
async function getCsrfToken(): Promise<string> {
  // Return cached token if available and not expired
  if (csrfTokenCache && csrfTokenCache.expiresAt > Date.now()) {
    return csrfTokenCache.token;
  }

  // If a request is already in progress, wait for it
  if (csrfTokenPromise) {
    return csrfTokenPromise;
  }

  // Fetch new CSRF token
  csrfTokenPromise = (async () => {
    try {
      const response = await fetch(`${getApiBaseUrl()}/api/auth/csrf-token`, {
        method: "GET",
        credentials: "include", // Include cookies for session
      });

      if (!response.ok) {
        throw new Error("Failed to fetch CSRF token");
      }

      const data = await response.json();
      const expiresAt = Date.now() + API_CONFIG.CSRF_TOKEN_EXPIRATION;
      csrfTokenCache = {
        token: data.csrf_token,
        expiresAt,
      };
      return csrfTokenCache.token;
    } catch (error) {
      csrfTokenPromise = null;
      throw error;
    } finally {
      csrfTokenPromise = null;
    }
  })();

  return csrfTokenPromise;
}

/**
 * Clear CSRF token cache (e.g., on logout)
 */
export function clearCsrfToken(): void {
  csrfTokenCache = null;
  csrfTokenPromise = null;
}

/**
 * Retry a request with exponential backoff
 */
async function apiRequestWithRetry<T>(
  endpoint: string,
  options: RequestInit = {},
  maxRetries: number = API_CONFIG.MAX_RETRIES
): Promise<T> {
  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await apiRequest<T>(endpoint, options);
    } catch (error: any) {
      lastError = error;

      // Don't retry on client errors (4xx) except 408 (timeout)
      if (
        error instanceof ApiClientError &&
        error.status &&
        error.status >= 400 &&
        error.status < 500 &&
        error.status !== 408
      ) {
        throw error;
      }

      // Don't retry on last attempt
      if (attempt === maxRetries) {
        break;
      }

      // Exponential backoff: delay = baseDelay * 2^attempt
      const delay = API_CONFIG.RETRY_BASE_DELAY * Math.pow(2, attempt);
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }

  throw lastError || new Error("Request failed after retries");
}

/**
 * Make API request with auth headers and CSRF token
 */
async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getAuthToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  // Add CSRF token for state-changing requests (POST, PUT, PATCH, DELETE)
  const method = options.method?.toUpperCase() || "GET";
  if (method !== "GET" && method !== "HEAD" && method !== "OPTIONS") {
    try {
      const csrf = await getCsrfToken();
      headers["X-CSRF-Token"] = csrf;
    } catch (error) {
      // If CSRF token fetch fails, continue anyway (might be unauthenticated request)
      console.warn("Failed to get CSRF token:", error);
    }
  }

  const url = endpoint.startsWith("http")
    ? endpoint
    : `${getApiBaseUrl()}${endpoint}`;

  // Create AbortController for timeout
  const controller = new AbortController();
  const timeoutId = setTimeout(
    () => controller.abort(),
    API_CONFIG.REQUEST_TIMEOUT
  );
  const requestStartTime = Date.now();

  try {
    const response = await fetch(url, {
      ...options,
      headers,
      credentials: "include", // Include cookies
      signal: controller.signal,
    });

    clearTimeout(timeoutId);
    const requestTime = Date.now() - requestStartTime;

    // Handle 204 No Content - no body to parse
    if (response.status === 204) {
      return {} as T;
    }

    if (!response.ok) {
      let errorData: any;
      try {
        // Check if response has content before trying to parse JSON
        const text = await response.text();
        if (text && text.trim()) {
          errorData = JSON.parse(text);
        } else {
          errorData = {
            message: `HTTP ${response.status}: ${response.statusText}`,
          };
        }
      } catch (parseError) {
        console.error("Failed to parse error response:", parseError);
        errorData = {
          message: `HTTP ${response.status}: ${response.statusText}`,
        };
      }

      // FastAPI returns errors with "detail" field, not "message"
      const errorMessage =
        errorData.detail || errorData.message || "API request failed";

      const apiError = new ApiClientError(
        errorMessage,
        response.status,
        errorData.code,
        errorData
      );

      // Track API errors with Sentry (only for server errors, not client errors)
      if (
        typeof window !== "undefined" &&
        process.env.NEXT_PUBLIC_SENTRY_DSN &&
        response.status >= 500
      ) {
        import("@sentry/nextjs").then((Sentry) => {
          Sentry.captureException(apiError, {
            tags: {
              endpoint,
              method,
              status: response.status.toString(),
            },
            extra: {
              errorData,
              requestTime: Date.now() - requestStartTime,
            },
          });
        });
      }

      throw apiError;
    }

    // Try to parse response body
    const text = await response.text();

    // If no content, return empty object
    if (!text || text.trim() === "") {
      return {} as T;
    }

    // Check content type, but don't fail if it's missing (some servers don't set it)
    const contentType = response.headers.get("content-type");
    if (contentType && !contentType.includes("application/json")) {
      // If content-type is set and it's not JSON, return empty object
      return {} as T;
    }

    // Try to parse as JSON
    try {
      const result = JSON.parse(text) as T;
      return result;
    } catch (error) {
      // If JSON parsing fails, log warning and return empty object
      console.error(`Failed to parse JSON for ${method} ${endpoint}:`, error);
      return {} as T;
    }
  } catch (error: any) {
    clearTimeout(timeoutId);
    const requestTime = Date.now() - requestStartTime;

    // Handle timeout/abort errors
    if (error.name === "AbortError" || controller.signal.aborted) {
      const timeoutError = new ApiClientError(
        "Request timeout: The server took too long to respond",
        408,
        "TIMEOUT"
      );

      // Track timeout errors with Sentry
      if (typeof window !== "undefined" && process.env.NEXT_PUBLIC_SENTRY_DSN) {
        import("@sentry/nextjs").then((Sentry) => {
          Sentry.captureException(timeoutError, {
            tags: {
              endpoint,
              method,
              errorType: "timeout",
            },
            extra: {
              requestTime,
            },
          });
        });
      }

      throw timeoutError;
    }

    // Re-throw ApiClientError as-is
    if (error instanceof ApiClientError) {
      throw error;
    }

    // Wrap other errors and track network errors
    const wrappedError = new ApiClientError(
      error.message || "API request failed",
      undefined,
      undefined,
      error
    );

    // Track network/unknown errors with Sentry
    if (typeof window !== "undefined" && process.env.NEXT_PUBLIC_SENTRY_DSN) {
      import("@sentry/nextjs").then((Sentry) => {
        Sentry.captureException(wrappedError, {
          tags: {
            endpoint,
            method,
            errorType: "network",
          },
          extra: {
            originalError: error.message,
            requestTime,
          },
        });
      });
    }

    throw wrappedError;
  }
}

/**
 * GET request with automatic retry
 *
 * @param endpoint - API endpoint path (e.g., "/api/admin/workspaces")
 * @returns Promise resolving to the response data
 *
 * @example
 * ```ts
 * const workspaces = await get<Workspace[]>("/api/admin/workspaces");
 * ```
 */
export async function get<T>(endpoint: string): Promise<T> {
  return apiRequestWithRetry<T>(endpoint, { method: "GET" });
}

/**
 * POST request
 *
 * @param endpoint - API endpoint path
 * @param data - Optional request body data (will be JSON stringified)
 * @returns Promise resolving to the response data
 *
 * @example
 * ```ts
 * const result = await post("/api/admin/workspaces/123/suspend", { reason: "Violation" });
 * ```
 */
export async function post<T>(endpoint: string, data?: any): Promise<T> {
  return apiRequest<T>(endpoint, {
    method: "POST",
    body: data ? JSON.stringify(data) : undefined,
  });
}

/**
 * PUT request
 *
 * @param endpoint - API endpoint path
 * @param data - Optional request body data (will be JSON stringified)
 * @returns Promise resolving to the response data
 */
export async function put<T>(endpoint: string, data?: any): Promise<T> {
  return apiRequest<T>(endpoint, {
    method: "PUT",
    body: data ? JSON.stringify(data) : undefined,
  });
}

/**
 * PATCH request
 *
 * @param endpoint - API endpoint path
 * @param data - Optional request body data (will be JSON stringified)
 * @returns Promise resolving to the response data
 */
export async function patch<T>(endpoint: string, data?: any): Promise<T> {
  return apiRequest<T>(endpoint, {
    method: "PATCH",
    body: data ? JSON.stringify(data) : undefined,
  });
}

/**
 * DELETE request
 *
 * @param endpoint - API endpoint path
 * @returns Promise resolving to the response data
 */
export async function del<T>(endpoint: string): Promise<T> {
  return apiRequest<T>(endpoint, { method: "DELETE" });
}
