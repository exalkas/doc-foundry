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
import { useApproveAffiliate } from "@/hooks/use-affiliate";
import { useToast } from "@/hooks/use-toast";
import { getErrorMessage } from "@/constants/api";
import { ApiClientError } from "@/lib/api-client";

interface ApproveAffiliateModalProps {
  affiliateId: string;
  affiliateEmail: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ApproveAffiliateModal({
  affiliateId,
  affiliateEmail,
  open,
  onOpenChange,
}: ApproveAffiliateModalProps) {
  const [notes, setNotes] = useState("");
  const approveMutation = useApproveAffiliate();
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      await approveMutation.mutateAsync({
        id: affiliateId,
        notes: notes.trim() || undefined,
      });

      toast({
        title: "Affiliate approved",
        description: `${affiliateEmail} has been approved successfully`,
        variant: "success",
      });

      onOpenChange(false);
      setNotes("");
    } catch (error: unknown) {
      const apiError =
        error instanceof ApiClientError
          ? error
          : new ApiClientError("An unexpected error occurred");
      toast({
        title: "Failed to approve affiliate",
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
            <DialogTitle>Approve Affiliate</DialogTitle>
            <DialogDescription>
              Approve the affiliate application for {affiliateEmail}. An
              approval email will be sent to the affiliate.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="notes">Notes (optional)</Label>
              <Textarea
                id="notes"
                placeholder="Add any notes about this approval..."
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={4}
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                onOpenChange(false);
                setNotes("");
              }}
            >
              Cancel
            </Button>
            <Button type="submit" isLoading={approveMutation.isPending}>
              Approve Affiliate
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
