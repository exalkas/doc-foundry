import { useQuery } from "@tanstack/react-query";
import { API_CONFIG } from "@/constants/api";
import { PAGINATION } from "@/constants/pagination";
import { get } from "@/lib/api-client";
import type { Document, PaginatedResponse } from "@/lib/types";

interface UseDocumentsParams {
  workspace_id?: string;
  status?: "queued" | "processing" | "completed" | "failed";
  page?: number;
  page_size?: number;
  search?: string;
  from_date?: string;
  to_date?: string;
}

/**
 * Fetches documents with optional filtering and pagination
 *
 * @param params - Query parameters
 * @param params.workspace_id - Filter by workspace ID
 * @param params.status - Filter by document status
 * @param params.page - Page number (default: 1)
 * @param params.page_size - Items per page (default: 50)
 * @param params.search - Search by document name
 * @param params.from_date - Filter by start date (ISO 8601)
 * @param params.to_date - Filter by end date (ISO 8601)
 * @returns React Query hook result with documents data
 *
 * @example
 * ```tsx
 * const { data, isLoading } = useDocuments({ status: "failed", page: 1 });
 * ```
 */
export function useDocuments(params?: UseDocumentsParams) {
  const {
    workspace_id,
    status,
    page = 1,
    page_size = PAGINATION.DEFAULT_PAGE_SIZE,
    search,
    from_date,
    to_date,
  } = params || {};

  const queryParams = new URLSearchParams();
  if (workspace_id) queryParams.append("workspace_id", workspace_id);
  if (status) queryParams.append("status", status);
  if (search && search.trim()) {
    queryParams.append("search", search.trim());
  }
  if (from_date) queryParams.append("from", from_date);
  if (to_date) queryParams.append("to", to_date);
  queryParams.append("page", page.toString());
  queryParams.append("page_size", page_size.toString());

  const endpoint = `/api/admin/documents?${queryParams.toString()}`;

  return useQuery<Document[] | PaginatedResponse<Document>>({
    queryKey: [
      "admin",
      "documents",
      workspace_id,
      status,
      page,
      page_size,
      search,
      from_date,
      to_date,
    ],
    queryFn: async () => {
      const data = await get<Document[] | PaginatedResponse<Document>>(
        endpoint
      );

      // Handle paginated response format
      if (data && typeof data === "object" && "items" in data) {
        return data as PaginatedResponse<Document>;
      }

      // Handle array response format (legacy/fallback)
      return data as Document[];
    },
    staleTime: API_CONFIG.STALE_TIME,
  });
}
