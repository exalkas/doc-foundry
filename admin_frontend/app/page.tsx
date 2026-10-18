"use client";

import { useQuery } from "@tanstack/react-query";
import { AdminLayout } from "@/components/layout/admin-layout";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { get } from "@/lib/api-client";
import { Shield, Building2, Users, UserCheck, Activity } from "lucide-react";
import Link from "next/link";
import type { Workspace, SystemMetrics } from "@/lib/types";

export default function DashboardPage() {
  const { data: workspaces } = useQuery<Workspace[]>({
    queryKey: ["admin", "workspaces"],
    queryFn: () => get("/api/admin/workspaces"),
  });

  const { data: metrics } = useQuery<SystemMetrics>({
    queryKey: ["admin", "metrics"],
    queryFn: () => get("/api/admin/metrics"),
    retry: false, // Don't retry if endpoint doesn't exist
  });

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">
            Platform overview and quick actions
          </p>
        </div>

        {/* Quick Actions */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Workspaces</CardTitle>
              <Building2 className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {workspaces?.length || 0}
              </div>
              <p className="text-xs text-muted-foreground">Total workspaces</p>
              <Link href="/workspaces" className="mt-2 block">
                <Button variant="link" className="h-auto p-0 text-xs">
                  View all →
                </Button>
              </Link>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Users</CardTitle>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">-</div>
              <p className="text-xs text-muted-foreground">Total users</p>
              <Link href="/users" className="mt-2 block">
                <Button variant="link" className="h-auto p-0 text-xs">
                  View all →
                </Button>
              </Link>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Affiliates</CardTitle>
              <UserCheck className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">-</div>
              <p className="text-xs text-muted-foreground">Total affiliates</p>
              <Link href="/affiliates" className="mt-2 block">
                <Button variant="link" className="h-auto p-0 text-xs">
                  View all →
                </Button>
              </Link>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                System Health
              </CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{metrics ? "✓" : "-"}</div>
              <p className="text-xs text-muted-foreground">
                {metrics ? "Operational" : "Metrics unavailable"}
              </p>
              <Link href="/metrics" className="mt-2 block">
                <Button variant="link" className="h-auto p-0 text-xs">
                  View details →
                </Button>
              </Link>
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          {/* Recent Workspaces */}
          <Card>
            <CardHeader>
              <CardTitle>Recent Workspaces</CardTitle>
              <CardDescription>
                Latest workspaces created on the platform
              </CardDescription>
            </CardHeader>
            <CardContent>
              {workspaces && workspaces.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Created</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {workspaces.slice(0, 5).map((workspace) => (
                      <TableRow key={workspace.id}>
                        <TableCell className="font-medium">
                          {workspace.name}
                        </TableCell>
                        <TableCell>
                          <span
                            className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${
                              workspace.status === "active"
                                ? "bg-accent/10 text-accent"
                                : "bg-muted text-muted-foreground"
                            }`}
                          >
                            {workspace.status}
                          </span>
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {new Date(workspace.created_at).toLocaleDateString()}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <p className="text-sm text-muted-foreground">No workspaces</p>
              )}
            </CardContent>
          </Card>

          {/* System Metrics */}
          <Card>
            <CardHeader>
              <CardTitle>System Metrics</CardTitle>
              <CardDescription>Platform performance indicators</CardDescription>
            </CardHeader>
            <CardContent>
              {metrics ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Metric</TableHead>
                      <TableHead>Value</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {metrics.queue_depth !== undefined && (
                      <TableRow>
                        <TableCell>Queue Depth</TableCell>
                        <TableCell className="font-medium">
                          {metrics.queue_depth}
                        </TableCell>
                      </TableRow>
                    )}
                    {metrics.avg_processing_time !== undefined && (
                      <TableRow>
                        <TableCell>Avg Processing Time</TableCell>
                        <TableCell className="font-medium">
                          {metrics.avg_processing_time.toFixed(2)}s
                        </TableCell>
                      </TableRow>
                    )}
                    {metrics.daily_docs_processed !== undefined && (
                      <TableRow>
                        <TableCell>Daily Docs Processed</TableCell>
                        <TableCell className="font-medium">
                          {metrics.daily_docs_processed}
                        </TableCell>
                      </TableRow>
                    )}
                    {metrics.errors_last_24h !== undefined && (
                      <TableRow>
                        <TableCell>Errors Last 24h</TableCell>
                        <TableCell className="font-medium text-destructive">
                          {metrics.errors_last_24h}
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Metrics endpoint not available
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </AdminLayout>
  );
}
