import { useMutation, useQueryClient } from "@tanstack/react-query";
import { post } from "@/lib/api-client";

/**
 * Mutation hook to retry document extraction
 *
 * @returns React Query mutation for retrying document extraction
 *
 * @example
 * ```tsx
 * const retryMutation = useRetryExtraction();
 * await retryMutation.mutateAsync({ id: "document-123" });
 * ```
 */
export function useRetryExtraction() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id }: { id: string }) =>
      post(`/api/admin/documents/${id}/retry`),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["admin", "documents"] });
      queryClient.invalidateQueries({
        queryKey: ["admin", "document", variables.id],
      });
    },
  });
}
