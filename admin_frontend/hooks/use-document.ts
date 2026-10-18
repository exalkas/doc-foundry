import { useQuery } from "@tanstack/react-query";
import { get } from "@/lib/api-client";
import type { Document } from "@/lib/types";

/**
 * Fetches a single document by ID
 *
 * @param id - Document ID
 * @returns React Query hook result with document data
 *
 * @example
 * ```tsx
 * const { data: document, isLoading } = useDocument("document-123");
 * ```
 */
export function useDocument(id: string) {
  return useQuery<Document | undefined>({
    queryKey: ["admin", "document", id],
    queryFn: async () => {
      const data = await get<Document>(`/api/admin/documents/${id}`);
      return data;
    },
    enabled: !!id,
    // Don't retry on 404 - document doesn't exist
    retry: (failureCount, error: any) => {
      if (error?.status === 404) {
        return false;
      }
      return failureCount < 2;
    },
  });
}
