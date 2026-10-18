import { useQuery } from "@tanstack/react-query";
import { get } from "@/lib/api-client";
import type { Subscription } from "@/lib/types";

/**
 * Fetches a single subscription by ID
 *
 * @param id - Subscription ID
 * @returns React Query hook result with subscription data
 *
 * @example
 * ```tsx
 * const { data: subscription, isLoading } = useSubscription("subscription-123");
 * ```
 */
export function useSubscription(id: string) {
  return useQuery<Subscription | undefined>({
    queryKey: ["admin", "subscription", id],
    queryFn: async () => {
      const data = await get<Subscription>(`/api/admin/subscriptions/${id}`);
      return data;
    },
    enabled: !!id,
    // Don't retry on 404 - subscription doesn't exist
    retry: (failureCount, error: any) => {
      if (error?.status === 404) {
        return false;
      }
      return failureCount < 2;
    },
  });
}
