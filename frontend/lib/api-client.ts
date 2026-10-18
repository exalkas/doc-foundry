/**
 * API client for backend calls
 */

import { getAuthToken } from "./auth";

const BACKEND_URL =
  process.env.BACKEND_URL ||
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  "http://localhost:8000";

// CSRF token cache
let csrfToken: string | null = null;
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
  // Return cached token if available
  if (csrfToken) {
    return csrfToken;
  }

  // If a request is already in progress, wait for it
  if (csrfTokenPromise) {
    return csrfTokenPromise;
  }

  // Fetch new CSRF token
  csrfTokenPromise = (async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/auth/csrf-token`, {
        method: "GET",
        credentials: "include", // Include cookies for session
      });

      if (!response.ok) {
        throw new Error("Failed to fetch CSRF token");
      }

      const data = await response.json();
      csrfToken = data.csrf_token;
      return csrfToken!;
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
  csrfToken = null;
  csrfTokenPromise = null;
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

  // Add workspace context if available
  const workspaceId =
    typeof window !== "undefined"
      ? localStorage.getItem("current_workspace_id")
      : null;

  if (workspaceId) {
    headers["X-Workspace-Id"] = workspaceId;
  }

  const url = endpoint.startsWith("http")
    ? endpoint
    : `${BACKEND_URL}${endpoint}`;

  // Create AbortController for timeout
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout
  const requestStartTime = Date.now();

  console.log(`[API_CLIENT] Starting request: ${method} ${endpoint}`);

  try {
    const response = await fetch(url, {
      ...options,
      headers,
      credentials: "include", // Include cookies
      signal: controller.signal,
    });

    clearTimeout(timeoutId);
    const requestTime = Date.now() - requestStartTime;
    console.log(
      `[API_CLIENT] Request completed: ${method} ${endpoint} - ${response.status} in ${requestTime}ms`
    );

    // Handle 204 No Content - no body to parse
    if (response.status === 204) {
      return {} as T;
    }

    // 201 Created responses typically have JSON body, don't skip parsing

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
      } catch {
        errorData = {
          message: `HTTP ${response.status}: ${response.statusText}`,
        };
      }

      // FastAPI returns errors with "detail" field, not "message"
      const errorMessage =
        errorData.detail || errorData.message || "API request failed";

      throw new ApiClientError(
        errorMessage,
        response.status,
        errorData.code,
        errorData
      );
    }

    // Try to parse response body
    // Read the text first to check if there's content
    const parseStartTime = Date.now();
    console.log(
      `[API_CLIENT] Starting to read response body for ${method} ${endpoint}`
    );
    const text = await response.text();
    const parseTime = Date.now() - parseStartTime;
    const textSize = text.length;
    console.log(
      `[API_CLIENT] Response body read in ${parseTime}ms, size: ${(
        textSize / 1024
      ).toFixed(2)}KB for ${method} ${endpoint}`
    );

    // If no content, return empty object
    if (!text || text.trim() === "") {
      console.log(`[API_CLIENT] Empty response body for ${method} ${endpoint}`);
      return {} as T;
    }

    // Check content type, but don't fail if it's missing (some servers don't set it)
    const contentType = response.headers.get("content-type");
    if (contentType && !contentType.includes("application/json")) {
      console.log(
        `[API_CLIENT] Non-JSON content type (${contentType}) for ${method} ${endpoint}`
      );
      // If content-type is set and it's not JSON, return empty object
      return {} as T;
    }

    // Try to parse as JSON
    const jsonParseStartTime = Date.now();
    console.log(
      `[API_CLIENT] Starting JSON parse for ${method} ${endpoint}, text length: ${textSize}`
    );
    try {
      const result = JSON.parse(text) as T;
      const jsonParseTime = Date.now() - jsonParseStartTime;
      const totalTime = Date.now() - requestStartTime;
      console.log(
        `[API_CLIENT] JSON parsed successfully in ${jsonParseTime}ms, total request time: ${totalTime}ms for ${method} ${endpoint}`
      );
      return result;
    } catch (error) {
      const jsonParseTime = Date.now() - jsonParseStartTime;
      // If JSON parsing fails, log warning and return empty object
      console.error(
        `[API_CLIENT] Failed to parse JSON after ${jsonParseTime}ms for ${method} ${endpoint}:`,
        error,
        "Response text preview:",
        text.substring(0, 200)
      );
      return {} as T;
    }
  } catch (error: any) {
    clearTimeout(timeoutId);
    const requestTime = Date.now() - requestStartTime;

    // Handle timeout/abort errors
    if (error.name === "AbortError" || controller.signal.aborted) {
      console.error(
        `[API_CLIENT] Request timeout after ${requestTime}ms: ${method} ${endpoint}`
      );
      throw new ApiClientError(
        "Request timeout: The server took too long to respond",
        408,
        "TIMEOUT"
      );
    }

    console.error(
      `[API_CLIENT] Request failed after ${requestTime}ms: ${method} ${endpoint}`,
      error
    );

    // Re-throw ApiClientError as-is
    if (error instanceof ApiClientError) {
      throw error;
    }

    // Wrap other errors
    throw new ApiClientError(
      error.message || "API request failed",
      undefined,
      undefined,
      error
    );
  }
}

/**
 * GET request
 */
export async function get<T>(endpoint: string): Promise<T> {
  return apiRequest<T>(endpoint, { method: "GET" });
}

/**
 * POST request
 */
export async function post<T>(endpoint: string, data?: any): Promise<T> {
  return apiRequest<T>(endpoint, {
    method: "POST",
    body: data ? JSON.stringify(data) : undefined,
  });
}

/**
 * PUT request
 */
export async function put<T>(endpoint: string, data?: any): Promise<T> {
  return apiRequest<T>(endpoint, {
    method: "PUT",
    body: data ? JSON.stringify(data) : undefined,
  });
}

/**
 * PATCH request
 */
export async function patch<T>(endpoint: string, data?: any): Promise<T> {
  return apiRequest<T>(endpoint, {
    method: "PATCH",
    body: data ? JSON.stringify(data) : undefined,
  });
}

/**
 * DELETE request
 */
export async function del<T>(endpoint: string): Promise<T> {
  return apiRequest<T>(endpoint, { method: "DELETE" });
}

/**
 * Upload file with multipart/form-data
 */
export async function uploadFile<T>(
  endpoint: string,
  file: File,
  additionalData?: Record<string, any>
): Promise<T> {
  const token = getAuthToken();
  const formData = new FormData();

  formData.append("file", file);

  if (additionalData) {
    Object.entries(additionalData).forEach(([key, value]) => {
      // Skip undefined and null values
      if (value === undefined || value === null) {
        return;
      }
      formData.append(
        key,
        typeof value === "string" ? value : JSON.stringify(value)
      );
    });
  }

  const workspaceId =
    typeof window !== "undefined"
      ? localStorage.getItem("current_workspace_id")
      : null;

  const headers: Record<string, string> = {};

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  // Add CSRF token for file uploads (POST request)
  try {
    const csrf = await getCsrfToken();
    headers["X-CSRF-Token"] = csrf;
  } catch (error) {
    // If CSRF token fetch fails, continue anyway (might be unauthenticated request)
    console.warn("Failed to get CSRF token:", error);
  }

  if (workspaceId) {
    headers["X-Workspace-Id"] = workspaceId;
  }

  const url = endpoint.startsWith("http")
    ? endpoint
    : `${BACKEND_URL}${endpoint}`;

  // Create AbortController for timeout (longer timeout for file uploads)
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 120000); // 2 minute timeout for uploads
  const uploadStartTime = Date.now();

  console.log(
    `[API_CLIENT] Starting file upload: ${endpoint}, file size: ${(
      file.size /
      1024 /
      1024
    ).toFixed(2)}MB`
  );

  try {
    const response = await fetch(url, {
      method: "POST",
      headers,
      body: formData,
      credentials: "include",
      signal: controller.signal,
    });

    clearTimeout(timeoutId);
    const uploadTime = Date.now() - uploadStartTime;
    console.log(
      `[API_CLIENT] Upload completed: ${endpoint} - ${response.status} in ${uploadTime}ms`
    );

    if (!response.ok) {
      let errorData: any;
      try {
        errorData = await response.json();
      } catch {
        errorData = {
          message: `HTTP ${response.status}: ${response.statusText}`,
        };
      }

      // FastAPI returns errors with "detail" field, not "message"
      const errorMessage =
        errorData.detail || errorData.message || "File upload failed";

      throw new ApiClientError(
        errorMessage,
        response.status,
        errorData.code,
        errorData
      );
    }

    const contentType = response.headers.get("content-type");
    if (!contentType || !contentType.includes("application/json")) {
      return {} as T;
    }

    return response.json();
  } catch (error: any) {
    clearTimeout(timeoutId);
    const uploadTime = Date.now() - uploadStartTime;

    // Handle timeout/abort errors
    if (error.name === "AbortError" || controller.signal.aborted) {
      console.error(
        `[API_CLIENT] Upload timeout after ${uploadTime}ms: ${endpoint}`
      );
      throw new ApiClientError(
        "Upload timeout: The server took too long to respond",
        408,
        "TIMEOUT"
      );
    }

    console.error(
      `[API_CLIENT] Upload failed after ${uploadTime}ms: ${endpoint}`,
      error
    );

    // Re-throw ApiClientError as-is
    if (error instanceof ApiClientError) {
      throw error;
    }

    // Wrap other errors
    throw new ApiClientError(
      error.message || "File upload failed",
      undefined,
      undefined,
      error
    );
  }
}
