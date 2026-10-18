"use client";

import { useState } from "react";
import { AdminLayout } from "@/components/layout/admin-layout";
import { AffiliateTable } from "@/components/admin/affiliate-table";
import { AffiliateFilters } from "@/components/admin/affiliate-filters";
import { useAffiliates } from "@/hooks/use-affiliates";
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

export default function AffiliatesPage() {
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [page, setPage] = useState(1);
  const pageSize = PAGINATION.DEFAULT_PAGE_SIZE;

  const status =
    statusFilter === "all"
      ? undefined
      : (statusFilter as "pending" | "approved" | "rejected" | "blocked");

  const {
    data: affiliates = [],
    isLoading,
    error,
  } = useAffiliates({
    status,
    page,
    page_size: pageSize,
  });

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Affiliates</h1>
          <p className="text-muted-foreground">
            Manage affiliate program participants and commissions
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>All Affiliates</CardTitle>
            <CardDescription>
              View and manage affiliates across the platform
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {error && (
              <div className="p-4 bg-red-50 dark:bg-red-900/20 rounded-md">
                <p className="text-sm text-red-800 dark:text-red-200">
                  Error loading affiliates:{" "}
                  {(error as any)?.message || "Unknown error"}
                </p>
              </div>
            )}
            <div className="flex justify-end">
              <AffiliateFilters
                statusFilter={statusFilter}
                onStatusChange={setStatusFilter}
              />
            </div>

            <AffiliateTable affiliates={affiliates} isLoading={isLoading} />

            {affiliates.length > 0 && (
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  Showing {affiliates.length} affiliate
                  {affiliates.length !== 1 ? "s" : ""}
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
                    disabled={affiliates.length < pageSize}
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
