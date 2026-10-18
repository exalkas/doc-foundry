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
import { useRevokeApiKey } from "@/hooks/use-revoke-api-key";
import { useToast } from "@/hooks/use-toast";
import { getErrorMessage } from "@/constants/api";
import { ApiClientError } from "@/lib/api-client";

interface RevokeApiKeyModalProps {
  apiKeyId: string;
  apiKeyName: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Modal component for revoking an API key
 *
 * Shows a confirmation dialog before revoking an API key. This action cannot be undone.
 *
 * @example
 * ```tsx
 * <RevokeApiKeyModal
 *   apiKeyId="api-key-123"
 *   apiKeyName="Production API Key"
 *   open={isOpen}
 *   onOpenChange={setIsOpen}
 * />
 * ```
 */
export function RevokeApiKeyModal({
  apiKeyId,
  apiKeyName,
  open,
  onOpenChange,
}: RevokeApiKeyModalProps) {
  const revokeMutation = useRevokeApiKey();
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      await revokeMutation.mutateAsync({ id: apiKeyId });

      toast({
        title: "API key revoked",
        description: `${apiKeyName} has been revoked successfully`,
      });

      onOpenChange(false);
    } catch (error: unknown) {
      const apiError =
        error instanceof ApiClientError
          ? error
          : new ApiClientError("An unexpected error occurred");
      toast({
        title: "Failed to revoke API key",
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
            <DialogTitle>Revoke API Key</DialogTitle>
            <DialogDescription>
              Are you sure you want to revoke <strong>{apiKeyName}</strong>?
              This action cannot be undone. The API key will immediately stop
              working.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={revokeMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="destructive"
              disabled={revokeMutation.isPending}
            >
              {revokeMutation.isPending ? "Revoking..." : "Revoke API Key"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
