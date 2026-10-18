import { useQuery } from "@tanstack/react-query";
import { API_CONFIG } from "@/constants/api";
import { PAGINATION } from "@/constants/pagination";
import { get } from "@/lib/api-client";
import type { Job, PaginatedResponse } from "@/lib/types";

interface UseJobsParams {
  type?: "document_extraction" | "webhook_delivery" | "email_send" | "other";
  status?: "queued" | "processing" | "completed" | "failed";
  page?: number;
  page_size?: number;
}

/**
 * Fetches jobs with optional filtering and pagination
 *
 * @param params - Query parameters
 * @param params.type - Filter by job type
 * @param params.status - Filter by job status
 * @param params.page - Page number (default: 1)
 * @param params.page_size - Items per page (default: 50)
 * @returns React Query hook result with jobs data
 *
 * @example
 * ```tsx
 * const { data, isLoading } = useJobs({ status: "failed", page: 1 });
 * ```
 */
export function useJobs(params?: UseJobsParams) {
  const {
    type,
    status,
    page = 1,
    page_size = PAGINATION.DEFAULT_PAGE_SIZE,
  } = params || {};

  const queryParams = new URLSearchParams();
  if (type) queryParams.append("type", type);
  if (status) queryParams.append("status", status);
  queryParams.append("page", page.toString());
  queryParams.append("page_size", page_size.toString());

  const endpoint = `/api/admin/jobs?${queryParams.toString()}`;

  return useQuery<Job[] | PaginatedResponse<Job>>({
    queryKey: ["admin", "jobs", type, status, page, page_size],
    queryFn: async () => {
      const data = await get<Job[] | PaginatedResponse<Job>>(endpoint);

      // Handle paginated response format
      if (data && typeof data === "object" && "items" in data) {
        return data as PaginatedResponse<Job>;
      }

      // Handle array response format (legacy/fallback)
      return data as Job[];
    },
    staleTime: API_CONFIG.STALE_TIME,
  });
}
