import { useQuery } from "@tanstack/react-query";
import { API_CONFIG } from "@/constants/api";
import { PAGINATION } from "@/constants/pagination";
import { get } from "@/lib/api-client";
import type { Workspace, PaginatedResponse } from "@/lib/types";
import { validateWorkspaces } from "@/lib/validation";

interface UseWorkspacesParams {
  status?: "active" | "suspended" | "trial" | "canceled";
  page?: number;
  page_size?: number;
  search?: string;
}

/**
 * Fetches workspaces with optional filtering and pagination
 *
 * @param params - Query parameters
 * @param params.status - Filter by workspace status (active, suspended, trial, canceled)
 * @param params.page - Page number (default: 1)
 * @param params.page_size - Items per page (default: 50)
 * @returns React Query hook result with workspaces data
 *
 * @example
 * ```tsx
 * const { data, isLoading } = useWorkspaces({ status: "active", page: 1 });
 * ```
 */
export function useWorkspaces(params?: UseWorkspacesParams) {
  const {
    status,
    page = 1,
    page_size = PAGINATION.DEFAULT_PAGE_SIZE,
    search,
  } = params || {};

  const queryParams = new URLSearchParams();
  if (status) queryParams.append("status", status);
  if (search && search.trim()) {
    queryParams.append("search", search.trim());
  }
  queryParams.append("page", page.toString());
  queryParams.append("page_size", page_size.toString());

  const endpoint = `/api/admin/workspaces?${queryParams.toString()}`;

  return useQuery<Workspace[] | PaginatedResponse<Workspace>>({
    queryKey: ["admin", "workspaces", status, page, page_size, search],
    queryFn: async () => {
      const data = await get<Workspace[] | PaginatedResponse<Workspace>>(
        endpoint
      );

      // Handle paginated response format
      if (data && typeof data === "object" && "items" in data) {
        const paginatedData = data as PaginatedResponse<Workspace>;
        // Runtime validation (only in development)
        if (process.env.NODE_ENV === "development") {
          try {
            return {
              ...paginatedData,
              items: validateWorkspaces(paginatedData.items),
            };
          } catch (error) {
            console.error("Workspace validation error:", error);
            return paginatedData;
          }
        }
        return paginatedData;
      }

      // Handle array response format (legacy/fallback)
      const arrayData = data as Workspace[];
      if (process.env.NODE_ENV === "development") {
        try {
          return validateWorkspaces(arrayData);
        } catch (error) {
          console.error("Workspace validation error:", error);
          return arrayData;
        }
      }
      return arrayData;
    },
    staleTime: API_CONFIG.STALE_TIME,
  });
}
