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
import { useSuspendWorkspace } from "@/hooks/use-workspace";
import { useToast } from "@/hooks/use-toast";

import { API_CONFIG, getErrorMessage } from "@/constants/api";
import { ApiClientError } from "@/lib/api-client";

/**
 * Props for SuspendWorkspaceModal component
 */
interface SuspendWorkspaceModalProps {
  /** The ID of the workspace to suspend */
  workspaceId: string;
  /** The name of the workspace (displayed in the modal) */
  workspaceName: string;
  /** Whether the modal is open */
  open: boolean;
  /** Callback when the modal open state changes */
  onOpenChange: (open: boolean) => void;
}

/**
 * Modal component for suspending a workspace
 *
 * Requires a reason with minimum 20 characters. Shows validation errors
 * and handles API errors gracefully.
 *
 * @example
 * ```tsx
 * <SuspendWorkspaceModal
 *   workspaceId="workspace-123"
 *   workspaceName="My Workspace"
 *   open={isOpen}
 *   onOpenChange={setIsOpen}
 * />
 * ```
 */
export function SuspendWorkspaceModal({
  workspaceId,
  workspaceName,
  open,
  onOpenChange,
}: SuspendWorkspaceModalProps) {
  const [reason, setReason] = useState("");
  const suspendMutation = useSuspendWorkspace();
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!reason.trim() || reason.trim().length < 20) {
      toast({
        title: "Invalid reason",
        description: "Please provide a reason with at least 20 characters",
        variant: "destructive",
      });
      return;
    }

    try {
      await suspendMutation.mutateAsync({
        id: workspaceId,
        reason: reason.trim(),
      });

      toast({
        title: "Workspace suspended",
        description: `${workspaceName} has been suspended successfully`,
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
        title: "Failed to suspend workspace",
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
            <DialogTitle>Suspend Workspace</DialogTitle>
            <DialogDescription>
              Suspend the workspace &ldquo;{workspaceName}&rdquo;. This will
              prevent access and send a notification to the workspace owner.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="reason">
                Reason for suspension{" "}
                <span className="text-destructive">*</span>
              </Label>
              <Textarea
                id="reason"
                placeholder="Please provide a detailed reason for suspending this workspace (minimum 20 characters)..."
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
              isLoading={suspendMutation.isPending}
            >
              Suspend Workspace
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
