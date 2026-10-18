import { useQuery } from "@tanstack/react-query";
import { API_CONFIG } from "@/constants/api";
import { PAGINATION } from "@/constants/pagination";
import { get } from "@/lib/api-client";
import type { ApiKey, PaginatedResponse } from "@/lib/types";

interface UseApiKeysParams {
  workspace_id?: string;
  status?: "active" | "revoked";
  page?: number;
  page_size?: number;
}

/**
 * Fetches API keys with optional filtering and pagination
 *
 * @param params - Query parameters
 * @param params.workspace_id - Filter by workspace ID
 * @param params.status - Filter by API key status
 * @param params.page - Page number (default: 1)
 * @param params.page_size - Items per page (default: 50)
 * @returns React Query hook result with API keys data
 *
 * @example
 * ```tsx
 * const { data, isLoading } = useApiKeys({ status: "active", page: 1 });
 * ```
 */
export function useApiKeys(params?: UseApiKeysParams) {
  const {
    workspace_id,
    status,
    page = 1,
    page_size = PAGINATION.DEFAULT_PAGE_SIZE,
  } = params || {};

  const queryParams = new URLSearchParams();
  if (workspace_id) queryParams.append("workspace_id", workspace_id);
  if (status) queryParams.append("status", status);
  queryParams.append("page", page.toString());
  queryParams.append("page_size", page_size.toString());

  const endpoint = `/api/admin/api-keys?${queryParams.toString()}`;

  return useQuery<ApiKey[] | PaginatedResponse<ApiKey>>({
    queryKey: ["admin", "api-keys", workspace_id, status, page, page_size],
    queryFn: async () => {
      const data = await get<ApiKey[] | PaginatedResponse<ApiKey>>(endpoint);

      // Handle paginated response format
      if (data && typeof data === "object" && "items" in data) {
        return data as PaginatedResponse<ApiKey>;
      }

      // Handle array response format (legacy/fallback)
      return data as ApiKey[];
    },
    staleTime: API_CONFIG.STALE_TIME,
  });
}
