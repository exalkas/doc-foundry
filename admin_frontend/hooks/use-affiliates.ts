import { useQuery } from "@tanstack/react-query";
import { PAGINATION } from "@/constants/pagination";
import { get } from "@/lib/api-client";
import type { Affiliate } from "@/lib/types";

interface UseAffiliatesParams {
  status?: "pending" | "approved" | "rejected" | "blocked";
  page?: number;
  page_size?: number;
}

export function useAffiliates(params?: UseAffiliatesParams) {
  const {
    status,
    page = 1,
    page_size = PAGINATION.DEFAULT_PAGE_SIZE,
  } = params || {};

  const queryParams = new URLSearchParams();
  if (status) queryParams.append("status", status);
  queryParams.append("page", page.toString());
  queryParams.append("page_size", page_size.toString());

  const endpoint = `/api/admin/affiliates?${queryParams.toString()}`;

  return useQuery<Affiliate[]>({
    queryKey: ["admin", "affiliates", status, page, page_size],
    queryFn: () => get(endpoint),
    staleTime: 30 * 1000, // 30 seconds
  });
}
