"use client";

import { use } from "react";
import { useState } from "react";
import { AdminLayout } from "@/components/layout/admin-layout";
import { useWorkspace } from "@/hooks/use-workspace";
import { useWorkspaceAnalytics } from "@/hooks/use-workspace-analytics";
import { UsageAnalyticsDisplay } from "@/components/admin/usage-analytics";
import { Card, CardContent } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import Link from "next/link";
import { ArrowLeft, BarChart3 } from "lucide-react";

interface WorkspaceUsagePageProps {
  params: Promise<{ id: string }>;
}

export default function WorkspaceUsagePage({
  params,
}: WorkspaceUsagePageProps) {
  const { id } = use(params);
  const [days, setDays] = useState(90);
  const { data: workspace, isLoading: workspaceLoading } = useWorkspace(id);
  const { data: analytics, isLoading: analyticsLoading } =
    useWorkspaceAnalytics(id, days);

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
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href={`/workspaces/${id}`}>
              <Button variant="ghost" size="sm">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Workspace
              </Button>
            </Link>
            <div>
              <h1 className="text-3xl font-bold tracking-tight">
                Usage Analytics
              </h1>
              <p className="text-muted-foreground">
                {workspace?.name || "Workspace"}
              </p>
            </div>
          </div>

          <Select
            value={days.toString()}
            onValueChange={(v) => setDays(Number(v))}
          >
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Time period" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="30">Last 30 days</SelectItem>
              <SelectItem value="90">Last 90 days</SelectItem>
              <SelectItem value="180">Last 180 days</SelectItem>
              <SelectItem value="365">Last year</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {analyticsLoading ? (
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-center py-12">
                <Spinner />
              </div>
            </CardContent>
          </Card>
        ) : analytics ? (
          <UsageAnalyticsDisplay analytics={analytics} />
        ) : (
          <Card>
            <CardContent className="pt-6">
              <p className="text-center text-muted-foreground">
                No analytics data available
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </AdminLayout>
  );
}
