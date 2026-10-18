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
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { useApprovePayout } from "@/hooks/use-payouts";
import { useToast } from "@/hooks/use-toast";
import { formatCurrency } from "@/lib/utils";
import type { Payout } from "@/lib/types";
import { getErrorMessage } from "@/constants/api";
import { ApiClientError } from "@/lib/api-client";

interface ApprovePayoutModalProps {
  payout: Payout | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ApprovePayoutModal({
  payout,
  open,
  onOpenChange,
}: ApprovePayoutModalProps) {
  const [paymentReference, setPaymentReference] = useState("");
  const [notes, setNotes] = useState("");
  const approveMutation = useApprovePayout();
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!payout) return;

    try {
      await approveMutation.mutateAsync({
        id: payout.id,
        payment_reference: paymentReference.trim() || undefined,
        notes: notes.trim() || undefined,
      });

      toast({
        title: "Payout approved",
        description: `Payout of ${formatCurrency(
          payout.amount,
          payout.currency
        )} has been approved`,
        variant: "success",
      });

      onOpenChange(false);
      setPaymentReference("");
      setNotes("");
    } catch (error: unknown) {
      const apiError =
        error instanceof ApiClientError
          ? error
          : new ApiClientError("An unexpected error occurred");
      toast({
        title: "Failed to approve payout",
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
            <DialogTitle>Approve Payout</DialogTitle>
            <DialogDescription>
              Approve the payout request for{" "}
              {formatCurrency(payout.amount, payout.currency)}. This will mark
              related commissions as paid.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="payment_reference">
                Payment Reference (optional)
              </Label>
              <Input
                id="payment_reference"
                placeholder="e.g., PAY-123456789"
                value={paymentReference}
                onChange={(e) => setPaymentReference(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="notes">Notes (optional)</Label>
              <Textarea
                id="notes"
                placeholder="Add any notes about this approval..."
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                onOpenChange(false);
                setPaymentReference("");
                setNotes("");
              }}
            >
              Cancel
            </Button>
            <Button type="submit" isLoading={approveMutation.isPending}>
              Approve Payout
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
