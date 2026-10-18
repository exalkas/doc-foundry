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
import { useBlockAffiliate } from "@/hooks/use-affiliate";
import { useToast } from "@/hooks/use-toast";
import { getErrorMessage } from "@/constants/api";
import { ApiClientError } from "@/lib/api-client";

interface BlockAffiliateModalProps {
  affiliateId: string;
  affiliateEmail: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function BlockAffiliateModal({
  affiliateId,
  affiliateEmail,
  open,
  onOpenChange,
}: BlockAffiliateModalProps) {
  const [notes, setNotes] = useState("");
  const blockMutation = useBlockAffiliate();
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!notes.trim()) {
      toast({
        title: "Notes required",
        description: "Please provide a reason for blocking",
        variant: "destructive",
      });
      return;
    }

    try {
      await blockMutation.mutateAsync({
        id: affiliateId,
        notes: notes.trim(),
      });

      toast({
        title: "Affiliate blocked",
        description: `${affiliateEmail} has been blocked. New commissions will be prevented.`,
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
        title: "Failed to block affiliate",
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
            <DialogTitle>Block Affiliate</DialogTitle>
            <DialogDescription>
              Block the affiliate {affiliateEmail}. This will prevent new
              commissions, but existing cleared commissions will remain payable.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="notes">
                Reason for blocking <span className="text-destructive">*</span>
              </Label>
              <Textarea
                id="notes"
                placeholder="Please provide a reason for blocking this affiliate..."
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
              isLoading={blockMutation.isPending}
            >
              Block Affiliate
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
