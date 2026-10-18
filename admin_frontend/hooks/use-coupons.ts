import { useQuery } from "@tanstack/react-query";
import { PAGINATION } from "@/constants/pagination";
import { get } from "@/lib/api-client";
import type { Coupon } from "@/lib/types";

interface UseCouponsParams {
  status?: "active" | "paused" | "expired";
  affiliate_id?: string;
  plan_id?: string;
  page?: number;
  page_size?: number;
}

export function useCoupons(params?: UseCouponsParams) {
  const {
    status,
    affiliate_id,
    plan_id,
    page = 1,
    page_size = PAGINATION.DEFAULT_PAGE_SIZE,
  } = params || {};

  const queryParams = new URLSearchParams();
  if (status) queryParams.append("status", status);
  if (affiliate_id) queryParams.append("affiliate_id", affiliate_id);
  if (plan_id) queryParams.append("plan_id", plan_id);
  queryParams.append("page", page.toString());
  queryParams.append("page_size", page_size.toString());

  const endpoint = `/api/admin/coupons?${queryParams.toString()}`;

  return useQuery<Coupon[]>({
    queryKey: ["admin", "coupons", status, affiliate_id, plan_id, page, page_size],
    queryFn: () => get(endpoint),
    staleTime: 30 * 1000, // 30 seconds
  });
}

