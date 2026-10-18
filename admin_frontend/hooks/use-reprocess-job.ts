import { useMutation, useQueryClient } from "@tanstack/react-query";
import { post } from "@/lib/api-client";

/**
 * Mutation hook to reprocess a failed job
 *
 * @returns React Query mutation for reprocessing a job
 *
 * @example
 * ```tsx
 * const reprocessMutation = useReprocessJob();
 * await reprocessMutation.mutateAsync({ id: "job-123" });
 * ```
 */
export function useReprocessJob() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id }: { id: string }) =>
      post(`/api/admin/jobs/${id}/reprocess`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "jobs"] });
    },
  });
}
