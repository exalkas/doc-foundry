import { useQuery } from "@tanstack/react-query";
import { API_CONFIG } from "@/constants/api";
import { get } from "@/lib/api-client";

export interface Analytics {
  total_workspaces: number;
  active_workspaces: number;
  suspended_workspaces: number;
  active_subscriptions: number;
  total_mrr: number;
  growth_trends: {
    workspaces: Array<{ date: string; count: number }>;
    subscriptions: Array<{ date: string; count: number }>;
  };
}

interface UseAnalyticsParams {
  from?: string;
  to?: string;
}

/**
 * Fetches platform analytics
 */
export function useAnalytics(params?: UseAnalyticsParams) {
  const { from, to } = params || {};

  const queryParams = new URLSearchParams();
  if (from) queryParams.append("from", from);
  if (to) queryParams.append("to", to);

  const endpoint = `/api/admin/analytics${
    queryParams.toString() ? `?${queryParams.toString()}` : ""
  }`;

  return useQuery<Analytics>({
    queryKey: ["admin", "analytics", from, to],
    queryFn: async () => {
      const data = await get<Analytics>(endpoint);
      return (
        data || {
          total_workspaces: 0,
          active_workspaces: 0,
          suspended_workspaces: 0,
          active_subscriptions: 0,
          total_mrr: 0,
          growth_trends: {
            workspaces: [],
            subscriptions: [],
          },
        }
      );
    },
    staleTime: API_CONFIG.STALE_TIME,
  });
}
