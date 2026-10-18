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
import { useUnsuspendWorkspace } from "@/hooks/use-workspace";
import { useToast } from "@/hooks/use-toast";
import { getErrorMessage } from "@/constants/api";
import { ApiClientError } from "@/lib/api-client";

interface UnsuspendWorkspaceDialogProps {
  workspaceId: string;
  workspaceName: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function UnsuspendWorkspaceDialog({
  workspaceId,
  workspaceName,
  open,
  onOpenChange,
}: UnsuspendWorkspaceDialogProps) {
  const unsuspendMutation = useUnsuspendWorkspace();
  const { toast } = useToast();

  const handleConfirm = async () => {
    try {
      await unsuspendMutation.mutateAsync({ id: workspaceId });

      toast({
        title: "Workspace unsuspended",
        description: `${workspaceName} has been restored to active status`,
        variant: "success",
      });

      onOpenChange(false);
    } catch (error: unknown) {
      const apiError =
        error instanceof ApiClientError
          ? error
          : new ApiClientError("An unexpected error occurred");
      toast({
        title: "Failed to unsuspend workspace",
        description: getErrorMessage(apiError),
        variant: "destructive",
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Unsuspend Workspace</DialogTitle>
          <DialogDescription>
            Restore the workspace &ldquo;{workspaceName}&rdquo; to active
            status. The workspace owner will regain access immediately.
          </DialogDescription>
        </DialogHeader>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            type="button"
            onClick={handleConfirm}
            isLoading={unsuspendMutation.isPending}
          >
            Unsuspend Workspace
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
