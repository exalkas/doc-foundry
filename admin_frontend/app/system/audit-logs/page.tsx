"use client";

import { useState } from "react";
import { AdminLayout } from "@/components/layout/admin-layout";
import { AuditLogTable } from "@/components/admin/audit-log-table";
import { useAuditLogs } from "@/hooks/use-audit-logs";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ChevronLeft, ChevronRight, Download } from "lucide-react";
import { PAGINATION } from "@/constants/pagination";

export default function AuditLogsPage() {
  const [workspaceId, setWorkspaceId] = useState<string>("");
  const [actorType, setActorType] = useState<string>("all");
  const [fromDate, setFromDate] = useState<string>("");
  const [toDate, setToDate] = useState<string>("");
  const [page, setPage] = useState(1);
  const pageSize = PAGINATION.DEFAULT_PAGE_SIZE;

  const { data: logs, isLoading } = useAuditLogs({
    workspace_id: workspaceId || undefined,
    actor_type: actorType === "all" ? undefined : actorType,
    from: fromDate || undefined,
    to: toDate || undefined,
    page,
    page_size: pageSize,
  });

  const handleExportCSV = () => {
    if (!logs || logs.length === 0) return;

    const headers = [
      "Timestamp",
      "Actor Type",
      "User ID",
      "Event Type",
      "Workspace ID",
      "Description",
    ];
    const rows = logs.map((log) => [
      log.created_at,
      log.actor_type,
      log.user_id || "",
      log.event_type,
      log.workspace_id || "",
      log.description.replace(/,/g, ";"), // Replace commas to avoid CSV issues
    ]);

    const csvContent = [
      headers.join(","),
      ...rows.map((row) => row.join(",")),
    ].join("\n");

    const blob = new Blob([csvContent], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `audit-logs-${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleExportJSON = () => {
    if (!logs || logs.length === 0) return;

    const jsonContent = JSON.stringify(logs, null, 2);
    const blob = new Blob([jsonContent], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `audit-logs-${new Date().toISOString().split("T")[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Audit Logs</h1>
          <p className="text-muted-foreground">
            View system audit logs across all workspaces
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Filter Audit Logs</CardTitle>
            <CardDescription>
              Filter audit logs by workspace, actor type, and date range
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
              <div className="space-y-2">
                <Label htmlFor="workspace-id">Workspace ID</Label>
                <Input
                  id="workspace-id"
                  placeholder="Filter by workspace ID"
                  value={workspaceId}
                  onChange={(e) => setWorkspaceId(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="actor-type">Actor Type</Label>
                <Select value={actorType} onValueChange={setActorType}>
                  <SelectTrigger id="actor-type">
                    <SelectValue placeholder="All types" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Types</SelectItem>
                    <SelectItem value="user">User</SelectItem>
                    <SelectItem value="system">System</SelectItem>
                    <SelectItem value="admin">Admin</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="from-date">From Date</Label>
                <Input
                  id="from-date"
                  type="datetime-local"
                  value={fromDate}
                  onChange={(e) => setFromDate(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="to-date">To Date</Label>
                <Input
                  id="to-date"
                  type="datetime-local"
                  value={toDate}
                  onChange={(e) => setToDate(e.target.value)}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Audit Logs</CardTitle>
                <CardDescription>
                  {logs?.length || 0} log{logs?.length !== 1 ? "s" : ""} found
                </CardDescription>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={handleExportCSV}>
                  <Download className="mr-2 h-4 w-4" />
                  Export CSV
                </Button>
                <Button variant="outline" size="sm" onClick={handleExportJSON}>
                  <Download className="mr-2 h-4 w-4" />
                  Export JSON
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <AuditLogTable logs={logs || []} isLoading={isLoading} />

            {logs && logs.length > 0 && (
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  Showing {(page - 1) * pageSize + 1}-
                  {Math.min(page * pageSize, logs.length)} of {logs.length} logs
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                  >
                    <ChevronLeft className="h-4 w-4" />
                    Previous
                  </Button>
                  <span className="text-sm text-muted-foreground">
                    Page {page}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => p + 1)}
                    disabled={logs.length < pageSize}
                  >
                    Next
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </AdminLayout>
  );
}
