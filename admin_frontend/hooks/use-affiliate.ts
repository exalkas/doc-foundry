import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { get, post } from "@/lib/api-client";
import type { Affiliate } from "@/lib/types";

export function useAffiliate(id: string) {
  return useQuery<Affiliate>({
    queryKey: ["admin", "affiliate", id],
    queryFn: () => get(`/api/admin/affiliates/${id}`),
    enabled: !!id,
  });
}

export function useApproveAffiliate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, notes }: { id: string; notes?: string }) =>
      post(`/api/admin/affiliates/${id}/approve`, { notes }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "affiliates"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "affiliate"] });
    },
  });
}

export function useRejectAffiliate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, notes }: { id: string; notes?: string }) =>
      post(`/api/admin/affiliates/${id}/reject`, { notes }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "affiliates"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "affiliate"] });
    },
  });
}

export function useBlockAffiliate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, notes }: { id: string; notes?: string }) =>
      post(`/api/admin/affiliates/${id}/block`, { notes }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "affiliates"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "affiliate"] });
    },
  });
}
