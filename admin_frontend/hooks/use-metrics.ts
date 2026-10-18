import { useQuery } from "@tanstack/react-query";
import { API_CONFIG } from "@/constants/api";
import { get } from "@/lib/api-client";

export interface Metrics {
  queue_depth: number;
  avg_processing_time_ms: number | null;
  daily_documents_processed: number;
  errors_last_24h: number;
  trends_7d: {
    documents_processed: Array<{ date: string; count: number }>;
    jobs_failed: Array<{ date: string; count: number }>;
    jobs_succeeded: Array<{ date: string; count: number }>;
  };
  trends_30d: {
    documents_processed: Array<{ week_start: string; count: number }>;
    jobs_failed: Array<{ week_start: string; count: number }>;
    jobs_succeeded: Array<{ week_start: string; count: number }>;
  };
}

/**
 * Fetches system metrics
 */
export function useMetrics() {
  return useQuery<Metrics>({
    queryKey: ["admin", "metrics"],
    queryFn: async () => {
      const data = await get<Metrics>("/api/admin/metrics");
      return (
        data || {
          queue_depth: 0,
          avg_processing_time_ms: null,
          daily_documents_processed: 0,
          errors_last_24h: 0,
          trends_7d: {
            documents_processed: [],
            jobs_failed: [],
            jobs_succeeded: [],
          },
          trends_30d: {
            documents_processed: [],
            jobs_failed: [],
            jobs_succeeded: [],
          },
        }
      );
    },
    staleTime: 30000, // 30 seconds for real-time updates
    refetchInterval: 30000, // Poll every 30 seconds
  });
}
