"use client";

import { useQuery } from "@tanstack/react-query";
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { MoreVertical, Shield } from "lucide-react";
import { get } from "@/lib/api-client";
import { useAuthContext } from "@/contexts/auth-context";
import { useRouter } from "next/navigation";

interface Workspace {
  id: string;
  name: string;
  owner_email: string;
  plan: string;
  status: string;
  created_at: string;
}

interface SystemMetrics {
  queue_depth: number;
  avg_processing_time: number;
  daily_docs_processed: number;
  errors_last_24h: number;
}

export default function AdminPage() {
  const { user } = useAuthContext();
  const router = useRouter();

  // Redirect if not admin
  if (user?.role !== "admin") {
    router.push("/app");
    return null;
  }

  const { data: workspaces } = useQuery<Workspace[]>({
    queryKey: ["admin", "workspaces"],
    queryFn: () => get("/api/admin/workspaces"),
  });

  const { data: metrics } = useQuery<SystemMetrics>({
    queryKey: ["admin", "metrics"],
    queryFn: () => get("/api/admin/metrics"),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Shield className="h-8 w-8" />
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Admin panel</h1>
          <p className="text-muted-foreground">
            Platform-level administration and monitoring
          </p>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Companies */}
        <Card>
          <CardHeader>
            <CardTitle>Companies</CardTitle>
            <CardDescription>Manage all companies</CardDescription>
          </CardHeader>
          <CardContent>
            {workspaces && workspaces.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Company</TableHead>
                    <TableHead>Owner</TableHead>
                    <TableHead>Plan</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {workspaces.map((workspace) => (
                    <TableRow key={workspace.id}>
                      <TableCell className="font-medium">
                        {workspace.name}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {workspace.owner_email}
                      </TableCell>
                      <TableCell>{workspace.plan}</TableCell>
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
                      <TableCell>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" className="h-8 w-8 p-0">
                              <MoreVertical className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem>
                              Impersonate owner
                            </DropdownMenuItem>
                            <DropdownMenuItem>Suspend company</DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <p className="text-sm text-muted-foreground">No companies</p>
            )}
          </CardContent>
        </Card>

        {/* System Metrics */}
        <Card>
          <CardHeader>
            <CardTitle>System metrics</CardTitle>
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
                  <TableRow>
                    <TableCell>Queue depth</TableCell>
                    <TableCell className="font-medium">
                      {metrics.queue_depth}
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Avg processing time</TableCell>
                    <TableCell className="font-medium">
                      {metrics.avg_processing_time.toFixed(2)}s
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Daily docs processed</TableCell>
                    <TableCell className="font-medium">
                      {metrics.daily_docs_processed}
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Errors last 24h</TableCell>
                    <TableCell className="font-medium text-destructive">
                      {metrics.errors_last_24h}
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            ) : (
              <p className="text-sm text-muted-foreground">
                Loading metrics...
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
