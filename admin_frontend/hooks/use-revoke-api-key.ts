import { useMutation, useQueryClient } from "@tanstack/react-query";
import { post } from "@/lib/api-client";

/**
 * Mutation hook to revoke an API key
 *
 * @returns React Query mutation for revoking an API key
 *
 * @example
 * ```tsx
 * const revokeMutation = useRevokeApiKey();
 * await revokeMutation.mutateAsync({ id: "api-key-123" });
 * ```
 */
export function useRevokeApiKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id }: { id: string }) =>
      post(`/api/admin/api-keys/${id}/revoke`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "api-keys"] });
    },
  });
}
