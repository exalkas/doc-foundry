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
import { useRetryDelivery } from "@/hooks/use-retry-delivery";
import { useToast } from "@/hooks/use-toast";
import { getErrorMessage } from "@/constants/api";
import { ApiClientError } from "@/lib/api-client";

interface RetryDeliveryModalProps {
  deliveryId: string;
  webhookUrl: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Modal component for retrying a webhook delivery
 *
 * Shows a confirmation dialog before retrying a failed webhook delivery.
 *
 * @example
 * ```tsx
 * <RetryDeliveryModal
 *   deliveryId="delivery-123"
 *   webhookUrl="https://example.com/webhook"
 *   open={isOpen}
 *   onOpenChange={setIsOpen}
 * />
 * ```
 */
export function RetryDeliveryModal({
  deliveryId,
  webhookUrl,
  open,
  onOpenChange,
}: RetryDeliveryModalProps) {
  const retryMutation = useRetryDelivery();
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      await retryMutation.mutateAsync({ id: deliveryId });

      toast({
        title: "Delivery retried",
        description: `Webhook delivery to ${webhookUrl} has been queued for retry`,
      });

      onOpenChange(false);
    } catch (error: unknown) {
      const apiError =
        error instanceof ApiClientError
          ? error
          : new ApiClientError("An unexpected error occurred");
      toast({
        title: "Failed to retry delivery",
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
            <DialogTitle>Retry Webhook Delivery</DialogTitle>
            <DialogDescription>
              Are you sure you want to retry this webhook delivery to{" "}
              <strong>{webhookUrl}</strong>? This will queue a new delivery
              attempt.
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
              {retryMutation.isPending ? "Retrying..." : "Retry Delivery"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
