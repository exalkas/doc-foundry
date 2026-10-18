"use client";

import { Button } from "@/components/ui/button";
import { useImpersonateWorkspace } from "@/hooks/use-workspace";
import { useToast } from "@/hooks/use-toast";
import { UserCog } from "lucide-react";
import { getErrorMessage } from "@/constants/api";
import { ApiClientError } from "@/lib/api-client";

interface ImpersonateButtonProps {
  workspaceId: string;
  workspaceName: string;
}

export function ImpersonateButton({
  workspaceId,
  workspaceName,
}: ImpersonateButtonProps) {
  const impersonateMutation = useImpersonateWorkspace();
  const { toast } = useToast();

  const handleImpersonate = async () => {
    try {
      const result = await impersonateMutation.mutateAsync({
        id: workspaceId,
      });

      // Get the main app URL from environment or use default
      const mainAppUrl =
        process.env.NEXT_PUBLIC_MAIN_APP_URL || "http://localhost:3000";

      // Store the impersonation token (could use localStorage or sessionStorage)
      // For now, we'll redirect with token in URL (not ideal for production)
      // In production, you'd want to use a more secure method
      const redirectUrl = `${mainAppUrl}/admin-impersonate?token=${result.token}`;

      toast({
        title: "Impersonation started",
        description: `Redirecting to ${workspaceName} as owner...`,
        variant: "success",
      });

      // Redirect to main app with impersonation token
      window.location.href = redirectUrl;
    } catch (error: unknown) {
      const apiError =
        error instanceof ApiClientError
          ? error
          : new ApiClientError("An unexpected error occurred");
      toast({
        title: "Failed to impersonate",
        description: getErrorMessage(apiError),
        variant: "destructive",
      });
    }
  };

  return (
    <Button
      variant="outline"
      onClick={handleImpersonate}
      isLoading={impersonateMutation.isPending}
      aria-label={`Impersonate owner of workspace ${workspaceName}`}
    >
      <UserCog className="mr-2 h-4 w-4" />
      Impersonate Owner
    </Button>
  );
}
