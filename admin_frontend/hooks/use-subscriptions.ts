import { useQuery } from "@tanstack/react-query";
import { API_CONFIG } from "@/constants/api";
import { PAGINATION } from "@/constants/pagination";
import { get } from "@/lib/api-client";
import type { Subscription, PaginatedResponse } from "@/lib/types";

interface UseSubscriptionsParams {
  plan?: string;
  status?:
    | "active"
    | "canceled"
    | "past_due"
    | "trialing"
    | "incomplete"
    | "incomplete_expired";
  page?: number;
  page_size?: number;
}

/**
 * Fetches subscriptions with optional filtering and pagination
 *
 * @param params - Query parameters
 * @param params.plan - Filter by plan name
 * @param params.status - Filter by subscription status
 * @param params.page - Page number (default: 1)
 * @param params.page_size - Items per page (default: 50)
 * @returns React Query hook result with subscriptions data
 *
 * @example
 * ```tsx
 * const { data, isLoading } = useSubscriptions({ status: "active", page: 1 });
 * ```
 */
export function useSubscriptions(params?: UseSubscriptionsParams) {
  const {
    plan,
    status,
    page = 1,
    page_size = PAGINATION.DEFAULT_PAGE_SIZE,
  } = params || {};

  const queryParams = new URLSearchParams();
  if (plan) queryParams.append("plan", plan);
  if (status) queryParams.append("status", status);
  queryParams.append("page", page.toString());
  queryParams.append("page_size", page_size.toString());

  const endpoint = `/api/admin/subscriptions?${queryParams.toString()}`;

  return useQuery<Subscription[] | PaginatedResponse<Subscription>>({
    queryKey: ["admin", "subscriptions", plan, status, page, page_size],
    queryFn: async () => {
      const data = await get<Subscription[] | PaginatedResponse<Subscription>>(
        endpoint
      );

      // Handle paginated response format
      if (data && typeof data === "object" && "items" in data) {
        return data as PaginatedResponse<Subscription>;
      }

      // Handle array response format (legacy/fallback)
      return data as Subscription[];
    },
    staleTime: API_CONFIG.STALE_TIME,
  });
}
