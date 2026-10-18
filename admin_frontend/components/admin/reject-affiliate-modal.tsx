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
import { useRejectAffiliate } from "@/hooks/use-affiliate";
import { useToast } from "@/hooks/use-toast";
import { getErrorMessage } from "@/constants/api";
import { ApiClientError } from "@/lib/api-client";

interface RejectAffiliateModalProps {
  affiliateId: string;
  affiliateEmail: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function RejectAffiliateModal({
  affiliateId,
  affiliateEmail,
  open,
  onOpenChange,
}: RejectAffiliateModalProps) {
  const [notes, setNotes] = useState("");
  const rejectMutation = useRejectAffiliate();
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!notes.trim()) {
      toast({
        title: "Notes required",
        description: "Please provide a reason for rejection",
        variant: "destructive",
      });
      return;
    }

    try {
      await rejectMutation.mutateAsync({
        id: affiliateId,
        notes: notes.trim(),
      });

      toast({
        title: "Affiliate rejected",
        description: `${affiliateEmail} has been rejected`,
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
        title: "Failed to reject affiliate",
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
            <DialogTitle>Reject Affiliate</DialogTitle>
            <DialogDescription>
              Reject the affiliate application for {affiliateEmail}. A rejection
              email with your notes will be sent to the affiliate.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="notes">
                Reason for rejection <span className="text-destructive">*</span>
              </Label>
              <Textarea
                id="notes"
                placeholder="Please provide a reason for rejecting this affiliate..."
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={4}
                required
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
            <Button
              type="submit"
              variant="destructive"
              isLoading={rejectMutation.isPending}
            >
              Reject Affiliate
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
