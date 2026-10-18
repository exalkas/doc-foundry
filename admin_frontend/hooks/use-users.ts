import { useQuery } from "@tanstack/react-query";
import { PAGINATION } from "@/constants/pagination";
import { get } from "@/lib/api-client";
import type { User } from "@/lib/types";
import { validateUsers } from "@/lib/validation";

interface UseUsersParams {
  role?: "admin" | "owner" | "member" | "readonly";
  page?: number;
  page_size?: number;
}

/**
 * Fetches users with optional filtering and pagination
 *
 * @param params - Query parameters
 * @param params.role - Filter by user role (admin, owner, member, readonly)
 * @param params.page - Page number (default: 1)
 * @param params.page_size - Items per page (default: 50)
 * @returns React Query hook result with users data
 *
 * @example
 * ```tsx
 * const { data, isLoading } = useUsers({ role: "admin", page: 1 });
 * ```
 */
export function useUsers(params?: UseUsersParams) {
  const {
    role,
    page = 1,
    page_size = PAGINATION.DEFAULT_PAGE_SIZE,
  } = params || {};

  const queryParams = new URLSearchParams();
  if (role) queryParams.append("role", role);
  queryParams.append("page", page.toString());
  queryParams.append("page_size", page_size.toString());

  const endpoint = `/api/admin/users?${queryParams.toString()}`;

  return useQuery<User[]>({
    queryKey: ["admin", "users", role, page, page_size],
    queryFn: async () => {
      const data = await get<User[]>(endpoint);
      // Runtime validation (only in development)
      if (process.env.NODE_ENV === "development") {
        try {
          return validateUsers(data);
        } catch (error) {
          console.error("User validation error:", error);
          // Return data anyway to avoid breaking the app
          return data;
        }
      }
      return data;
    },
    staleTime: 30 * 1000, // 30 seconds
    retry: false, // Don't retry if endpoint doesn't exist
  });
}
