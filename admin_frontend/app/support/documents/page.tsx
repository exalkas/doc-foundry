"use client";

import { useState, useMemo } from "react";
import { AdminLayout } from "@/components/layout/admin-layout";
import { DocumentTable } from "@/components/admin/document-table";
import { DocumentFilters } from "@/components/admin/document-filters";
import { useDocuments } from "@/hooks/use-documents";
import type { Document, PaginatedResponse } from "@/lib/types";
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

export default function DocumentsPage() {
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [fromDate, setFromDate] = useState<string>("");
  const [toDate, setToDate] = useState<string>("");
  const [page, setPage] = useState(1);
  const pageSize = PAGINATION.DEFAULT_PAGE_SIZE;

  const status =
    statusFilter === "all"
      ? undefined
      : (statusFilter as "queued" | "processing" | "completed" | "failed");

  const { data: documentsData, isLoading } = useDocuments({
    status,
    page,
    page_size: pageSize,
    search: searchQuery.trim() || undefined,
    from_date: fromDate || undefined,
    to_date: toDate || undefined,
  });

  // Extract documents array and pagination metadata
  const { documents, pagination } = useMemo(() => {
    if (!documentsData) {
      return { documents: [], pagination: null };
    }

    // Check if response is paginated
    if (typeof documentsData === "object" && "items" in documentsData) {
      const paginated = documentsData as PaginatedResponse<Document>;
      return {
        documents: paginated.items,
        pagination: {
          total: paginated.total,
          page: paginated.page,
          page_size: paginated.page_size,
          total_pages: paginated.total_pages,
        },
      };
    }

    // Legacy array format
    const arrayData = documentsData as Document[];
    return { documents: arrayData, pagination: null };
  }, [documentsData]);

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Documents</h1>
          <p className="text-muted-foreground">
            View and manage all documents across the platform
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>All Documents</CardTitle>
            <CardDescription>
              View and manage document extractions across all workspaces
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <DocumentFilters
              statusFilter={statusFilter}
              onStatusChange={setStatusFilter}
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
              fromDate={fromDate}
              onFromDateChange={setFromDate}
              toDate={toDate}
              onToDateChange={setToDate}
            />

            <DocumentTable documents={documents} isLoading={isLoading} />

            {documents.length > 0 && (
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  {pagination
                    ? `Showing ${
                        (pagination.page - 1) * pagination.page_size + 1
                      }-${Math.min(
                        pagination.page * pagination.page_size,
                        pagination.total
                      )} of ${pagination.total} documents`
                    : `Showing ${documents.length} document${
                        documents.length !== 1 ? "s" : ""
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
                        : documents.length < pageSize
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
