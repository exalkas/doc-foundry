"use client";

import { useState, useMemo } from "react";
import { AdminLayout } from "@/components/layout/admin-layout";
import { WorkspaceTable } from "@/components/admin/workspace-table";
import { WorkspaceFilters } from "@/components/admin/workspace-filters";
import { useWorkspaces } from "@/hooks/use-workspaces";
import type { Workspace, PaginatedResponse } from "@/lib/types";
import { PAGINATION } from "@/constants/pagination";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight } from "lucide-react";

export default function WorkspacesPage() {
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [page, setPage] = useState(1);
  const pageSize = PAGINATION.DEFAULT_PAGE_SIZE;

  const status =
    statusFilter === "all"
      ? undefined
      : (statusFilter as "active" | "suspended" | "trial" | "canceled");

  const { data: workspacesData, isLoading } = useWorkspaces({
    status,
    page,
    page_size: pageSize,
    search: searchQuery.trim() || undefined,
  });

  // Extract workspaces array and pagination metadata
  const { workspaces, pagination } = useMemo(() => {
    if (!workspacesData) {
      return { workspaces: [], pagination: null };
    }

    // Check if response is paginated
    if (typeof workspacesData === "object" && "items" in workspacesData) {
      const paginated = workspacesData as PaginatedResponse<Workspace>;
      return {
        workspaces: paginated.items,
        pagination: {
          total: paginated.total,
          page: paginated.page,
          page_size: paginated.page_size,
          total_pages: paginated.total_pages,
        },
      };
    }

    // Legacy array format
    const arrayData = workspacesData as Workspace[];
    return { workspaces: arrayData, pagination: null };
  }, [workspacesData]);

  // Search is now handled by backend API
  // If backend doesn't support search yet, fallback to client-side filtering
  const filteredWorkspaces = useMemo(() => {
    // If search query exists but backend doesn't filter (no search param sent or results don't match),
    // fallback to client-side filtering for backward compatibility
    if (searchQuery.trim() && workspaces.length > 0) {
      // Check if results seem filtered (heuristic: if all results match, backend likely filtered)
      const query = searchQuery.toLowerCase();
      const allMatch = workspaces.every(
        (w) =>
          w.name.toLowerCase().includes(query) ||
          w.owner_email?.toLowerCase().includes(query)
      );

      // If not all match, backend likely filtered - use as-is
      if (!allMatch) {
        return workspaces;
      }

      // Otherwise, apply client-side filter as fallback
      return workspaces.filter(
        (w) =>
          w.name.toLowerCase().includes(query) ||
          w.owner_email?.toLowerCase().includes(query)
      );
    }

    return workspaces;
  }, [workspaces, searchQuery]);

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Workspaces</h1>
          <p className="text-muted-foreground">
            Manage and monitor all workspaces on the platform
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>All Workspaces</CardTitle>
            <CardDescription>
              View and manage workspaces across the platform
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <WorkspaceFilters
              statusFilter={statusFilter}
              onStatusChange={setStatusFilter}
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
            />

            <WorkspaceTable
              workspaces={filteredWorkspaces}
              isLoading={isLoading}
            />

            {filteredWorkspaces.length > 0 && (
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  {pagination
                    ? `Showing ${
                        (pagination.page - 1) * pagination.page_size + 1
                      }-${Math.min(
                        pagination.page * pagination.page_size,
                        pagination.total
                      )} of ${pagination.total} workspaces`
                    : `Showing ${filteredWorkspaces.length} workspace${
                        filteredWorkspaces.length !== 1 ? "s" : ""
                      }`}
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1 || pagination?.page === 1}
                    aria-label="Go to previous page"
                  >
                    <ChevronLeft className="h-4 w-4" />
                    Previous
                  </Button>
                  <span className="text-sm text-muted-foreground">
                    Page {page}
                    {pagination && ` of ${pagination.total_pages}`}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => p + 1)}
                    disabled={
                      pagination
                        ? pagination.page >= pagination.total_pages
                        : filteredWorkspaces.length < pageSize
                    }
                    aria-label="Go to next page"
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
