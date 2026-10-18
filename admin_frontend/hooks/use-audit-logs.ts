import { useQuery } from "@tanstack/react-query";
import { API_CONFIG } from "@/constants/api";
import { PAGINATION } from "@/constants/pagination";
import { get } from "@/lib/api-client";

export interface AuditLog {
  id: string;
  workspace_id: string | null;
  user_id: string | null;
  actor_type: string;
  event_type: string;
  description: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

interface UseAuditLogsParams {
  workspace_id?: string;
  actor_type?: string;
  from?: string;
  to?: string;
  page?: number;
  page_size?: number;
}

/**
 * Fetches audit logs with optional filtering and pagination
 */
export function useAuditLogs(params?: UseAuditLogsParams) {
  const {
    workspace_id,
    actor_type,
    from,
    to,
    page = 1,
    page_size = PAGINATION.DEFAULT_PAGE_SIZE,
  } = params || {};

  const queryParams = new URLSearchParams();
  if (workspace_id) queryParams.append("workspace_id", workspace_id);
  if (actor_type) queryParams.append("actor_type", actor_type);
  if (from) queryParams.append("from", from);
  if (to) queryParams.append("to", to);
  queryParams.append("page", page.toString());
  queryParams.append("page_size", page_size.toString());

  const endpoint = `/api/admin/audit-logs?${queryParams.toString()}`;

  return useQuery<AuditLog[]>({
    queryKey: [
      "admin",
      "audit-logs",
      workspace_id,
      actor_type,
      from,
      to,
      page,
      page_size,
    ],
    queryFn: async () => {
      const data = await get<AuditLog[]>(endpoint);
      return data || [];
    },
    staleTime: API_CONFIG.STALE_TIME,
  });
}
