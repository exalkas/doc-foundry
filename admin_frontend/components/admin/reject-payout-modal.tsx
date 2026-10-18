"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { useRejectPayout } from "@/hooks/use-payouts";
import { useToast } from "@/hooks/use-toast";
import { formatCurrency } from "@/lib/utils";
import type { Payout } from "@/lib/types";
import { getErrorMessage } from "@/constants/api";
import { ApiClientError } from "@/lib/api-client";

interface RejectPayoutModalProps {
  payout: Payout | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function RejectPayoutModal({
  payout,
  open,
  onOpenChange,
}: RejectPayoutModalProps) {
  const [reason, setReason] = useState("");
  const rejectMutation = useRejectPayout();
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!payout) return;

    if (!reason.trim() || reason.trim().length < 20) {
      toast({
        title: "Reason required",
        description: "Please provide a reason with at least 20 characters",
        variant: "destructive",
      });
      return;
    }

    try {
      await rejectMutation.mutateAsync({
        id: payout.id,
        reason: reason.trim(),
      });

      toast({
        title: "Payout rejected",
        description: `Payout of ${formatCurrency(
          payout.amount,
          payout.currency
        )} has been rejected`,
        variant: "success",
      });

      onOpenChange(false);
      setReason("");
    } catch (error: unknown) {
      const apiError =
        error instanceof ApiClientError
          ? error
          : new ApiClientError("An unexpected error occurred");
      toast({
        title: "Failed to reject payout",
        description: getErrorMessage(apiError),
        variant: "destructive",
      });
    }
  };

  if (!payout) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Reject Payout</DialogTitle>
            <DialogDescription>
              Reject the payout request for{" "}
              {formatCurrency(payout.amount, payout.currency)}. Commissions will
              be returned to cleared status.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="reason">
                Reason for rejection <span className="text-destructive">*</span>
              </Label>
              <Textarea
                id="reason"
                placeholder="Please provide a detailed reason for rejecting this payout (minimum 20 characters)..."
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={4}
                required
                minLength={20}
              />
              <p className="text-xs text-muted-foreground">
                {reason.length}/20 characters minimum
              </p>
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                onOpenChange(false);
                setReason("");
              }}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="destructive"
              isLoading={rejectMutation.isPending}
            >
              Reject Payout
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
