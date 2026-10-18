"use client";

import { use } from "react";
import { AdminLayout } from "@/components/layout/admin-layout";
import { WorkspaceDetailHeader } from "@/components/admin/workspace-detail-header";
import { useWorkspace } from "@/hooks/use-workspace";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Spinner } from "@/components/ui/spinner";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ArrowLeft, BarChart3, Shield } from "lucide-react";

interface WorkspaceDetailPageProps {
  params: Promise<{ id: string }>;
}

export default function WorkspaceDetailPage({
  params,
}: WorkspaceDetailPageProps) {
  const { id } = use(params);
  const { data: workspace, isLoading, error } = useWorkspace(id);

  if (isLoading) {
    return (
      <AdminLayout>
        <div className="flex items-center justify-center py-12">
          <Spinner />
        </div>
      </AdminLayout>
    );
  }

  if (error || !workspace) {
    return (
      <AdminLayout>
        <div className="space-y-6">
          <div className="flex items-center gap-4">
            <Link href="/workspaces">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Workspaces
              </Button>
            </Link>
          </div>
          <Card>
            <CardContent className="pt-6">
              <p className="text-center text-muted-foreground">
                Workspace not found or error loading workspace
              </p>
            </CardContent>
          </Card>
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Link href="/workspaces">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Workspaces
            </Button>
          </Link>
        </div>

        <WorkspaceDetailHeader workspace={workspace} />

        <Tabs defaultValue="overview" className="space-y-4">
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="analytics">
              <BarChart3 className="mr-2 h-4 w-4" />
              Analytics
            </TabsTrigger>
            <TabsTrigger value="abuse">
              <Shield className="mr-2 h-4 w-4" />
              Abuse Detection
            </TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Workspace Information</CardTitle>
                <CardDescription>
                  Basic information about this workspace
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">
                      Workspace ID
                    </p>
                    <p className="text-sm font-mono">{workspace.id}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">
                      Status
                    </p>
                    <p className="text-sm capitalize">{workspace.status}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">
                      Owner Email
                    </p>
                    <p className="text-sm">{workspace.owner_email || "-"}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">
                      Plan
                    </p>
                    <p className="text-sm">{workspace.plan || "-"}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">
                      Created At
                    </p>
                    <p className="text-sm">
                      {new Date(workspace.created_at).toLocaleString()}
                    </p>
                  </div>
                  {workspace.updated_at && (
                    <div>
                      <p className="text-sm font-medium text-muted-foreground">
                        Updated At
                      </p>
                      <p className="text-sm">
                        {new Date(workspace.updated_at).toLocaleString()}
                      </p>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="analytics">
            <Card>
              <CardHeader>
                <CardTitle>Usage Analytics</CardTitle>
                <CardDescription>
                  View detailed usage analytics for this workspace
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Link href={`/workspaces/${id}/usage`}>
                  <Button variant="outline">
                    View Full Analytics
                    <BarChart3 className="ml-2 h-4 w-4" />
                  </Button>
                </Link>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="abuse">
            <Card>
              <CardHeader>
                <CardTitle>Abuse Detection</CardTitle>
                <CardDescription>
                  Check for abuse patterns and violations
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Link href={`/workspaces/${id}/abuse`}>
                  <Button variant="outline">
                    View Abuse Detection
                    <Shield className="ml-2 h-4 w-4" />
                  </Button>
                </Link>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </AdminLayout>
  );
}
