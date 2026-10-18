"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { getStatusColor, formatDate, formatDateTime } from "@/lib/utils";
import type { Workspace } from "@/lib/types";
import { SuspendWorkspaceModal } from "./suspend-workspace-modal";
import { UnsuspendWorkspaceDialog } from "./unsuspend-workspace-dialog";
import { ImpersonateButton } from "./impersonate-button";
import { Shield, Ban, CheckCircle2 } from "lucide-react";

interface WorkspaceDetailHeaderProps {
  workspace: Workspace;
}

export function WorkspaceDetailHeader({
  workspace,
}: WorkspaceDetailHeaderProps) {
  const [suspendModalOpen, setSuspendModalOpen] = useState(false);
  const [unsuspendDialogOpen, setUnsuspendDialogOpen] = useState(false);

  const isSuspended = workspace.status === "suspended";
  const isActive = workspace.status === "active";

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="space-y-2">
              <div className="flex items-center gap-3">
                <h2 className="text-2xl font-bold">{workspace.name}</h2>
                <Badge variant={getStatusColor(workspace.status)}>
                  {workspace.status}
                </Badge>
              </div>
              <div className="space-y-1 text-sm text-muted-foreground">
                <p>
                  <span className="font-medium">ID:</span> {workspace.id}
                </p>
                {workspace.owner_email && (
                  <p>
                    <span className="font-medium">Owner:</span>{" "}
                    {workspace.owner_email}
                  </p>
                )}
                {workspace.plan && (
                  <p>
                    <span className="font-medium">Plan:</span> {workspace.plan}
                  </p>
                )}
                <p>
                  <span className="font-medium">Created:</span>{" "}
                  {formatDateTime(workspace.created_at)}
                </p>
                {workspace.updated_at && (
                  <p>
                    <span className="font-medium">Updated:</span>{" "}
                    {formatDateTime(workspace.updated_at)}
                  </p>
                )}
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              {isActive && (
                <Button
                  variant="destructive"
                  onClick={() => setSuspendModalOpen(true)}
                >
                  <Ban className="mr-2 h-4 w-4" />
                  Suspend
                </Button>
              )}
              {isSuspended && (
                <Button
                  variant="default"
                  onClick={() => setUnsuspendDialogOpen(true)}
                >
                  <CheckCircle2 className="mr-2 h-4 w-4" />
                  Unsuspend
                </Button>
              )}
              <ImpersonateButton
                workspaceId={workspace.id}
                workspaceName={workspace.name}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <SuspendWorkspaceModal
        workspaceId={workspace.id}
        workspaceName={workspace.name}
        open={suspendModalOpen}
        onOpenChange={setSuspendModalOpen}
      />

      <UnsuspendWorkspaceDialog
        workspaceId={workspace.id}
        workspaceName={workspace.name}
        open={unsuspendDialogOpen}
        onOpenChange={setUnsuspendDialogOpen}
      />
    </div>
  );
}
