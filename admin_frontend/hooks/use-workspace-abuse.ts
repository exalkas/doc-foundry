import { useQuery } from "@tanstack/react-query";
import { get } from "@/lib/api-client";
import type { AbuseDetection } from "@/lib/types";

export function useWorkspaceAbuse(workspaceId: string) {
  return useQuery<AbuseDetection>({
    queryKey: ["admin", "workspace", workspaceId, "abuse"],
    queryFn: () => get(`/api/admin/workspaces/${workspaceId}/abuse-detection`),
    enabled: !!workspaceId,
  });
}
