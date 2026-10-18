"use client";

import { useState, useMemo } from "react";
import { AdminLayout } from "@/components/layout/admin-layout";
import { ApiKeyTable } from "@/components/admin/api-key-table";
import { ApiKeyFilters } from "@/components/admin/api-key-filters";
import { RevokeApiKeyModal } from "@/components/admin/revoke-api-key-modal";
import { useApiKeys } from "@/hooks/use-api-keys";
import type { ApiKey, PaginatedResponse } from "@/lib/types";
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

export default function ApiKeysPage() {
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [page, setPage] = useState(1);
  const [selectedApiKey, setSelectedApiKey] = useState<ApiKey | null>(null);
  const pageSize = PAGINATION.DEFAULT_PAGE_SIZE;

  const status =
    statusFilter === "all" ? undefined : (statusFilter as "active" | "revoked");

  const { data: apiKeysData, isLoading } = useApiKeys({
    status,
    page,
    page_size: pageSize,
  });

  // Extract API keys array and pagination metadata
  const { apiKeys, pagination } = useMemo(() => {
    if (!apiKeysData) {
      return { apiKeys: [], pagination: null };
    }

    // Check if response is paginated
    if (typeof apiKeysData === "object" && "items" in apiKeysData) {
      const paginated = apiKeysData as PaginatedResponse<ApiKey>;
      return {
        apiKeys: paginated.items,
        pagination: {
          total: paginated.total,
          page: paginated.page,
          page_size: paginated.page_size,
          total_pages: paginated.total_pages,
        },
      };
    }

    // Legacy array format
    const arrayData = apiKeysData as ApiKey[];
    return { apiKeys: arrayData, pagination: null };
  }, [apiKeysData]);

  const handleRevoke = (apiKeyId: string) => {
    const apiKey = apiKeys.find((k) => k.id === apiKeyId);
    if (apiKey) {
      setSelectedApiKey(apiKey);
    }
  };

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">API Keys</h1>
          <p className="text-muted-foreground">
            View and manage API keys across the platform
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>All API Keys</CardTitle>
            <CardDescription>
              View and manage API keys for all workspaces
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <ApiKeyFilters
              statusFilter={statusFilter}
              onStatusChange={setStatusFilter}
            />

            <ApiKeyTable
              apiKeys={apiKeys}
              isLoading={isLoading}
              onRevoke={handleRevoke}
            />

            {apiKeys.length > 0 && (
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  {pagination
                    ? `Showing ${
                        (pagination.page - 1) * pagination.page_size + 1
                      }-${Math.min(
                        pagination.page * pagination.page_size,
                        pagination.total
                      )} of ${pagination.total} API keys`
                    : `Showing ${apiKeys.length} API key${
                        apiKeys.length !== 1 ? "s" : ""
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
                        : apiKeys.length < pageSize
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

        {selectedApiKey && (
          <RevokeApiKeyModal
            apiKeyId={selectedApiKey.id}
            apiKeyName={selectedApiKey.name}
            open={!!selectedApiKey}
            onOpenChange={(open) => {
              if (!open) setSelectedApiKey(null);
            }}
          />
        )}
      </div>
    </AdminLayout>
  );
}
