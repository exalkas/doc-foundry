"use client";

import { use } from "react";
import { AdminLayout } from "@/components/layout/admin-layout";
import { useWorkspace } from "@/hooks/use-workspace";
import { useWorkspaceAbuse } from "@/hooks/use-workspace-abuse";
import { AbuseDetectionDisplay } from "@/components/admin/abuse-detection";
import { Card, CardContent } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { ArrowLeft, Shield } from "lucide-react";

interface WorkspaceAbusePageProps {
  params: Promise<{ id: string }>;
}

export default function WorkspaceAbusePage({
  params,
}: WorkspaceAbusePageProps) {
  const { id } = use(params);
  const { data: workspace, isLoading: workspaceLoading } = useWorkspace(id);
  const { data: abuseDetection, isLoading: abuseLoading } =
    useWorkspaceAbuse(id);

  if (workspaceLoading) {
    return (
      <AdminLayout>
        <div className="flex items-center justify-center py-12">
          <Spinner />
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Link href={`/workspaces/${id}`}>
            <Button variant="ghost" size="sm">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Workspace
            </Button>
          </Link>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">
              Abuse Detection
            </h1>
            <p className="text-muted-foreground">
              {workspace?.name || "Workspace"}
            </p>
          </div>
        </div>

        {abuseLoading ? (
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-center py-12">
                <Spinner />
              </div>
            </CardContent>
          </Card>
        ) : abuseDetection ? (
          <AbuseDetectionDisplay
            abuseDetection={abuseDetection}
            workspaceName={workspace?.name || "Workspace"}
          />
        ) : (
          <Card>
            <CardContent className="pt-6">
              <p className="text-center text-muted-foreground">
                Unable to load abuse detection data
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </AdminLayout>
  );
}
