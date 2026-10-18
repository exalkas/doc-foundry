import { useQuery } from "@tanstack/react-query";
import { get } from "@/lib/api-client";
import type { User } from "@/lib/types";

export function useUser(id: string) {
  return useQuery<User>({
    queryKey: ["admin", "user", id],
    queryFn: () => get(`/api/admin/users/${id}`),
    enabled: !!id,
    retry: false, // Don't retry if endpoint doesn't exist
  });
}
