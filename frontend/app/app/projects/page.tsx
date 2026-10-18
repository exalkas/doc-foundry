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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  FolderPlus,
  MoreVertical,
  Pencil,
  Trash2,
  UploadCloud,
  FileCode2,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { get, post, put, del } from "@/lib/api-client";
import type { Project } from "@/lib/types";
import { ROUTES } from "@/lib/constants";
import { HelpText } from "@/components/app/help-text";
import { FilterBar, type FilterOption } from "@/components/app/filter-bar";
import { DataGrid, type Column } from "@/components/app/data-grid";
import { Pagination } from "@/components/ui/pagination";
import { useToast } from "@/hooks/use-toast";
import { getSuccessMessage, getErrorMessage } from "@/lib/notifications";

export default function ProjectsPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [formData, setFormData] = useState({ name: "", description: "" });

  // Filter and pagination state
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("created_at");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");

  const { data: projectsData, isLoading } = useQuery<{
    projects: Project[];
    pagination: {
      page: number;
      page_size: number;
      total: number;
      total_pages: number;
    };
  }>({
    queryKey: ["projects", page, pageSize, search, sortBy, sortOrder],
    queryFn: () => {
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: pageSize.toString(),
        sort_by: sortBy,
        sort_order: sortOrder,
      });
      if (search) {
        params.append("search", search);
      }
      return get(`/api/projects?${params.toString()}`);
    },
  });

  const projects = projectsData?.projects || [];
  const pagination = projectsData?.pagination;

  // Reset to page 1 when filters change
  React.useEffect(() => {
    setPage(1);
  }, [search, sortBy, sortOrder]);

  const createMutation = useMutation({
    mutationFn: (data: { name: string; description?: string }) =>
      post<{ project: Project }>("/api/projects", data),
    onSuccess: () => {
      toast({
        variant: "success",
        title: getSuccessMessage("create", "project"),
        description: "Project created successfully",
      });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setCreateOpen(false);
      setFormData({ name: "", description: "" });
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Error",
        description: getErrorMessage(error, "create", "project"),
      });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      data: { name: string; description?: string };
    }) => put<{ project: Project }>(`/api/projects/${id}`, data),
    onSuccess: () => {
      toast({
        variant: "success",
        title: getSuccessMessage("update", "project"),
        description: "Project updated successfully",
      });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setEditOpen(false);
      setSelectedProject(null);
      setFormData({ name: "", description: "" });
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Error",
        description: getErrorMessage(error, "update", "project"),
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => del(`/api/projects/${id}`),
    onSuccess: () => {
      toast({
        variant: "success",
        title: getSuccessMessage("delete", "project"),
        description: "Project deleted successfully",
      });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setDeleteOpen(false);
      setSelectedProject(null);
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Error",
        description: getErrorMessage(error, "delete", "project"),
      });
    },
  });

  const handleCreate = () => {
    createMutation.mutate(formData);
  };

  const handleEdit = (project: Project) => {
    setSelectedProject(project);
    setFormData({ name: project.name, description: project.description || "" });
    setEditOpen(true);
  };

  const handleUpdate = () => {
    if (selectedProject) {
      updateMutation.mutate({ id: selectedProject.id, data: formData });
    }
  };

  const handleDelete = (project: Project) => {
    setSelectedProject(project);
    setDeleteOpen(true);
  };

  const confirmDelete = () => {
    if (selectedProject) {
      deleteMutation.mutate(selectedProject.id);
    }
  };

  const handleClearFilters = () => {
    setSearch("");
    setSortBy("created_at");
    setSortOrder("desc");
    setPage(1);
  };

  const sortOptions: FilterOption[] = [
    { label: "Name", value: "name" },
    { label: "Created Date", value: "created_at" },
    { label: "Updated Date", value: "updated_at" },
  ];

  const columns: Column<Project>[] = [
    {
      key: "name",
      header: "Name",
      cell: (project) => (
        <Link
          href={`${ROUTES.PROJECTS}/${project.id}`}
          className="font-medium text-foreground hover:underline"
          onClick={(e) => e.stopPropagation()}
        >
          {project.name}
        </Link>
      ),
    },
    {
      key: "description",
      header: "Description",
      cell: (project) => (
        <div className="text-muted-foreground">
          {project.description || (
            <span className="italic">No description</span>
          )}
        </div>
      ),
    },
    {
      key: "created_at",
      header: "Created",
      cell: (project) => (
        <div className="text-muted-foreground">
          {new Date(project.created_at).toLocaleDateString()}
        </div>
      ),
    },
    {
      key: "actions",
      header: "",
      cell: (project) => (
        <div className="flex justify-end" onClick={(e) => e.stopPropagation()}>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => handleEdit(project)}>
                <Pencil className="mr-2 h-4 w-4" />
                Edit
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => handleDelete(project)}
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
          <h1 className="text-3xl font-bold tracking-tight">Projects</h1>
          <p className="text-muted-foreground">
            Organize documents and templates into project folders. Useful for
            invoice processing, client records, contract reviews, tax documents,
            medical records, and more.
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <FolderPlus className="mr-2 h-4 w-4" />
          New project
        </Button>
      </div>

      <HelpText
        title="Real-world use case examples"
        defaultOpen={false}
        content={
          <div className="space-y-4">
            <div>
              <p className="font-medium text-foreground mb-2">
                📊 Accountants & Bookkeepers
              </p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li>
                  <strong>By Client:</strong> "Company A Invoices", "XYZ Corp -
                  2024", "ABC Ltd Tax Prep"
                </li>
                <li>
                  <strong>By Document Type:</strong> "Vendor Invoices",
                  "Receipts - Q4 2024", "Expense Reports"
                </li>
                <li>
                  <strong>By Tax Year:</strong> "2024 Tax Returns", "2023 Audit
                  Documents"
                </li>
              </ul>
            </div>
            <div>
              <p className="font-medium text-foreground mb-2">⚖️ Legal Firms</p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li>
                  <strong>By Case:</strong> "Smith vs. Jones", "Patent
                  Application #12345"
                </li>
                <li>
                  <strong>By Document Type:</strong> "Contract Reviews",
                  "Compliance Documents", "Merger Agreements"
                </li>
                <li>
                  <strong>By Client:</strong> "Client A - All Documents",
                  "Client B - Contracts Only"
                </li>
              </ul>
            </div>
            <div>
              <p className="font-medium text-foreground mb-2">
                🏥 Healthcare & Medical
              </p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li>
                  <strong>By Department:</strong> "Cardiology Reports", "Lab
                  Results", "Radiology"
                </li>
                <li>
                  <strong>By Patient Group:</strong> "Patient Records - Q1",
                  "Insurance Claims"
                </li>
                <li>
                  <strong>By Document Type:</strong> "Medical Reports",
                  "Prescription Forms", "Billing Statements"
                </li>
              </ul>
            </div>
            <div>
              <p className="font-medium text-foreground mb-2">🏢 Real Estate</p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li>
                  <strong>By Property:</strong> "123 Main St - All Documents",
                  "Downtown Office Building"
                </li>
                <li>
                  <strong>By Transaction:</strong> "Lease Agreements", "Purchase
                  Contracts", "Property Listings"
                </li>
                <li>
                  <strong>By Client:</strong> "Buyer Documents", "Seller
                  Documents"
                </li>
              </ul>
            </div>
            <div>
              <p className="font-medium text-foreground mb-2">
                💼 HR & Recruitment
              </p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li>
                  <strong>By Department:</strong> "Engineering Resumes", "Sales
                  Applications"
                </li>
                <li>
                  <strong>By Process:</strong> "Benefits Enrollment",
                  "Performance Reviews", "Onboarding Documents"
                </li>
                <li>
                  <strong>By Position:</strong> "Senior Developer - 2024",
                  "Marketing Manager"
                </li>
              </ul>
            </div>
            <div>
              <p className="font-medium text-foreground mb-2">
                📦 Supply Chain & Procurement
              </p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li>
                  <strong>By Vendor:</strong> "Vendor A - All Invoices",
                  "Supplier B - Purchase Orders"
                </li>
                <li>
                  <strong>By Department:</strong> "IT Procurement", "Office
                  Supplies", "Manufacturing Materials"
                </li>
                <li>
                  <strong>By Document Type:</strong> "Purchase Orders",
                  "Shipping Documents", "Vendor Contracts"
                </li>
              </ul>
            </div>
            <div className="pt-2 border-t">
              <p className="text-sm text-muted-foreground">
                <strong>Tip:</strong> Create a project for each logical
                grouping. You can have multiple templates per project, and all
                documents uploaded to a project will be organized together.
              </p>
            </div>
          </div>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>All projects</CardTitle>
          <CardDescription>Manage your project folders</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <FilterBar
            searchValue={search}
            onSearchChange={setSearch}
            searchPlaceholder="Search projects by name or description..."
            sortBy={sortBy}
            onSortByChange={setSortBy}
            sortOrder={sortOrder}
            onSortOrderChange={setSortOrder}
            sortOptions={sortOptions}
            onClear={handleClearFilters}
          />

          {!isLoading && projects.length === 0 && !search ? (
            <div className="flex flex-col items-center justify-center py-16 px-4">
              <div className="max-w-md text-center space-y-6">
                <div className="space-y-2">
                  <h3 className="text-xl font-semibold text-foreground">
                    Get started with projects
                  </h3>
                  <p className="text-muted-foreground">
                    Projects help you organize documents and templates. Create
                    your first project to get started, or explore templates and
                    upload documents.
                  </p>
                </div>
                <div className="flex flex-col sm:flex-row gap-3 justify-center">
                  <Button onClick={() => setCreateOpen(true)} size="lg">
                    <FolderPlus className="mr-2 h-4 w-4" />
                    Create your first project
                  </Button>
                  <div className="flex flex-col sm:flex-row gap-3">
                    <Button
                      variant="outline"
                      size="lg"
                      asChild
                      className="w-full sm:w-auto"
                    >
                      <Link href={ROUTES.UPLOAD}>
                        <UploadCloud className="mr-2 h-4 w-4" />
                        Upload documents
                      </Link>
                    </Button>
                    <Button
                      variant="outline"
                      size="lg"
                      asChild
                      className="w-full sm:w-auto"
                    >
                      <Link href={ROUTES.TEMPLATES}>
                        <FileCode2 className="mr-2 h-4 w-4" />
                        Browse templates
                      </Link>
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <>
              <DataGrid
                data={projects}
                columns={columns}
                isLoading={isLoading}
                emptyMessage={
                  search
                    ? "No projects found matching your search. Try adjusting your filters."
                    : "No projects found. Create your first project to get started."
                }
                onRowClick={(project) =>
                  router.push(`${ROUTES.PROJECTS}/${project.id}`)
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
            </>
          )}
        </CardContent>
      </Card>

      {/* Create Project Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create project</DialogTitle>
            <DialogDescription>
              Create a new project folder to organize your documents and
              templates.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="name">Project name</Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                placeholder="e.g. Invoices Q4"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
                placeholder="Optional description"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleCreate}
              disabled={!formData.name || createMutation.isPending}
            >
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Project Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rename project</DialogTitle>
            <DialogDescription>
              Update the project name and description.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="edit-name">Project name</Label>
              <Input
                id="edit-name"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-description">Description</Label>
              <Textarea
                id="edit-description"
                value={formData.description}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleUpdate}
              disabled={!formData.name || updateMutation.isPending}
            >
              Save changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete project?</AlertDialogTitle>
            <AlertDialogDescription>
              This will not delete already processed documents, but will remove
              the folder organization. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
