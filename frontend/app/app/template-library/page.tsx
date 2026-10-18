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
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Spinner } from "@/components/ui/spinner";
import { Search, Library } from "lucide-react";
import { useRouter } from "next/navigation";
import { get, post } from "@/lib/api-client";
import type { LibraryTemplate, Project } from "@/lib/types";
import {
  ROUTES,
  TEMPLATE_CATEGORIES,
  TEMPLATE_CATEGORY_LABELS,
} from "@/lib/constants";
import { useToast } from "@/hooks/use-toast";
import { getSuccessMessage, getErrorMessage } from "@/lib/notifications";
import { TemplateLibraryCard } from "@/components/app/template-library-card";
import { ImportTemplateDialog } from "@/components/app/import-template-dialog";

export default function TemplateLibraryPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [selectedTemplate, setSelectedTemplate] =
    useState<LibraryTemplate | null>(null);

  const { data: libraryTemplates, isLoading } = useQuery<LibraryTemplate[]>({
    queryKey: ["template-library", selectedCategory, search],
    queryFn: () => {
      const params = new URLSearchParams();
      if (selectedCategory) {
        params.append("category", selectedCategory);
      }
      if (search) {
        params.append("search", search);
      }
      return get(`/api/template-library?${params.toString()}`);
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

  // Fetch total template count and usage summary to check limit before importing
  const { data: allTemplatesData } = useQuery<{
    pagination: {
      total: number;
    };
  }>({
    queryKey: ["templates", "total-count"],
    queryFn: () => get("/api/templates?page=1&page_size=1"),
  });

  const { data: usageSummary } = useQuery<{
    plan_limits: {
      max_templates: number | null;
    };
  }>({
    queryKey: ["usage-summary"],
    queryFn: () => get("/api/usage/summary"),
  });

  const importMutation = useMutation<
    {
      id: string;
      workspace_id: string;
      project_id?: string;
      name: string;
      description?: string;
      document_type?: string;
      library_template_id?: string;
      created_at: string;
    },
    unknown,
    {
      library_template_id: string;
      name?: string;
      project_id?: string;
    }
  >({
    mutationFn: (data) =>
      post<{
        id: string;
        workspace_id: string;
        project_id?: string;
        name: string;
        description?: string;
        document_type?: string;
        library_template_id?: string;
        created_at: string;
      }>(`/api/template-library/${data.library_template_id}/import`, {
        name: data.name,
        project_id: data.project_id,
      }),
    onSuccess: (data) => {
      toast({
        variant: "success",
        title: getSuccessMessage("create", "template"),
        description: "Template imported successfully",
      });
      queryClient.invalidateQueries({ queryKey: ["templates"] });
      setImportDialogOpen(false);
      setSelectedTemplate(null);
      // Optionally navigate to the imported template
      router.push(`${ROUTES.TEMPLATES}/${data.id}/edit`);
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Error",
        description: getErrorMessage(error, "create", "template"),
      });
    },
  });

  const handleImport = (template: LibraryTemplate) => {
    // Check template limit before opening import dialog
    const currentTemplateCount = allTemplatesData?.pagination?.total || 0;
    const maxTemplates = usageSummary?.plan_limits?.max_templates;

    if (
      maxTemplates !== null &&
      maxTemplates !== undefined &&
      currentTemplateCount >= maxTemplates
    ) {
      toast({
        variant: "destructive",
        title: "Template limit reached",
        description: `You have reached the limit of ${maxTemplates} templates. Please delete an existing template or upgrade your plan to import more templates.`,
      });
      return;
    }

    setSelectedTemplate(template);
    setImportDialogOpen(true);
  };

  const handleImportConfirm = (name?: string, projectId?: string) => {
    if (selectedTemplate) {
      importMutation.mutate({
        library_template_id: selectedTemplate.id,
        name,
        project_id: projectId,
      });
    }
  };

  const categories = [
    { value: null, label: "All Categories" },
    {
      value: TEMPLATE_CATEGORIES.ACCOUNTING_FINANCE,
      label: TEMPLATE_CATEGORY_LABELS.accounting_finance,
    },
    {
      value: TEMPLATE_CATEGORIES.LOGISTICS,
      label: TEMPLATE_CATEGORY_LABELS.logistics,
    },
    {
      value: TEMPLATE_CATEGORIES.ECOMMERCE,
      label: TEMPLATE_CATEGORY_LABELS.ecommerce,
    },
    {
      value: TEMPLATE_CATEGORIES.HR_LEGAL,
      label: TEMPLATE_CATEGORY_LABELS.hr_legal,
    },
  ];

  const filteredTemplates = libraryTemplates || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            Template Library
          </h1>
          <p className="text-muted-foreground">
            Browse and import ready-made templates to get started quickly
          </p>
        </div>
        <Button variant="outline" onClick={() => router.push(ROUTES.TEMPLATES)}>
          <Library className="mr-2 h-4 w-4" />
          My Templates
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Browse Templates</CardTitle>
          <CardDescription>
            Select a category or search to find templates
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search templates..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>

          {/* Category Tabs */}
          <Tabs
            value={selectedCategory || "all"}
            onValueChange={(value) =>
              setSelectedCategory(value === "all" ? null : value)
            }
          >
            <TabsList className="grid w-full grid-cols-5">
              {categories.map((cat) => (
                <TabsTrigger
                  key={cat.value || "all"}
                  value={cat.value || "all"}
                >
                  {cat.label}
                </TabsTrigger>
              ))}
            </TabsList>

            <TabsContent value={selectedCategory || "all"} className="mt-6">
              {isLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Spinner />
                </div>
              ) : filteredTemplates.length === 0 ? (
                <div className="py-12 text-center text-muted-foreground">
                  <Library className="mx-auto h-12 w-12 mb-4 opacity-50" />
                  <p>No templates found.</p>
                  {search && (
                    <p className="text-sm mt-2">
                      Try adjusting your search terms.
                    </p>
                  )}
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {filteredTemplates.map((template) => (
                    <TemplateLibraryCard
                      key={template.id}
                      template={template}
                      onImport={() => handleImport(template)}
                    />
                  ))}
                </div>
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {/* Import Dialog */}
      {selectedTemplate && (
        <ImportTemplateDialog
          open={importDialogOpen}
          onOpenChange={setImportDialogOpen}
          template={selectedTemplate}
          projects={projects}
          onConfirm={handleImportConfirm}
          isLoading={importMutation.isPending}
        />
      )}
    </div>
  );
}
