import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { PAGINATION } from "@/constants/pagination";
import { get, post } from "@/lib/api-client";
import type { Commission } from "@/lib/types";

interface UseCommissionsParams {
  affiliate_id?: string;
  status?: "pending" | "cleared" | "paid" | "reversed";
  page?: number;
  page_size?: number;
}

export function useCommissions(params?: UseCommissionsParams) {
  const {
    affiliate_id,
    status,
    page = 1,
    page_size = PAGINATION.DEFAULT_PAGE_SIZE,
  } = params || {};

  const queryParams = new URLSearchParams();
  if (affiliate_id) queryParams.append("affiliate_id", affiliate_id);
  if (status) queryParams.append("status", status);
  queryParams.append("page", page.toString());
  queryParams.append("page_size", page_size.toString());

  const endpoint = `/api/admin/affiliates/commissions/list?${queryParams.toString()}`;

  return useQuery<Commission[]>({
    queryKey: ["admin", "commissions", affiliate_id, status, page, page_size],
    queryFn: () => get(endpoint),
    staleTime: 30 * 1000, // 30 seconds
  });
}

export function useAdjustCommission() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      id,
      amount,
      reason,
    }: {
      id: string;
      amount: number;
      reason: string;
    }) =>
      post(`/api/admin/affiliates/commissions/${id}/adjust`, {
        amount,
        reason,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "commissions"] });
    },
  });
}
