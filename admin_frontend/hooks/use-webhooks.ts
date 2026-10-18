import { useQuery } from "@tanstack/react-query";
import { API_CONFIG } from "@/constants/api";
import { PAGINATION } from "@/constants/pagination";
import { get } from "@/lib/api-client";
import type { Webhook, PaginatedResponse } from "@/lib/types";

interface UseWebhooksParams {
  workspace_id?: string;
  status?: "active" | "inactive" | "failed";
  page?: number;
  page_size?: number;
}

/**
 * Fetches webhooks with optional filtering and pagination
 *
 * @param params - Query parameters
 * @param params.workspace_id - Filter by workspace ID
 * @param params.status - Filter by webhook status
 * @param params.page - Page number (default: 1)
 * @param params.page_size - Items per page (default: 50)
 * @returns React Query hook result with webhooks data
 *
 * @example
 * ```tsx
 * const { data, isLoading } = useWebhooks({ status: "active", page: 1 });
 * ```
 */
export function useWebhooks(params?: UseWebhooksParams) {
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

  const endpoint = `/api/admin/webhooks?${queryParams.toString()}`;

  return useQuery<Webhook[] | PaginatedResponse<Webhook>>({
    queryKey: ["admin", "webhooks", workspace_id, status, page, page_size],
    queryFn: async () => {
      const data = await get<Webhook[] | PaginatedResponse<Webhook>>(endpoint);

      // Handle paginated response format
      if (data && typeof data === "object" && "items" in data) {
        return data as PaginatedResponse<Webhook>;
      }

      // Handle array response format (legacy/fallback)
      return data as Webhook[];
    },
    staleTime: API_CONFIG.STALE_TIME,
  });
}
