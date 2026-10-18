"use client";

import { useState, useEffect, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { Badge } from "@/components/ui/badge";
import { Pagination } from "@/components/ui/pagination";
import {
  FileText,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  AlertCircle,
  Search,
  X,
  UploadCloud,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { get, del } from "@/lib/api-client";
import type {
  Document,
  Project,
  PaginatedDocumentsResponse,
} from "@/lib/types";
import { ROUTES } from "@/lib/constants";
import { useToast } from "@/hooks/use-toast";
import { getSuccessMessage, getErrorMessage } from "@/lib/notifications";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

const statusConfig = {
  pending: {
    label: "Pending",
    icon: Clock,
    variant: "secondary" as const,
  },
  queued: {
    label: "Queued",
    icon: Clock,
    variant: "secondary" as const,
  },
  processing: {
    label: "Processing",
    icon: Loader2,
    variant: "default" as const,
  },
  scanned: {
    label: "Scanned - Apply Template",
    icon: FileText,
    variant: "secondary" as const,
  },
  completed: {
    label: "Completed - Ready to Export",
    icon: CheckCircle2,
    variant: "default" as const,
  },
  failed: {
    label: "Failed",
    icon: XCircle,
    variant: "destructive" as const,
  },
  // needs_review is now stored in ExtractionResult metadata, not document status
  // Keeping for backward compatibility but will be removed
  needs_review: {
    label: "Needs Review",
    icon: AlertCircle,
    variant: "secondary" as const,
  },
};

type DateRangePreset = "all" | "7d" | "30d" | "month" | "3months";

const dateRangeOptions: { value: DateRangePreset; label: string }[] = [
  { value: "all", label: "All time" },
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "month", label: "This month" },
  { value: "3months", label: "Last 3 months" },
];

function getDateRange(preset: DateRangePreset): {
  date_from?: string;
  date_to?: string;
} {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

  switch (preset) {
    case "7d": {
      const dateFrom = new Date(today);
      dateFrom.setDate(dateFrom.getDate() - 7);
      return {
        date_from: dateFrom.toISOString(),
        date_to: now.toISOString(),
      };
    }
    case "30d": {
      const dateFrom = new Date(today);
      dateFrom.setDate(dateFrom.getDate() - 30);
      return {
        date_from: dateFrom.toISOString(),
        date_to: now.toISOString(),
      };
    }
    case "month": {
      const dateFrom = new Date(today.getFullYear(), today.getMonth(), 1);
      return {
        date_from: dateFrom.toISOString(),
        date_to: now.toISOString(),
      };
    }
    case "3months": {
      const dateFrom = new Date(today);
      dateFrom.setMonth(dateFrom.getMonth() - 3);
      return {
        date_from: dateFrom.toISOString(),
        date_to: now.toISOString(),
      };
    }
    case "all":
    default:
      return {};
  }
}

function getPresetFromDates(
  dateFrom?: string | null,
  dateTo?: string | null
): DateRangePreset {
  if (!dateFrom || !dateTo) return "all";

  const { date_from, date_to } = getDateRange("7d");
  if (dateFrom === date_from && dateTo === date_to) return "7d";

  const { date_from: df30, date_to: dt30 } = getDateRange("30d");
  if (dateFrom === df30 && dateTo === dt30) return "30d";

  const { date_from: dfMonth, date_to: dtMonth } = getDateRange("month");
  if (dateFrom === dfMonth && dateTo === dtMonth) return "month";

  const { date_from: df3m, date_to: dt3m } = getDateRange("3months");
  if (dateFrom === df3m && dateTo === dt3m) return "3months";

  return "all";
}

export default function DocumentsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // Get filter values from URL
  const projectId = searchParams.get("projectId");
  const statusFilter = searchParams.get("status");
  const searchQuery = searchParams.get("search") || "";
  const dateFrom = searchParams.get("date_from") || null;
  const dateTo = searchParams.get("date_to") || null;
  const page = parseInt(searchParams.get("page") || "1", 10);
  const pageSize = parseInt(searchParams.get("page_size") || "20", 10);

  // Local state for search input (debounced)
  const [searchInput, setSearchInput] = useState(searchQuery);

  // Update URL params helper
  const updateParams = useCallback(
    (updates: Record<string, string | null>) => {
      const params = new URLSearchParams(searchParams.toString());

      // Reset to page 1 when filters change (except when updating page itself)
      // When page_size changes, we'll explicitly set page to 1 in the updates
      if (!updates.page && !updates.page_size) {
        params.delete("page");
      }

      Object.entries(updates).forEach(([key, value]) => {
        if (value === null || value === "" || value === "all") {
          params.delete(key);
        } else {
          params.set(key, value);
        }
      });

      router.replace(`${ROUTES.DOCUMENTS}?${params.toString()}`);
    },
    [router, searchParams]
  );

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchInput !== searchQuery) {
        updateParams({ search: searchInput || null });
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [searchInput, searchQuery, updateParams]);

  // Build API query params
  const buildQueryParams = useCallback(() => {
    const params = new URLSearchParams();
    if (projectId) params.append("project_id", projectId);
    if (statusFilter) params.append("status", statusFilter);
    if (searchQuery) params.append("search", searchQuery);
    if (dateFrom) params.append("date_from", dateFrom);
    if (dateTo) params.append("date_to", dateTo);
    params.append("page", page.toString());
    // Ensure page_size is always set and is a valid number
    const validPageSize = pageSize > 0 ? pageSize : 20;
    params.append("page_size", validPageSize.toString());
    params.append("sort", "created_at");
    params.append("order", "desc");
    return params.toString();
  }, [projectId, statusFilter, searchQuery, dateFrom, dateTo, page, pageSize]);

  const { data: documentsData, isLoading } =
    useQuery<PaginatedDocumentsResponse>({
      queryKey: [
        "documents",
        projectId,
        statusFilter,
        searchQuery,
        dateFrom,
        dateTo,
        page,
        pageSize,
      ],
      queryFn: () => {
        // Build params fresh each time to ensure we use the latest values
        const params = new URLSearchParams();
        if (projectId) params.append("project_id", projectId);
        if (statusFilter) params.append("status", statusFilter);
        if (searchQuery) params.append("search", searchQuery);
        if (dateFrom) params.append("date_from", dateFrom);
        if (dateTo) params.append("date_to", dateTo);
        params.append("page", page.toString());
        const validPageSize = pageSize > 0 ? pageSize : 20;
        params.append("page_size", validPageSize.toString());
        params.append("sort", "created_at");
        params.append("order", "desc");
        return get(`/api/documents?${params.toString()}`);
      },
      refetchInterval: (query) => {
        const data = query.state.data;
        if (!data || !data.documents || data.documents.length === 0)
          return false;
        // Poll if any document is still processing, pending, or queued
        const hasProcessing = data.documents.some(
          (doc) => doc.status === "processing" || doc.status === "pending"
        );
        return hasProcessing ? 3000 : false;
      },
    });

  const { data: projectsData } = useQuery<{
    projects: Project[];
    pagination: {
      page: number;
      page_size: number;
      total: number;
      total_pages: number;
    };
  }>({
    queryKey: ["projects"],
    queryFn: () => get("/api/projects"),
  });

  const projects = projectsData?.projects || [];
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const documents = documentsData?.documents || [];
  const pagination = documentsData?.pagination;

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [documentToDelete, setDocumentToDelete] = useState<Document | null>(null);

  const deleteMutation = useMutation({
    mutationFn: (documentId: string) => del(`/api/documents/${documentId}`),
    onSuccess: () => {
      toast({
        variant: "success",
        title: getSuccessMessage("delete", "document"),
        description: "Document deleted successfully. Scanned data and extraction results are preserved.",
      });
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      setDeleteDialogOpen(false);
      setDocumentToDelete(null);
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Error",
        description: getErrorMessage(error, "delete", "document"),
      });
    },
  });

  const handleDeleteClick = (document: Document) => {
    setDocumentToDelete(document);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = () => {
    if (documentToDelete) {
      deleteMutation.mutate(documentToDelete.id);
    }
  };

  const getProjectName = (projectId?: string) => {
    if (!projectId || !projects) return "-";
    const project = projects.find((p) => p.id === projectId);
    return project?.name || "-";
  };

  const getStatusBadge = (status: Document["status"]) => {
    const config = statusConfig[status];
    const Icon = config.icon;
    return (
      <Badge
        variant={config.variant}
        className="flex items-center gap-1 px-2 py-1"
      >
        <Icon className="h-3 w-3" />
        {config.label}
      </Badge>
    );
  };

  const handleDateRangeChange = (preset: DateRangePreset) => {
    const dateRange = getDateRange(preset);
    updateParams({
      date_from: dateRange.date_from || null,
      date_to: dateRange.date_to || null,
    });
  };

  const handleResetFilters = () => {
    router.push(ROUTES.DOCUMENTS);
  };

  const hasActiveFilters =
    projectId || statusFilter || searchQuery || dateFrom || dateTo;

  const currentDatePreset = getPresetFromDates(dateFrom, dateTo);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Documents</h1>
          <p className="text-muted-foreground">
            View and manage all uploaded documents
          </p>
        </div>
        <Button asChild>
          <Link href={ROUTES.UPLOAD}>
            <UploadCloud className="mr-2 h-4 w-4" />
            Upload Documents
          </Link>
        </Button>
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>All documents</CardTitle>
                <CardDescription>
                  {pagination
                    ? `${pagination.total} document${
                        pagination.total !== 1 ? "s" : ""
                      } found`
                    : "Loading..."}
                </CardDescription>
              </div>
            </div>

            {/* Filter Bar */}
            <div className="flex flex-col sm:flex-row gap-3 pt-2 border-t border-border">
              {/* Search Input */}
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="Search by file name..."
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  className={`pl-9 ${
                    searchInput ? "pr-9" : ""
                  } bg-background border-input text-foreground placeholder:text-muted-foreground dark:bg-background dark:border-input dark:text-foreground`}
                />
                {searchInput && (
                  <button
                    type="button"
                    onClick={() => setSearchInput("")}
                    className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground hover:text-foreground transition-colors"
                    aria-label="Clear search"
                  >
                    <X className="h-4 w-4" />
                  </button>
                )}
              </div>

              {/* Status Filter */}
              <Select
                value={statusFilter || "all"}
                onValueChange={(value) => {
                  updateParams({ status: value === "all" ? null : value });
                }}
              >
                <SelectTrigger className="w-full sm:w-[150px] bg-background border-input text-foreground dark:bg-background dark:border-input dark:text-foreground">
                  <SelectValue placeholder="Filter by status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All statuses</SelectItem>
                  <SelectItem value="pending">Pending</SelectItem>
                  <SelectItem value="processing">Processing</SelectItem>
                  <SelectItem value="scanned">
                    Scanned - Apply Template
                  </SelectItem>
                  <SelectItem value="completed">
                    Completed - Ready to Export
                  </SelectItem>
                  <SelectItem value="failed">Failed</SelectItem>
                </SelectContent>
              </Select>

              {/* Project Filter */}
              <Select
                value={projectId || "all"}
                onValueChange={(value) => {
                  updateParams({ projectId: value === "all" ? null : value });
                }}
              >
                <SelectTrigger className="w-full sm:w-[200px] bg-background border-input text-foreground dark:bg-background dark:border-input dark:text-foreground">
                  <SelectValue placeholder="Filter by project" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All projects</SelectItem>
                  {projects?.map((project) => (
                    <SelectItem key={project.id} value={project.id}>
                      {project.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {/* Date Range Filter */}
              <Select
                value={currentDatePreset}
                onValueChange={(value) =>
                  handleDateRangeChange(value as DateRangePreset)
                }
              >
                <SelectTrigger className="w-full sm:w-[180px] bg-background border-input text-foreground dark:bg-background dark:border-input dark:text-foreground">
                  <SelectValue placeholder="Date range" />
                </SelectTrigger>
                <SelectContent>
                  {dateRangeOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {/* Reset Filters Button */}
              {hasActiveFilters && (
                <Button
                  variant="outline"
                  onClick={handleResetFilters}
                  className="w-full sm:w-auto bg-background border-input text-foreground hover:bg-accent hover:text-accent-foreground dark:bg-background dark:border-input dark:text-foreground dark:hover:bg-accent dark:hover:text-accent-foreground"
                >
                  <X className="h-4 w-4 mr-2" />
                  Reset
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {documents && documents.length > 0 ? (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>File name</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Project</TableHead>
                    <TableHead>Pages</TableHead>
                    <TableHead>Source</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead className="w-[100px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {documents.map((document) => (
                    <TableRow key={document.id}>
                      <TableCell>
                        <Link
                          href={`${ROUTES.DOCUMENTS}/${document.id}`}
                          className="font-medium hover:underline flex items-center gap-2"
                        >
                          <FileText className="h-4 w-4 text-muted-foreground" />
                          {document.file_name}
                        </Link>
                      </TableCell>
                      <TableCell>{getStatusBadge(document.status)}</TableCell>
                      <TableCell className="text-muted-foreground">
                        {getProjectName(document.project_id)}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {document.pages || "-"}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">
                          {document.source === "ui" ? "UI" : "API"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {new Date(document.created_at).toLocaleString()}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteClick(document)}
                          disabled={deleteMutation.isPending}
                          className="text-destructive hover:text-destructive hover:bg-destructive/10"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {/* Pagination */}
              {pagination && pagination.total > 0 && (
                <div className="mt-6">
                  <Pagination
                    currentPage={pagination.page}
                    totalPages={pagination.total_pages}
                    totalItems={pagination.total}
                    pageSize={pageSize}
                    defaultPageSize={20}
                    onPageChange={(newPage) => {
                      updateParams({ page: newPage.toString() });
                    }}
                    onPageSizeChange={(newPageSize) => {
                      updateParams({
                        page_size: newPageSize.toString(),
                        page: "1", // Reset to first page
                      });
                    }}
                    pageSizeOptions={[10, 20, 30, 50, 100]}
                  />
                </div>
              )}
            </>
          ) : (
            <div className="text-center py-8">
              <p className="text-muted-foreground">
                {hasActiveFilters
                  ? "No documents found matching the selected filters."
                  : "No documents yet. Upload your first document to get started."}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete document?</AlertDialogTitle>
            <AlertDialogDescription>
              This will remove the document from your list, but all scanned data (OCR text, metadata) and extraction results will be preserved. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setDocumentToDelete(null)}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteConfirm}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
