import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { get, post, patch, del } from "@/lib/api-client";
import type { Coupon } from "@/lib/types";

export function useCoupon(id: string) {
  return useQuery<Coupon>({
    queryKey: ["admin", "coupon", id],
    queryFn: () => get(`/api/admin/coupons/${id}`),
    enabled: !!id,
  });
}

export function useCreateCoupon() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: any) => post("/api/admin/coupons", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "coupons"] });
    },
  });
}

export function useUpdateCoupon() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      patch(`/api/admin/coupons/${id}`, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["admin", "coupons"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "coupon", variables.id] });
    },
  });
}

export function useDeleteCoupon() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => del(`/api/admin/coupons/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "coupons"] });
    },
  });
}

