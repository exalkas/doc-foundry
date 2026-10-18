import { useQuery } from "@tanstack/react-query";
import { get } from "@/lib/api-client";
import type { OCRBlock } from "@/lib/types";

export interface OCRData {
  blocks: OCRBlock[];
  page_count: number;
  image_dimensions?: {
    width: number;
    height: number;
  };
}

export function useDocumentOCR(
  templateId: string | undefined,
  documentId: string | undefined
) {
  return useQuery<OCRData>({
    queryKey: ["ocr-data", templateId, documentId],
    queryFn: async () => {
      if (!templateId || !documentId) {
        throw new Error("Template ID and Document ID are required");
      }
      return await get<OCRData>(
        `/api/templates/${templateId}/ocr-data?document_id=${documentId}`
      );
    },
    enabled: !!templateId && !!documentId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}
