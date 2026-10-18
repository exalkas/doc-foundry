import { useQuery } from "@tanstack/react-query";
import { get } from "@/lib/api-client";
import type { UsageAnalytics } from "@/lib/types";

export function useWorkspaceAnalytics(workspaceId: string, days: number = 90) {
  return useQuery<UsageAnalytics>({
    queryKey: ["admin", "workspace", workspaceId, "analytics", days],
    queryFn: () =>
      get(`/api/admin/workspaces/${workspaceId}/usage-analytics?days=${days}`),
    enabled: !!workspaceId,
  });
}
