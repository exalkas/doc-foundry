import { useQuery } from "@tanstack/react-query";
import { API_CONFIG } from "@/constants/api";
import { PAGINATION } from "@/constants/pagination";
import { get } from "@/lib/api-client";
import type { WebhookDelivery, PaginatedResponse } from "@/lib/types";

interface UseWebhookDeliveriesParams {
  webhook_id: string;
  status?: "pending" | "success" | "failed";
  page?: number;
  page_size?: number;
}

/**
 * Fetches webhook deliveries for a specific webhook
 *
 * @param params - Query parameters
 * @param params.webhook_id - Webhook ID (required)
 * @param params.status - Filter by delivery status
 * @param params.page - Page number (default: 1)
 * @param params.page_size - Items per page (default: 50)
 * @returns React Query hook result with deliveries data
 *
 * @example
 * ```tsx
 * const { data, isLoading } = useWebhookDeliveries({ webhook_id: "webhook-123" });
 * ```
 */
export function useWebhookDeliveries(params: UseWebhookDeliveriesParams) {
  const {
    webhook_id,
    status,
    page = 1,
    page_size = PAGINATION.DEFAULT_PAGE_SIZE,
  } = params;

  const queryParams = new URLSearchParams();
  if (status) queryParams.append("status", status);
  queryParams.append("page", page.toString());
  queryParams.append("page_size", page_size.toString());

  const endpoint = `/api/admin/webhooks/${webhook_id}/deliveries?${queryParams.toString()}`;

  return useQuery<WebhookDelivery[] | PaginatedResponse<WebhookDelivery>>({
    queryKey: [
      "admin",
      "webhook-deliveries",
      webhook_id,
      status,
      page,
      page_size,
    ],
    queryFn: async () => {
      const data = await get<
        WebhookDelivery[] | PaginatedResponse<WebhookDelivery>
      >(endpoint);

      // Handle paginated response format
      if (data && typeof data === "object" && "items" in data) {
        return data as PaginatedResponse<WebhookDelivery>;
      }

      // Handle array response format (legacy/fallback)
      return data as WebhookDelivery[];
    },
    enabled: !!webhook_id,
    staleTime: API_CONFIG.STALE_TIME,
  });
}
