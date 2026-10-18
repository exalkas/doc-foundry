import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { get, post } from "@/lib/api-client";
import type { Workspace } from "@/lib/types";
import { validateWorkspace } from "@/lib/validation";

/**
 * Fetches a single workspace by ID
 *
 * **Note:** This hook requires the backend endpoint `/api/admin/workspaces/{id}` to be implemented.
 * The inefficient fallback to fetching all workspaces has been removed for better performance.
 *
 * @param id - Workspace ID
 * @returns React Query hook result with workspace data
 *
 * @example
 * ```tsx
 * const { data: workspace, isLoading } = useWorkspace("workspace-123");
 * ```
 */
export function useWorkspace(id: string) {
  return useQuery<Workspace | undefined>({
    queryKey: ["admin", "workspace", id],
    queryFn: async () => {
      const data = await get<Workspace>(`/api/admin/workspaces/${id}`);
      // Runtime validation (only in development)
      if (process.env.NODE_ENV === "development") {
        try {
          return validateWorkspace(data);
        } catch (validationError) {
          console.error("Workspace validation error:", validationError);
          // Return data anyway to avoid breaking the app
          return data;
        }
      }
      return data;
    },
    enabled: !!id,
    // Don't retry on 404 - workspace doesn't exist
    retry: (failureCount, error: any) => {
      if (error?.status === 404) {
        return false;
      }
      return failureCount < 2;
    },
  });
}

/**
 * Mutation hook to suspend a workspace
 *
 * @returns React Query mutation for suspending a workspace
 *
 * @example
 * ```tsx
 * const suspendMutation = useSuspendWorkspace();
 * await suspendMutation.mutateAsync({ id: "workspace-123", reason: "Violation of terms" });
 * ```
 */
export function useSuspendWorkspace() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => {
      const params = new URLSearchParams();
      if (reason) params.append("reason", reason);
      return post(`/api/admin/workspaces/${id}/suspend?${params.toString()}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "workspaces"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "workspace"] });
    },
  });
}

/**
 * Mutation hook to unsuspend a workspace
 *
 * @returns React Query mutation for unsuspending a workspace
 *
 * @example
 * ```tsx
 * const unsuspendMutation = useUnsuspendWorkspace();
 * await unsuspendMutation.mutateAsync({ id: "workspace-123" });
 * ```
 */
export function useUnsuspendWorkspace() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id }: { id: string }) =>
      post(`/api/admin/workspaces/${id}/unsuspend`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "workspaces"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "workspace"] });
    },
  });
}

/**
 * Mutation hook to impersonate a workspace owner
 *
 * @returns React Query mutation that returns an impersonation token
 *
 * @example
 * ```tsx
 * const impersonateMutation = useImpersonateWorkspace();
 * const { token } = await impersonateMutation.mutateAsync({ id: "workspace-123" });
 * ```
 */
export function useImpersonateWorkspace() {
  return useMutation({
    mutationFn: ({ id }: { id: string }) =>
      post<{ token: string }>(`/api/admin/workspaces/${id}/impersonate-owner`),
  });
}
