"use client";

import { useState, useEffect } from "react";
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
import { useAdjustCommission } from "@/hooks/use-commissions";
import { useToast } from "@/hooks/use-toast";
import { formatCurrency } from "@/lib/utils";
import type { Commission } from "@/lib/types";
import { getErrorMessage } from "@/constants/api";
import { ApiClientError } from "@/lib/api-client";

interface AdjustCommissionModalProps {
  commission: Commission | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AdjustCommissionModal({
  commission,
  open,
  onOpenChange,
}: AdjustCommissionModalProps) {
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const adjustMutation = useAdjustCommission();
  const { toast } = useToast();

  useEffect(() => {
    if (commission) {
      setAmount(commission.amount.toString());
      setReason("");
    }
  }, [commission]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!commission) return;

    const amountNum = parseFloat(amount);
    if (isNaN(amountNum) || amountNum < 0) {
      toast({
        title: "Invalid amount",
        description: "Please enter a valid positive number",
        variant: "destructive",
      });
      return;
    }

    if (!reason.trim() || reason.trim().length < 20) {
      toast({
        title: "Reason required",
        description: "Please provide a reason with at least 20 characters",
        variant: "destructive",
      });
      return;
    }

    try {
      await adjustMutation.mutateAsync({
        id: commission.id,
        amount: amountNum,
        reason: reason.trim(),
      });

      toast({
        title: "Commission adjusted",
        description: `Commission amount updated to ${formatCurrency(
          amountNum,
          commission.currency
        )}`,
        variant: "success",
      });

      onOpenChange(false);
      setAmount("");
      setReason("");
    } catch (error: unknown) {
      const apiError =
        error instanceof ApiClientError
          ? error
          : new ApiClientError("An unexpected error occurred");
      toast({
        title: "Failed to adjust commission",
        description: getErrorMessage(apiError),
        variant: "destructive",
      });
    }
  };

  if (!commission) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Adjust Commission</DialogTitle>
            <DialogDescription>
              Manually adjust the commission amount. Current amount:{" "}
              {formatCurrency(commission.amount, commission.currency)}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="amount">
                New Amount ({commission.currency}){" "}
                <span className="text-destructive">*</span>
              </Label>
              <Input
                id="amount"
                type="number"
                step="0.01"
                min="0"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="reason">
                Reason <span className="text-destructive">*</span>
              </Label>
              <Textarea
                id="reason"
                placeholder="Please provide a detailed reason for this adjustment (minimum 20 characters)..."
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
                setAmount("");
                setReason("");
              }}
            >
              Cancel
            </Button>
            <Button type="submit" isLoading={adjustMutation.isPending}>
              Adjust Commission
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
