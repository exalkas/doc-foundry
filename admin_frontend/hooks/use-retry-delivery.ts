import { useMutation, useQueryClient } from "@tanstack/react-query";
import { post } from "@/lib/api-client";

/**
 * Mutation hook to retry a webhook delivery
 *
 * @returns React Query mutation for retrying a webhook delivery
 *
 * @example
 * ```tsx
 * const retryMutation = useRetryDelivery();
 * await retryMutation.mutateAsync({ id: "delivery-123" });
 * ```
 */
export function useRetryDelivery() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id }: { id: string }) =>
      post(`/api/admin/webhook-deliveries/${id}/retry`),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["admin", "webhook-deliveries"],
      });
    },
  });
}
