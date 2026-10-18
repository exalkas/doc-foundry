"use client";

import { useState, useMemo } from "react";
import { AdminLayout } from "@/components/layout/admin-layout";
import { WebhookTable } from "@/components/admin/webhook-table";
import { WebhookFilters } from "@/components/admin/webhook-filters";
import { useWebhooks } from "@/hooks/use-webhooks";
import type { Webhook, PaginatedResponse } from "@/lib/types";
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

export default function WebhooksPage() {
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [page, setPage] = useState(1);
  const pageSize = PAGINATION.DEFAULT_PAGE_SIZE;

  const status =
    statusFilter === "all"
      ? undefined
      : (statusFilter as "active" | "inactive" | "failed");

  const { data: webhooksData, isLoading } = useWebhooks({
    status,
    page,
    page_size: pageSize,
  });

  // Extract webhooks array and pagination metadata
  const { webhooks, pagination } = useMemo(() => {
    if (!webhooksData) {
      return { webhooks: [], pagination: null };
    }

    // Check if response is paginated
    if (typeof webhooksData === "object" && "items" in webhooksData) {
      const paginated = webhooksData as PaginatedResponse<Webhook>;
      return {
        webhooks: paginated.items,
        pagination: {
          total: paginated.total,
          page: paginated.page,
          page_size: paginated.page_size,
          total_pages: paginated.total_pages,
        },
      };
    }

    // Legacy array format
    const arrayData = webhooksData as Webhook[];
    return { webhooks: arrayData, pagination: null };
  }, [webhooksData]);

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Webhooks</h1>
          <p className="text-muted-foreground">
            View and manage webhook configurations across the platform
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>All Webhooks</CardTitle>
            <CardDescription>
              View and manage webhook configurations for all workspaces
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <WebhookFilters
              statusFilter={statusFilter}
              onStatusChange={setStatusFilter}
            />

            <WebhookTable webhooks={webhooks} isLoading={isLoading} />

            {webhooks.length > 0 && (
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  {pagination
                    ? `Showing ${
                        (pagination.page - 1) * pagination.page_size + 1
                      }-${Math.min(
                        pagination.page * pagination.page_size,
                        pagination.total
                      )} of ${pagination.total} webhooks`
                    : `Showing ${webhooks.length} webhook${
                        webhooks.length !== 1 ? "s" : ""
                      }`}
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1 || pagination?.page === 1}
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
                        : webhooks.length < pageSize
                    }
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
