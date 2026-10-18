"use client";

import { useState, useEffect, useMemo } from "react";
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
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Spinner } from "@/components/ui/spinner";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
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
  Save,
  PlayCircle,
  Trash2,
  Plus,
  ExternalLink,
  Library,
  X,
} from "lucide-react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { get, put, post, del, ApiClientError } from "@/lib/api-client";
import type {
  Template,
  Document,
  PaginatedDocumentsResponse,
  Project,
  LibraryTemplate,
} from "@/lib/types";
import { ROUTES } from "@/lib/constants";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import { getSuccessMessage, getErrorMessage } from "@/lib/notifications";
import { VisualTemplateEditor } from "@/components/app/visual-template-editor";

interface FieldDefinition {
  id?: string;
  field_name: string;
  json_key: string;
  data_type: "string" | "number" | "date" | "boolean";
  required: boolean;
  default_value?: string;
  validation_rules?: string;
  strategy?: "regex" | "anchor" | "ml" | "name";
  anchor_texts?: string[]; // For multilingual anchor support
  anchor?: string; // Single anchor (backward compatibility)
  pattern?: string; // For regex strategy
  selection_coordinates?: [number, number, number, number];
  selection_page?: number;
  selection_method?: "visual" | "manual";
}

export default function TemplateEditorPage({
  params,
}: {
  params: { templateId: string };
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const templateId = params?.templateId;
  const isNew = templateId === "new";

  // Debug logging (remove in production)
  useEffect(() => {
    if (templateId && !isNew) {
      console.log("Loading template with ID:", templateId);
    }
  }, [templateId, isNew]);

  const [formData, setFormData] = useState({
    name: "",
    description: "",
    document_type: "",
    default_export_format: "json" as "json" | "csv" | "excel",
    test_document_id: "",
    project_id: "__none__",
  });

  const [fields, setFields] = useState<FieldDefinition[]>([]);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [openAccordion, setOpenAccordion] = useState<string | undefined>(
    undefined
  );
  const [previewJson, setPreviewJson] = useState<Record<string, any> | null>(
    null
  );
  const [editorMode, setEditorMode] = useState<"form" | "visual">("form");

  const {
    data: template,
    isLoading,
    error,
  } = useQuery<Template>({
    queryKey: ["template", templateId],
    queryFn: async () => {
      try {
        const response = await get<Template>(`/api/templates/${templateId}`);
        console.log("Template loaded:", response);
        return response;
      } catch (err) {
        console.error("Error loading template:", err);
        throw err;
      }
    },
    enabled: !isNew && !!templateId,
  });

  // Fetch library template if this template was imported from library
  const { data: libraryTemplate } = useQuery<LibraryTemplate | null>({
    queryKey: ["library-template", template?.library_template_id],
    queryFn: async () => {
      if (!template?.library_template_id) return null;
      try {
        return await get<LibraryTemplate>(
          `/api/template-library/${template.library_template_id}`
        );
      } catch {
        return null;
      }
    },
    enabled: !isNew && !!template?.library_template_id,
  });

  // Update form data when template loads
  useEffect(() => {
    if (template) {
      setFormData({
        name: template.name,
        description: template.description || "",
        document_type: template.document_type || "",
        default_export_format: (template.default_export_format?.toLowerCase() ||
          "json") as "json" | "csv" | "excel",
        test_document_id: "",
        project_id: template.project_id || "__none__",
      });
      if (template.field_schema && typeof template.field_schema === "object") {
        let fieldArray: FieldDefinition[] = [];

        // Handle AI-generated format: { fields: [...] }
        if (Array.isArray(template.field_schema.fields)) {
          fieldArray = template.field_schema.fields.map(
            (field: any, index: number) => ({
              id: `field-${index}`,
              field_name:
                field.name || field.field_name || field.json_key || "",
              json_key: field.json_key || field.key || "",
              data_type: (field.data_type ||
                field.type ||
                "string") as FieldDefinition["data_type"],
              required: field.required || false,
              default_value: field.default_value || field.default || "",
              validation_rules:
                field.validation_rules ||
                (field.validation ? JSON.stringify(field.validation) : "") ||
                "",
              strategy: field.strategy || "anchor", // Default to anchor for better multilingual support
              anchor_texts:
                field.anchor_texts || (field.anchor ? [field.anchor] : []),
              anchor: field.anchor, // Keep for backward compatibility
              pattern: field.pattern,
              selection_coordinates: field.selection_coordinates,
              selection_page: field.selection_page,
              selection_method: field.selection_method || "manual",
            })
          );
        }
        // Handle manual format: { "json_key": { label, type, ... } }
        else if (!template.field_schema.fields) {
          fieldArray = Object.entries(template.field_schema).map(
            ([json_key, config]: [string, any], index: number) => ({
              id: `field-${index}`,
              field_name: config.label || json_key,
              json_key,
              data_type: (config.type ||
                "string") as FieldDefinition["data_type"],
              required: config.required || false,
              default_value: config.default || "",
              validation_rules: config.validation || "",
              selection_coordinates: config.selection_coordinates,
              selection_page: config.selection_page,
              selection_method: config.selection_method || "manual",
            })
          );
        }

        setFields(fieldArray);
      }
    }
  }, [template]);

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

  // Fetch templates count and usage summary to check limit for new templates
  const { data: templatesData } = useQuery<{
    templates: Template[];
    pagination: {
      total: number;
    };
  }>({
    queryKey: ["templates", "count"],
    queryFn: () => get("/api/templates?page=1&page_size=1"),
    enabled: isNew,
  });

  const { data: usageSummary } = useQuery<{
    plan_limits: {
      max_templates: number | null;
    };
  }>({
    queryKey: ["usage-summary"],
    queryFn: () => get("/api/usage/summary"),
    enabled: isNew,
  });

  // Check template limit when creating a new template - redirect immediately if limit reached
  useEffect(() => {
    if (isNew) {
      // Wait for data to load
      if (templatesData && usageSummary) {
        const currentTemplateCount = templatesData.pagination?.total || 0;
        const maxTemplates = usageSummary.plan_limits?.max_templates;

        // Check if limit exists and is reached
        if (
          maxTemplates !== null &&
          maxTemplates !== undefined &&
          currentTemplateCount >= maxTemplates
        ) {
          // Show error and redirect immediately
          toast({
            variant: "destructive",
            title: "Template limit reached",
            description: `You have reached the limit of ${maxTemplates} templates. Please delete an existing template or upgrade your plan to create more templates.`,
          });
          // Redirect back to templates list immediately
          router.replace(ROUTES.TEMPLATES);
        }
      }
    }
  }, [isNew, templatesData, usageSummary, router, toast]);

  const { data: testDocuments } = useQuery<PaginatedDocumentsResponse>({
    queryKey: ["documents", "all"],
    queryFn: async () => {
      // Fetch all documents by paginating through all pages
      // Don't filter by status - include all documents so user can test with any document
      const allDocuments: any[] = [];
      let page = 1;
      let hasMore = true;
      const pageSize = 100; // Maximum allowed page size

      while (hasMore) {
        const response = await get<PaginatedDocumentsResponse>(
          `/api/documents?page=${page}&page_size=${pageSize}&sort=created_at&order=desc`
        );

        if (response.documents && response.documents.length > 0) {
          allDocuments.push(...response.documents);
        }

        // Check if there are more pages
        hasMore = page < (response.pagination?.total_pages || 1);
        page++;
      }

      return {
        documents: allDocuments,
        pagination: {
          total: allDocuments.length,
          page: 1,
          page_size: allDocuments.length,
          total_pages: 1,
        },
      };
    },
  });

  const documents = testDocuments?.documents || [];

  const saveMutation = useMutation({
    mutationFn: (data: any) => {
      // Convert fields to backend format: { fields: [...] }
      const fieldSchema = {
        fields: fields.map((field) => {
          const fieldDef: any = {
            name: field.field_name,
            json_key: field.json_key,
            data_type: field.data_type,
            required: field.required,
            strategy: field.strategy || "anchor", // Default to anchor
          };

          // Add optional fields only if they have values
          if (field.default_value) {
            fieldDef.default_value = field.default_value;
          }

          // Add anchor text(s) for anchor strategy
          if (field.strategy === "anchor" || !field.strategy) {
            if (field.anchor_texts && field.anchor_texts.length > 0) {
              fieldDef.anchor_texts = field.anchor_texts.filter(
                (text) => text.trim() !== ""
              );
            } else if (field.anchor && field.anchor.trim() !== "") {
              fieldDef.anchor = field.anchor;
            }
          }

          // Add pattern for regex strategy
          if (field.strategy === "regex" && field.pattern) {
            fieldDef.pattern = field.pattern;
          }

          // Handle validation - convert JSON string to object if needed
          if (field.validation_rules) {
            try {
              // Try to parse as JSON if it's a string
              const validation =
                typeof field.validation_rules === "string"
                  ? JSON.parse(field.validation_rules)
                  : field.validation_rules;

              // Only add if it's a valid object
              if (
                validation &&
                typeof validation === "object" &&
                !Array.isArray(validation)
              ) {
                fieldDef.validation = validation;
              }
            } catch {
              // If parsing fails, skip validation (invalid format)
            }
          }

          // Add visual selection data if present
          if (field.selection_coordinates) {
            fieldDef.selection_coordinates = field.selection_coordinates;
          }
          if (field.selection_page) {
            fieldDef.selection_page = field.selection_page;
          }
          if (field.selection_method) {
            fieldDef.selection_method = field.selection_method;
          }

          return fieldDef;
        }),
      };

      // Ensure default_export_format is lowercase
      // Convert "__none__" to null for project_id
      const payload = {
        ...data,
        default_export_format:
          data.default_export_format?.toLowerCase() || "json",
        field_schema: fieldSchema,
        project_id: data.project_id === "__none__" ? null : data.project_id,
      };

      if (isNew) {
        return post<Template>("/api/templates", payload);
      } else {
        return put<Template>(`/api/templates/${templateId}`, payload);
      }
    },
    onSuccess: (data) => {
      toast({
        variant: "success",
        title: getSuccessMessage(isNew ? "create" : "update", "template"),
        description: isNew
          ? "Template created successfully"
          : "Template updated successfully",
      });
      queryClient.invalidateQueries({ queryKey: ["templates"] });
      queryClient.invalidateQueries({ queryKey: ["template", templateId] });
      // Redirect to templates page after save
      router.push(ROUTES.TEMPLATES);
    },
    onError: (error) => {
      let errorMessage = getErrorMessage(
        error,
        isNew ? "create" : "update",
        "template"
      );

      // Improve error messages for validation errors
      if (error instanceof ApiClientError) {
        // Check for field schema validation errors
        if (
          error.message?.toLowerCase().includes("field schema") ||
          error.message?.toLowerCase().includes("at least one field")
        ) {
          errorMessage =
            "A template must have at least one field defined. Please add at least one field before saving.";
        } else if (
          error.details?.detail?.toLowerCase().includes("field schema") ||
          error.details?.detail?.toLowerCase().includes("at least one field")
        ) {
          errorMessage =
            "A template must have at least one field defined. Please add at least one field before saving.";
        } else if (
          error.details?.detail &&
          typeof error.details.detail === "string"
        ) {
          // Use the detail message if it's more descriptive
          errorMessage = error.details.detail;
        }
      }

      toast({
        variant: "destructive",
        title: "Error",
        description: errorMessage,
      });
    },
  });

  const testMutation = useMutation({
    mutationFn: async () => {
      if (!formData.test_document_id) {
        throw new Error("Please select a test document");
      }
      // Start the test job
      const testResponse = await post<{ job_id: string; document_id: string }>(
        `/api/templates/${templateId}/test`,
        {
          test_document_id: formData.test_document_id,
        }
      );

      // Poll for extraction results using lightweight status endpoint
      const maxAttempts = 30; // 30 attempts
      const pollInterval = 1000; // 1 second
      let attempts = 0;

      console.log(
        `[TEMPLATE_TEST] Starting to poll document ${formData.test_document_id} for extraction results`
      );

      while (attempts < maxAttempts) {
        await new Promise((resolve) => setTimeout(resolve, pollInterval));

        try {
          // Use lightweight status endpoint for polling
          const pollStartTime = Date.now();
          const documentStatus = await get<{
            status: string;
          }>(`/api/documents/${formData.test_document_id}/status`);
          const pollTime = Date.now() - pollStartTime;
          console.log(
            `[TEMPLATE_TEST] Status poll ${
              attempts + 1
            }/${maxAttempts}: status=${documentStatus.status} in ${pollTime}ms`
          );

          // If completed, fetch full document to get extraction result
          if (documentStatus.status === "completed") {
            console.log(
              `[TEMPLATE_TEST] Document completed, fetching full document for extraction results`
            );
            const fullDocStartTime = Date.now();
            const document = await get<{
              status: string;
              extraction_result?: { extracted_json?: any; metadata?: any };
            }>(`/api/documents/${formData.test_document_id}`);
            const fullDocTime = Date.now() - fullDocStartTime;
            console.log(
              `[TEMPLATE_TEST] Full document fetched in ${fullDocTime}ms`
            );

            if (document.extraction_result?.extracted_json) {
              return {
                extracted_json: document.extraction_result.extracted_json,
                metadata: document.extraction_result.metadata,
              };
            }
            // If completed but no extraction result yet, continue polling
            console.log(
              `[TEMPLATE_TEST] Document completed but extraction result not ready yet, continuing to poll`
            );
            continue;
          }

          // If failed, stop polling
          if (documentStatus.status === "failed") {
            throw new Error(
              "Extraction failed. Please check the document status."
            );
          }

          // Still processing, continue polling
          console.log(
            `[TEMPLATE_TEST] Document status: ${documentStatus.status}, continuing to poll`
          );
        } catch (error: any) {
          const errorMsg =
            error instanceof Error ? error.message : String(error);
          // Continue polling on error unless it's a clear failure or timeout
          if (errorMsg.includes("failed") || errorMsg.includes("timeout")) {
            console.error(`[TEMPLATE_TEST] Polling error (stopping):`, error);
            throw error;
          }
          console.warn(`[TEMPLATE_TEST] Polling error (continuing):`, error);
        }

        attempts++;
      }

      throw new Error(
        "Extraction timed out. Please check the document status manually."
      );
    },
    onSuccess: (data: any) => {
      const fieldCount = Object.keys(data.extracted_json || {}).length;
      toast({
        variant: "success",
        title: getSuccessMessage("test", "template"),
        description:
          fieldCount > 0
            ? `Successfully extracted ${fieldCount} field${
                fieldCount !== 1 ? "s" : ""
              } from the test document.`
            : "Template test completed, but no fields were extracted.",
      });
      setPreviewJson(data.extracted_json || null);
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Error",
        description: getErrorMessage(error, "test", "template"),
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => del(`/api/templates/${templateId}`),
    onSuccess: () => {
      toast({
        variant: "success",
        title: getSuccessMessage("delete", "template"),
        description: "Template deleted successfully",
      });
      queryClient.invalidateQueries({ queryKey: ["templates"] });
      router.push(ROUTES.TEMPLATES);
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Error",
        description: getErrorMessage(error, "delete", "template"),
      });
    },
  });

  const addField = () => {
    const newIndex = fields.length;
    setFields([
      ...fields,
      {
        id: `field-${Date.now()}`,
        field_name: "",
        json_key: "",
        data_type: "string",
        required: false,
        strategy: "anchor",
        anchor_texts: [],
        selection_method: "manual",
      },
    ]);
    // Open the accordion for the newly added field
    setOpenAccordion(`field-${newIndex}`);
  };

  const updateField = (index: number, updates: Partial<FieldDefinition>) => {
    const newFields = [...fields];
    newFields[index] = { ...newFields[index], ...updates };
    setFields(newFields);
  };

  const removeField = (index: number) => {
    setFields(fields.filter((_, i) => i !== index));
    // Close accordion if the removed field was open, or adjust if a later field was open
    if (openAccordion === `field-${index}`) {
      setOpenAccordion(undefined);
    } else if (openAccordion) {
      const openIndex = parseInt(openAccordion.replace("field-", ""));
      if (openIndex > index) {
        // Adjust the open accordion index since fields shifted
        setOpenAccordion(`field-${openIndex - 1}`);
      }
    }
  };

  const handleSave = () => {
    // Client-side validation: check if template has at least one field
    if (fields.length === 0) {
      toast({
        variant: "destructive",
        title: "Cannot save template",
        description:
          "Please add at least one field to the template. A template must have at least one field defined to extract data from documents.",
      });
      return;
    }

    // Validate that all fields have required information
    const invalidFields = fields.filter(
      (field) => !field.field_name || !field.json_key
    );
    if (invalidFields.length > 0) {
      toast({
        variant: "destructive",
        title: "Cannot save template",
        description:
          "Please complete all fields. Each field must have both a field label and a JSON key.",
      });
      return;
    }

    saveMutation.mutate(formData);
  };

  const handleDelete = () => {
    deleteMutation.mutate();
  };

  // Check if limit is reached for new templates - show loading while checking
  const isCheckingLimit = isNew && (!templatesData || !usageSummary);
  const isLimitReached = useMemo(() => {
    if (!isNew || !templatesData || !usageSummary) return false;
    const currentTemplateCount = templatesData.pagination?.total || 0;
    const maxTemplates = usageSummary.plan_limits?.max_templates;
    return (
      maxTemplates !== null &&
      maxTemplates !== undefined &&
      currentTemplateCount >= maxTemplates
    );
  }, [isNew, templatesData, usageSummary]);

  if (!isNew && isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Spinner />
      </div>
    );
  }

  if (!isNew && error) {
    return (
      <div className="space-y-4">
        <div className="text-destructive">
          Error loading template:{" "}
          {error instanceof Error ? error.message : "Unknown error"}
        </div>
        <Button onClick={() => router.push(ROUTES.TEMPLATES)}>
          Back to Templates
        </Button>
      </div>
    );
  }

  // Show loading while checking limit for new templates
  if (isCheckingLimit) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Spinner />
      </div>
    );
  }

  // If limit is reached, don't render the form (redirect will happen via useEffect)
  if (isLimitReached) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link href={ROUTES.TEMPLATES}>Templates</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>Editor</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <h1 className="text-3xl font-bold tracking-tight">
              {isNew ? "Create template" : "Edit template"}
            </h1>
            {libraryTemplate && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Library className="h-4 w-4" />
                <span>Imported from:</span>
                <Link
                  href={ROUTES.TEMPLATE_LIBRARY}
                  className="text-primary hover:underline"
                >
                  {libraryTemplate.name}
                </Link>
              </div>
            )}
          </div>
        </div>
        <div className="flex gap-2">
          {!isNew && (
            <>
              <Button
                variant="outline"
                onClick={() => testMutation.mutate()}
                disabled={testMutation.isPending || !formData.test_document_id}
              >
                <PlayCircle className="mr-2 h-4 w-4" />
                {testMutation.isPending ? "Testing..." : "Run test"}
              </Button>
              <Button variant="destructive" onClick={() => setDeleteOpen(true)}>
                <Trash2 className="h-4 w-4" />
              </Button>
            </>
          )}
          <Button onClick={handleSave} disabled={saveMutation.isPending}>
            <Save className="mr-2 h-4 w-4" />
            Save template
          </Button>
        </div>
      </div>

      {/* Template Settings */}
      <Card>
        <CardHeader>
          <CardTitle>Template settings</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-4 px-2">
          <div className="space-y-2">
            <Label htmlFor="template-name">Name</Label>
            <Input
              id="template-name"
              value={formData.name}
              onChange={(e) =>
                setFormData({ ...formData, name: e.target.value })
              }
              placeholder="e.g. Invoice Template"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="project">Project</Label>
            <Select
              value={formData.project_id}
              onValueChange={(value) =>
                setFormData({ ...formData, project_id: value })
              }
            >
              <SelectTrigger id="project">
                <SelectValue placeholder="Select project (optional)" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">No project</SelectItem>
                {projects?.map((project) => (
                  <SelectItem key={project.id} value={project.id}>
                    {project.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2 md:col-span-2">
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
          <div className="space-y-2">
            <Label htmlFor="document-type">Document type</Label>
            <Input
              id="document-type"
              value={formData.document_type}
              onChange={(e) =>
                setFormData({ ...formData, document_type: e.target.value })
              }
              placeholder="e.g. Invoice, Packing slip"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="export-format">Default export</Label>
            <Select
              value={formData.default_export_format}
              onValueChange={(value: "json" | "csv" | "excel") =>
                setFormData({ ...formData, default_export_format: value })
              }
            >
              <SelectTrigger id="export-format">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="json">JSON</SelectItem>
                <SelectItem value="csv">CSV</SelectItem>
                <SelectItem value="excel">Excel</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {!isNew && (
            <div className="space-y-2">
              <Label htmlFor="test-document">Test document</Label>
              <Select
                value={formData.test_document_id}
                onValueChange={(value) =>
                  setFormData({ ...formData, test_document_id: value })
                }
              >
                <SelectTrigger id="test-document">
                  <SelectValue placeholder="Choose uploaded sample" />
                </SelectTrigger>
                <SelectContent>
                  {documents.length === 0 ? (
                    <div className="py-6 text-center text-sm text-muted-foreground">
                      No documents available
                    </div>
                  ) : (
                    documents.map((doc) => {
                      const date = new Date(doc.created_at);
                      const formattedDate = date.toLocaleDateString("en-US", {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      });
                      const formattedTime = date.toLocaleTimeString("en-US", {
                        hour: "numeric",
                        minute: "2-digit",
                        hour12: true,
                      });
                      return (
                        <SelectItem key={doc.id} value={doc.id}>
                          <div className="flex flex-col">
                            <span className="font-medium">{doc.file_name}</span>
                            <span className="text-xs text-muted-foreground">
                              {formattedDate} at {formattedTime}
                            </span>
                          </div>
                        </SelectItem>
                      );
                    })
                  )}
                </SelectContent>
              </Select>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Field Editor - Tabs for Form and Visual */}
      <Card className="col-span-full">
        <CardHeader>
          <CardTitle>Fields</CardTitle>
          <CardDescription>
            Define fields using form editor or visual selection
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs
            value={editorMode}
            onValueChange={(v) => setEditorMode(v as "form" | "visual")}
          >
            <TabsList className="mb-4">
              <TabsTrigger value="form">Form Editor</TabsTrigger>
              <TabsTrigger value="visual">Visual Editor</TabsTrigger>
            </TabsList>
            <TabsContent value="form" className="mt-4">
              <div className="space-y-4">
                <div className="flex justify-end">
                  <Button variant="outline" size="sm" onClick={addField}>
                    <Plus className="mr-2 h-4 w-4" />
                    Add field
                  </Button>
                </div>
                <Accordion
                  type="single"
                  collapsible
                  className="w-full"
                  value={openAccordion}
                  onValueChange={setOpenAccordion}
                >
                  {fields.length > 0 ? (
                    fields.map((field, index) => (
                      <AccordionItem key={index} value={`field-${index}`}>
                        <AccordionTrigger>
                          {field.field_name ||
                            field.json_key ||
                            `Field ${index + 1}`}
                          {field.json_key && ` (${field.json_key})`}
                        </AccordionTrigger>
                        <AccordionContent>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 px-2">
                            <div className="space-y-2">
                              <Label>Field label</Label>
                              <Input
                                value={field.field_name}
                                onChange={(e) =>
                                  updateField(index, {
                                    field_name: e.target.value,
                                  })
                                }
                                placeholder="e.g. Invoice Number"
                              />
                            </div>
                            <div className="space-y-2">
                              <Label>JSON key</Label>
                              <Input
                                value={field.json_key}
                                onChange={(e) =>
                                  updateField(index, {
                                    json_key: e.target.value,
                                  })
                                }
                                placeholder="e.g. invoice_number"
                              />
                            </div>
                            <div className="space-y-2">
                              <Label>Data type</Label>
                              <Select
                                value={field.data_type}
                                onValueChange={(
                                  value: FieldDefinition["data_type"]
                                ) => updateField(index, { data_type: value })}
                              >
                                <SelectTrigger>
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="string">String</SelectItem>
                                  <SelectItem value="number">Number</SelectItem>
                                  <SelectItem value="date">Date</SelectItem>
                                  <SelectItem value="boolean">
                                    Boolean
                                  </SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                            <div className="space-y-2">
                              <Label>Extraction strategy</Label>
                              <Select
                                value={field.strategy || "anchor"}
                                onValueChange={(
                                  value: "regex" | "anchor" | "ml" | "name"
                                ) =>
                                  updateField(index, {
                                    strategy: value,
                                    // Clear anchor_texts if switching away from anchor
                                    anchor_texts:
                                      value === "anchor"
                                        ? field.anchor_texts || []
                                        : undefined,
                                    pattern:
                                      value === "regex"
                                        ? field.pattern
                                        : undefined,
                                  })
                                }
                              >
                                <SelectTrigger>
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="anchor">
                                    Anchor (recommended for multilingual)
                                  </SelectItem>
                                  <SelectItem value="regex">
                                    Regex Pattern
                                  </SelectItem>
                                  <SelectItem value="name">
                                    Name-based
                                  </SelectItem>
                                  <SelectItem value="ml">
                                    Machine Learning
                                  </SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                            {(field.strategy === "anchor" ||
                              !field.strategy) && (
                              <div className="space-y-2 md:col-span-2">
                                <Label>
                                  Anchor text(s) - exact text from document
                                </Label>
                                <div className="space-y-2">
                                  {(field.anchor_texts || []).map(
                                    (anchor, anchorIndex) => (
                                      <div
                                        key={anchorIndex}
                                        className="flex gap-2"
                                      >
                                        <Input
                                          value={anchor}
                                          onChange={(e) => {
                                            const newAnchors = [
                                              ...(field.anchor_texts || []),
                                            ];
                                            newAnchors[anchorIndex] =
                                              e.target.value;
                                            updateField(index, {
                                              anchor_texts: newAnchors,
                                            });
                                          }}
                                          placeholder="e.g. ΑΡΙΘΜΟΣ ΚΥΚΛΟΦΟΡΙΑΣ or Registration Number"
                                        />
                                        <Button
                                          type="button"
                                          variant="outline"
                                          size="sm"
                                          onClick={() => {
                                            const newAnchors = (
                                              field.anchor_texts || []
                                            ).filter(
                                              (_, i) => i !== anchorIndex
                                            );
                                            updateField(index, {
                                              anchor_texts: newAnchors,
                                            });
                                          }}
                                        >
                                          <X className="h-4 w-4" />
                                        </Button>
                                      </div>
                                    )
                                  )}
                                  <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={() => {
                                      updateField(index, {
                                        anchor_texts: [
                                          ...(field.anchor_texts || []),
                                          "",
                                        ],
                                      });
                                    }}
                                  >
                                    <Plus className="mr-2 h-4 w-4" />
                                    Add anchor text
                                  </Button>
                                </div>
                                <p className="text-xs text-muted-foreground">
                                  Enter the exact label text that appears in the
                                  document before the value. For multilingual
                                  documents, add anchors in all languages (e.g.,
                                  Greek and English).
                                </p>
                              </div>
                            )}
                            {field.strategy === "regex" && (
                              <div className="space-y-2 md:col-span-2">
                                <Label>Regex pattern</Label>
                                <Input
                                  value={field.pattern || ""}
                                  onChange={(e) =>
                                    updateField(index, {
                                      pattern: e.target.value,
                                    })
                                  }
                                  placeholder="e.g. \\d{4} for 4 digits"
                                />
                                <p className="text-xs text-muted-foreground">
                                  Enter a regex pattern to match the value in
                                  the document.
                                </p>
                              </div>
                            )}
                            <div className="flex items-center space-x-2">
                              <Checkbox
                                id={`required-${index}`}
                                checked={field.required}
                                onCheckedChange={(checked) =>
                                  updateField(index, {
                                    required: checked === true,
                                  })
                                }
                              />
                              <Label
                                htmlFor={`required-${index}`}
                                className="cursor-pointer"
                              >
                                Required
                              </Label>
                            </div>
                            <div className="space-y-2">
                              <Label>Default value</Label>
                              <Input
                                value={field.default_value || ""}
                                onChange={(e) =>
                                  updateField(index, {
                                    default_value: e.target.value,
                                  })
                                }
                                placeholder="Optional"
                              />
                            </div>
                            <div className="space-y-2">
                              <Label>Validation (optional)</Label>
                              <Textarea
                                value={field.validation_rules || ""}
                                onChange={(e) =>
                                  updateField(index, {
                                    validation_rules: e.target.value,
                                  })
                                }
                                placeholder="e.g. regex, min/max"
                              />
                            </div>
                            <Button
                              variant="destructive"
                              size="sm"
                              onClick={() => removeField(index)}
                              className="md:col-span-2"
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              Delete field
                            </Button>
                          </div>
                        </AccordionContent>
                      </AccordionItem>
                    ))
                  ) : (
                    <div className="text-center py-8">
                      <p className="text-sm text-muted-foreground mb-4">
                        No fields defined yet. Add fields to map document data
                        to JSON keys.
                      </p>
                      <Button variant="outline" onClick={addField}>
                        <Plus className="mr-2 h-4 w-4" />
                        Add first field
                      </Button>
                    </div>
                  )}
                </Accordion>
              </div>
            </TabsContent>
            <TabsContent value="visual" className="mt-4">
              <div className="h-[600px]">
                <VisualTemplateEditor
                  templateId={templateId}
                  fields={fields.map((f, idx) => ({
                    ...f,
                    id: f.id || `field-${idx}`,
                  }))}
                  onFieldsChange={(newFields) => {
                    setFields(newFields);
                  }}
                />
              </div>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {/* Preview */}
      {previewJson !== null && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Test Results</CardTitle>
                <CardDescription>
                  {Object.keys(previewJson || {}).length === 0
                    ? "No fields were extracted. The template may not match the document structure."
                    : `Successfully extracted ${
                        Object.keys(previewJson || {}).length
                      } field${
                        Object.keys(previewJson || {}).length !== 1 ? "s" : ""
                      }`}
                </CardDescription>
              </div>
              {formData.test_document_id && (
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      window.open(
                        `/app/documents/${formData.test_document_id}`,
                        "_blank"
                      );
                    }}
                  >
                    View Document
                    <ExternalLink className="ml-2 h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setPreviewJson(null);
                      testMutation.reset();
                    }}
                  >
                    Test Again
                  </Button>
                </div>
              )}
            </div>
            {Object.keys(previewJson || {}).length === 0 && (
              <CardDescription className="text-destructive mt-2">
                No fields were extracted. The template may not match the
                document structure.
              </CardDescription>
            )}
          </CardHeader>
          <CardContent>
            {Object.keys(previewJson || {}).length > 0 ? (
              <Tabs defaultValue="json" className="w-full">
                <TabsList>
                  <TabsTrigger value="json">JSON</TabsTrigger>
                  <TabsTrigger value="table">Table</TabsTrigger>
                </TabsList>
                <TabsContent value="json" className="mt-4">
                  <ScrollArea className="h-[300px] w-full rounded-md border p-4">
                    <pre className="text-xs">
                      {JSON.stringify(previewJson, null, 2)}
                    </pre>
                  </ScrollArea>
                </TabsContent>
                <TabsContent value="table" className="mt-4">
                  <div className="space-y-2">
                    {Object.entries(previewJson).map(([key, value]) => (
                      <div
                        key={key}
                        className="flex justify-between border-b pb-2"
                      >
                        <span className="font-medium">{key}</span>
                        <span className="text-muted-foreground">
                          {typeof value === "object"
                            ? JSON.stringify(value)
                            : String(value)}
                        </span>
                      </div>
                    ))}
                  </div>
                </TabsContent>
              </Tabs>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                <p>
                  No data extracted. Check if the template fields match the
                  document structure.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Delete Confirmation */}
      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete template?</AlertDialogTitle>
            <AlertDialogDescription>
              Existing extraction results stay, but this template cannot be
              reused. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
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
