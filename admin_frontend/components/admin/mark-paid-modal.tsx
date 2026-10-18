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
import { useMarkPayoutPaid } from "@/hooks/use-payouts";
import { useToast } from "@/hooks/use-toast";
import { formatCurrency } from "@/lib/utils";
import type { Payout } from "@/lib/types";
import { getErrorMessage } from "@/constants/api";
import { ApiClientError } from "@/lib/api-client";

interface MarkPaidModalProps {
  payout: Payout | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function MarkPaidModal({
  payout,
  open,
  onOpenChange,
}: MarkPaidModalProps) {
  const [paymentReference, setPaymentReference] = useState("");
  const [notes, setNotes] = useState("");
  const markPaidMutation = useMarkPayoutPaid();
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!payout) return;

    if (!paymentReference.trim()) {
      toast({
        title: "Payment reference required",
        description: "Please provide the payment transaction ID",
        variant: "destructive",
      });
      return;
    }

    try {
      await markPaidMutation.mutateAsync({
        id: payout.id,
        payment_reference: paymentReference.trim(),
        notes: notes.trim() || undefined,
      });

      toast({
        title: "Payout marked as paid",
        description: `Payout of ${formatCurrency(
          payout.amount,
          payout.currency
        )} has been marked as paid`,
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
        title: "Failed to mark payout as paid",
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
            <DialogTitle>Mark Payout as Paid</DialogTitle>
            <DialogDescription>
              Mark the payout as paid after completing the external payment.
              Amount: {formatCurrency(payout.amount, payout.currency)}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="payment_reference">
                Payment Reference <span className="text-destructive">*</span>
              </Label>
              <Input
                id="payment_reference"
                placeholder="Transaction ID from payment provider"
                value={paymentReference}
                onChange={(e) => setPaymentReference(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="notes">Notes (optional)</Label>
              <Textarea
                id="notes"
                placeholder="Add any notes about this payment..."
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
            <Button type="submit" isLoading={markPaidMutation.isPending}>
              Mark as Paid
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
