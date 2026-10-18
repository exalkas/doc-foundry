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
import { useReprocessJob } from "@/hooks/use-reprocess-job";
import { useToast } from "@/hooks/use-toast";
import { getErrorMessage } from "@/constants/api";
import { ApiClientError } from "@/lib/api-client";

interface ReprocessJobModalProps {
  jobId: string;
  jobType: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Modal component for reprocessing a failed job
 *
 * Shows a confirmation dialog before reprocessing a job.
 *
 * @example
 * ```tsx
 * <ReprocessJobModal
 *   jobId="job-123"
 *   jobType="document_extraction"
 *   open={isOpen}
 *   onOpenChange={setIsOpen}
 * />
 * ```
 */
export function ReprocessJobModal({
  jobId,
  jobType,
  open,
  onOpenChange,
}: ReprocessJobModalProps) {
  const reprocessMutation = useReprocessJob();
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      await reprocessMutation.mutateAsync({ id: jobId });

      toast({
        title: "Job reprocessed",
        description: `Job ${jobType.replace(
          "_",
          " "
        )} has been queued for reprocessing`,
      });

      onOpenChange(false);
    } catch (error: unknown) {
      const apiError =
        error instanceof ApiClientError
          ? error
          : new ApiClientError("An unexpected error occurred");
      toast({
        title: "Failed to reprocess job",
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
            <DialogTitle>Reprocess Job</DialogTitle>
            <DialogDescription>
              Are you sure you want to reprocess this{" "}
              {jobType.replace("_", " ")} job? This will reset the job status
              and queue it for processing again.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={reprocessMutation.isPending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={reprocessMutation.isPending}>
              {reprocessMutation.isPending
                ? "Reprocessing..."
                : "Reprocess Job"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
