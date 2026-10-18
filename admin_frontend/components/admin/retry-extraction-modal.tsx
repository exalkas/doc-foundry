"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useRetryExtraction } from "@/hooks/use-retry-extraction";
import { useToast } from "@/hooks/use-toast";
import { getErrorMessage } from "@/constants/api";
import { ApiClientError } from "@/lib/api-client";

interface RetryExtractionModalProps {
  documentId: string;
  documentName: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Modal component for retrying document extraction
 *
 * Shows a confirmation dialog before retrying extraction.
 *
 * @example
 * ```tsx
 * <RetryExtractionModal
 *   documentId="document-123"
 *   documentName="Invoice.pdf"
 *   open={isOpen}
 *   onOpenChange={setIsOpen}
 * />
 * ```
 */
export function RetryExtractionModal({
  documentId,
  documentName,
  open,
  onOpenChange,
}: RetryExtractionModalProps) {
  const retryMutation = useRetryExtraction();
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      await retryMutation.mutateAsync({ id: documentId });

      toast({
        title: "Extraction retried",
        description: `Extraction for ${documentName} has been queued for retry`,
      });

      onOpenChange(false);
    } catch (error: unknown) {
      const apiError =
        error instanceof ApiClientError
          ? error
          : new ApiClientError("An unexpected error occurred");
      toast({
        title: "Failed to retry extraction",
        description: getErrorMessage(apiError),
        variant: "destructive",
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Retry Document Extraction</DialogTitle>
            <DialogDescription>
              Are you sure you want to retry extraction for{" "}
              <strong>{documentName}</strong>? This will queue a new extraction
              job.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={retryMutation.isPending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={retryMutation.isPending}>
              {retryMutation.isPending ? "Retrying..." : "Retry Extraction"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
