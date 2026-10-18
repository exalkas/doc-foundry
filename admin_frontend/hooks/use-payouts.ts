import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { PAGINATION } from "@/constants/pagination";
import { get, post } from "@/lib/api-client";
import type { Payout } from "@/lib/types";

interface UsePayoutsParams {
  status?: "requested" | "approved" | "paid" | "rejected";
  page?: number;
  page_size?: number;
}

export function usePayouts(params?: UsePayoutsParams) {
  const {
    status,
    page = 1,
    page_size = PAGINATION.DEFAULT_PAGE_SIZE,
  } = params || {};

  const queryParams = new URLSearchParams();
  if (status) queryParams.append("status", status);
  queryParams.append("page", page.toString());
  queryParams.append("page_size", page_size.toString());

  const endpoint = `/api/admin/affiliates/payouts/list?${queryParams.toString()}`;

  return useQuery<Payout[]>({
    queryKey: ["admin", "payouts", status, page, page_size],
    queryFn: () => get(endpoint),
    staleTime: 30 * 1000, // 30 seconds
  });
}

export function useApprovePayout() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      id,
      payment_reference,
      notes,
    }: {
      id: string;
      payment_reference?: string;
      notes?: string;
    }) =>
      post(`/api/admin/affiliates/payouts/${id}/approve`, {
        payment_reference,
        notes,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "payouts"] });
    },
  });
}

export function useMarkPayoutPaid() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      id,
      payment_reference,
      notes,
    }: {
      id: string;
      payment_reference?: string;
      notes?: string;
    }) =>
      post(`/api/admin/affiliates/payouts/${id}/pay`, {
        payment_reference,
        notes,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "payouts"] });
    },
  });
}

export function useRejectPayout() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      post(`/api/admin/affiliates/payouts/${id}/reject`, { reason }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "payouts"] });
    },
  });
}
