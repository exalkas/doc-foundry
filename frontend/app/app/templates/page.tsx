"use client";

import { useState } from "react";
import * as React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Spinner } from "@/components/ui/spinner";
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
import { FileCode2, MoreVertical, Pencil, Trash2, Library } from "lucide-react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { get, del } from "@/lib/api-client";
import type { Template, Project } from "@/lib/types";
import { ROUTES } from "@/lib/constants";
import { useToast } from "@/hooks/use-toast";
import { getSuccessMessage, getErrorMessage } from "@/lib/notifications";
import { FilterBar, type FilterOption } from "@/components/app/filter-bar";
import { DataGrid, type Column } from "@/components/app/data-grid";
import { Pagination } from "@/components/ui/pagination";

export default function TemplatesPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const projectId = searchParams.get("projectId");
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(
    null
  );

  // Filter and pagination state
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("created_at");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");

  const { data: templatesData, isLoading } = useQuery<{
    templates: Template[];
    pagination: {
      page: number;
      page_size: number;
      total: number;
      total_pages: number;
    };
  }>({
    queryKey: [
      "templates",
      projectId,
      page,
      pageSize,
      search,
      sortBy,
      sortOrder,
    ],
    queryFn: () => {
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: pageSize.toString(),
        sort_by: sortBy,
        sort_order: sortOrder,
      });
      if (projectId) {
        params.append("project_id", projectId);
      }
      if (search) {
        params.append("search", search);
      }
      return get(`/api/templates?${params.toString()}`);
    },
  });

  const templates = templatesData?.templates || [];
  const pagination = templatesData?.pagination;

  // Reset to page 1 when filters change
  React.useEffect(() => {
    setPage(1);
  }, [search, sortBy, sortOrder, projectId]);

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

  // Fetch total template count (without project filter) for limit checking
  const { data: allTemplatesData } = useQuery<{
    pagination: {
      total: number;
    };
  }>({
    queryKey: ["templates", "total-count"],
    queryFn: () => get("/api/templates?page=1&page_size=1"),
  });

  // Fetch usage summary to get template limit
  const { data: usageSummary } = useQuery<{
    plan_limits: {
      max_templates: number | null;
    };
  }>({
    queryKey: ["usage-summary"],
    queryFn: () => get("/api/usage/summary"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => del(`/api/templates/${id}`),
    onSuccess: () => {
      toast({
        variant: "success",
        title: getSuccessMessage("delete", "template"),
        description: "Template deleted successfully",
      });
      queryClient.invalidateQueries({ queryKey: ["templates"] });
      setDeleteOpen(false);
      setSelectedTemplate(null);
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Error",
        description: getErrorMessage(error, "delete", "template"),
      });
    },
  });

  const getProjectName = (projectId?: string) => {
    if (!projectId || !projects) return "-";
    const project = projects.find((p) => p.id === projectId);
    return project?.name || "-";
  };

  const handleDelete = (template: Template) => {
    setSelectedTemplate(template);
    setDeleteOpen(true);
  };

  const confirmDelete = () => {
    if (selectedTemplate) {
      deleteMutation.mutate(selectedTemplate.id);
    }
  };

  const handleClearFilters = () => {
    setSearch("");
    setSortBy("created_at");
    setSortOrder("desc");
    setPage(1);
  };

  const handleNewTemplate = (e: React.MouseEvent<HTMLAnchorElement>) => {
    // Use total count from all templates (not filtered by project)
    const currentTemplateCount = allTemplatesData?.pagination?.total || 0;
    const maxTemplates = usageSummary?.plan_limits?.max_templates;

    // Check if limit exists and is reached
    if (
      maxTemplates !== null &&
      maxTemplates !== undefined &&
      currentTemplateCount >= maxTemplates
    ) {
      e.preventDefault();
      e.stopPropagation();
      toast({
        variant: "destructive",
        title: "Template limit reached",
        description: `You have reached the limit of ${maxTemplates} templates. Please delete an existing template or upgrade your plan to create more templates.`,
      });
      return false;
    }

    // Allow navigation if no limit or limit not reached
    return true;
  };

  // Check if template limit is reached
  const isTemplateLimitReached = React.useMemo(() => {
    if (!allTemplatesData || !usageSummary) return false;
    const currentTemplateCount = allTemplatesData.pagination?.total || 0;
    const maxTemplates = usageSummary.plan_limits?.max_templates;
    return (
      maxTemplates !== null &&
      maxTemplates !== undefined &&
      currentTemplateCount >= maxTemplates
    );
  }, [allTemplatesData, usageSummary]);

  // Check if we're still loading the limit data
  const isLoadingLimitCheck = !allTemplatesData || !usageSummary;

  const sortOptions: FilterOption[] = [
    { label: "Name", value: "name" },
    { label: "Document Type", value: "document_type" },
    { label: "Created Date", value: "created_at" },
    { label: "Updated Date", value: "updated_at" },
  ];

  const columns: Column<Template>[] = [
    {
      key: "name",
      header: "Name",
      cell: (template) => (
        <Link
          href={`${ROUTES.TEMPLATES}/${template.id}/edit`}
          className="font-medium text-foreground hover:underline"
          onClick={(e) => e.stopPropagation()}
        >
          {template.name}
        </Link>
      ),
    },
    {
      key: "project",
      header: "Project",
      cell: (template) => (
        <div className="text-muted-foreground">
          {getProjectName(template.project_id)}
        </div>
      ),
    },
    {
      key: "document_type",
      header: "Document type",
      cell: (template) => (
        <div className="text-muted-foreground">
          {template.document_type || <span className="italic">-</span>}
        </div>
      ),
    },
    {
      key: "created_at",
      header: "Created",
      cell: (template) => (
        <div className="text-muted-foreground">
          {template.created_at ? (
            new Date(template.created_at).toLocaleDateString()
          ) : (
            <span className="italic">-</span>
          )}
        </div>
      ),
    },
    {
      key: "last_run",
      header: "Last run",
      cell: (template) => (
        <div className="text-muted-foreground">
          {template.last_run_at ? (
            new Date(template.last_run_at).toLocaleDateString()
          ) : (
            <span className="italic">-</span>
          )}
        </div>
      ),
    },
    {
      key: "success_rate",
      header: "Success rate",
      cell: (template) => (
        <div className="text-foreground">
          {template.success_count + template.failure_count > 0 ? (
            `${Math.round(
              (template.success_count /
                (template.success_count + template.failure_count)) *
                100
            )}%`
          ) : (
            <span className="text-muted-foreground italic">-</span>
          )}
        </div>
      ),
    },
    {
      key: "actions",
      header: "",
      cell: (template) => (
        <div className="flex justify-end" onClick={(e) => e.stopPropagation()}>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                onClick={() =>
                  router.push(`${ROUTES.TEMPLATES}/${template.id}/edit`)
                }
              >
                <Pencil className="mr-2 h-4 w-4" />
                Edit
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => handleDelete(template)}
                className="text-destructive"
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Templates</h1>
          <p className="text-muted-foreground">
            View and manage all company templates
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" asChild>
            <Link href={ROUTES.TEMPLATE_LIBRARY}>
              <Library className="mr-2 h-4 w-4" />
              Browse Library
            </Link>
          </Button>
          {isTemplateLimitReached ? (
            <Button
              disabled
              onClick={() => {
                const maxTemplates = usageSummary?.plan_limits?.max_templates;
                toast({
                  variant: "destructive",
                  title: "Template limit reached",
                  description: `You have reached the limit of ${maxTemplates} templates. Please delete an existing template or upgrade your plan to create more templates.`,
                });
              }}
            >
              <FileCode2 className="mr-2 h-4 w-4" />
              New template
            </Button>
          ) : (
            <Button asChild disabled={isLoadingLimitCheck}>
              <Link
                href={`${ROUTES.TEMPLATES}/new/edit${
                  projectId ? `?projectId=${projectId}` : ""
                }`}
                onClick={handleNewTemplate}
              >
                <FileCode2 className="mr-2 h-4 w-4" />
                New template
              </Link>
            </Button>
          )}
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All templates</CardTitle>
          <CardDescription>Manage your extraction templates</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <FilterBar
            searchValue={search}
            onSearchChange={setSearch}
            searchPlaceholder="Search templates by name or description..."
            sortBy={sortBy}
            onSortByChange={setSortBy}
            sortOrder={sortOrder}
            onSortOrderChange={setSortOrder}
            sortOptions={sortOptions}
            onClear={handleClearFilters}
          />

          <DataGrid
            data={templates}
            columns={columns}
            isLoading={isLoading}
            emptyMessage="No templates found. Create your first template to get started."
            onRowClick={(template) =>
              router.push(`${ROUTES.TEMPLATES}/${template.id}/edit`)
            }
          />

          {pagination && pagination.total > 0 && (
            <Pagination
              currentPage={pagination.page}
              totalPages={pagination.total_pages}
              totalItems={pagination.total}
              pageSize={pagination.page_size}
              onPageChange={setPage}
              onPageSizeChange={(newSize) => {
                setPageSize(newSize);
                setPage(1);
              }}
            />
          )}
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete template?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete the template "
              {selectedTemplate?.name}". This action cannot be undone. Documents
              that used this template will not be affected, but you won't be
              able to use this template for new extractions.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDelete}
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
