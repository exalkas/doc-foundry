"use client";

import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import {
  UploadCloud,
  X,
  FileText,
  Loader2,
  AlertCircle,
  CheckCircle2,
  ExternalLink,
  Library,
} from "lucide-react";
import { uploadFile, get } from "@/lib/api-client";
import type { Project, Template, Document } from "@/lib/types";
import { ROUTES } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { useToast } from "@/hooks/use-toast";
import { getSuccessMessage, getErrorMessage } from "@/lib/notifications";
import { HelpIcon } from "@/components/app/help-icon";
import { HelpText } from "@/components/app/help-text";
import { getHelpText, getHelpTextLong } from "@/lib/help-content";
import { getFilePageCount } from "@/lib/pdf-utils";

interface UsageSummary {
  current_period: {
    documents_processed: number;
    pages_processed: number;
  };
  plan_limits: {
    documents_per_month: number;
    pages_per_month: number;
    max_file_size_mb: number;
    max_pages_per_document: number;
  };
  current_plan: string;
}

interface FileWithMetadata extends File {
  pageCount?: number;
  pageCountError?: string;
  isValid?: boolean;
  validationError?: string;
}

export default function UploadPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const projectIdParam = searchParams.get("projectId");

  const [selectedProjectId, setSelectedProjectId] = useState<string>(
    projectIdParam || "__none__"
  );
  const [selectedTemplateId, setSelectedTemplateId] =
    useState<string>("__none__");
  const [files, setFiles] = useState<FileWithMetadata[]>([]);
  const [priority, setPriority] = useState(false);
  const [ocrLanguage, setOcrLanguage] = useState<string>("eng");
  const [uploading, setUploading] = useState(false);
  const [uploadedDocuments, setUploadedDocuments] = useState<
    Array<{ id: string; fileName: string }>
  >([]);
  const [loadingPageCounts, setLoadingPageCounts] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const dropZoneRef = useRef<HTMLDivElement>(null);

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

  const { data: templatesData } = useQuery<{
    templates: Template[];
    pagination: {
      page: number;
      page_size: number;
      total: number;
      total_pages: number;
    };
  }>({
    queryKey: ["templates", selectedProjectId],
    queryFn: () =>
      get(
        `/api/templates${
          selectedProjectId && selectedProjectId !== "__none__"
            ? `?project_id=${selectedProjectId}`
            : ""
        }`
      ),
    enabled: selectedProjectId !== "__none__",
  });

  const templates = templatesData?.templates || [];

  // Poll for uploaded documents status
  const uploadedDocumentIds = uploadedDocuments.map((d) => d.id);
  const { data: documentsData } = useQuery<Document[]>({
    queryKey: ["documents", "uploaded", uploadedDocumentIds],
    queryFn: async () => {
      if (uploadedDocumentIds.length === 0) return [];
      const pollStartTime = Date.now();
      console.log(
        `[UPLOAD_PAGE] Polling ${uploadedDocumentIds.length} documents:`,
        uploadedDocumentIds
      );

      const results = await Promise.allSettled(
        uploadedDocumentIds.map(async (id) => {
          const docStartTime = Date.now();
          try {
            // Use lightweight status endpoint for polling
            const response = await get<Document>(`/api/documents/${id}/status`);
            const docTime = Date.now() - docStartTime;
            console.log(
              `[UPLOAD_PAGE] Document ${id} status fetched in ${docTime}ms, status: ${response.status}`
            );
            return response;
          } catch (error: any) {
            const docTime = Date.now() - docStartTime;
            // If timeout or error, return the last known status or null
            // The query will retry on next poll
            console.warn(
              `[UPLOAD_PAGE] Failed to fetch document ${id} after ${docTime}ms:`,
              error
            );
            return null;
          }
        })
      );

      const pollTime = Date.now() - pollStartTime;
      const successful = results.filter(
        (r) => r.status === "fulfilled" && r.value !== null
      ).length;
      console.log(
        `[UPLOAD_PAGE] Poll completed in ${pollTime}ms: ${successful}/${uploadedDocumentIds.length} successful`
      );
      // Filter out failed requests and return successful ones
      return results
        .map((result) => (result.status === "fulfilled" ? result.value : null))
        .filter((doc): doc is Document => doc !== null);
    },
    enabled: uploadedDocumentIds.length > 0,
    retry: 1, // Only retry once on failure
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data || data.length === 0) return false;
      // Poll if any document is still processing, pending, or queued
      const hasProcessing = data.some(
        (doc) => doc.status === "processing" || doc.status === "pending"
      );
      return hasProcessing ? 3000 : false;
    },
  });

  const { data: usage } = useQuery<UsageSummary>({
    queryKey: ["usage"],
    queryFn: () => get("/api/usage/summary"),
  });

  // Check if current plan supports priority queue (Pro and Enterprise only)
  const currentPlan = usage?.current_plan?.toLowerCase() || "free";
  const supportsPriority =
    currentPlan === "pro" || currentPlan === "enterprise";

  // Reset priority if plan doesn't support it
  useEffect(() => {
    if (!supportsPriority && priority) {
      setPriority(false);
    }
  }, [supportsPriority, priority]);

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      return uploadFile<Document>("/api/documents", file, {
        project_id:
          selectedProjectId !== "__none__" ? selectedProjectId : undefined,
        template_id:
          selectedTemplateId !== "__none__" ? selectedTemplateId : undefined,
        priority: priority,
        ocr_language: ocrLanguage,
      });
    },
    onSuccess: (data, file) => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      // Track uploaded document
      setUploadedDocuments((prev) => [
        ...prev,
        { id: data.id, fileName: file.name },
      ]);
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Error",
        description: getErrorMessage(error, "upload", "document"),
      });
    },
  });

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    setLoadingPageCounts(true);

    try {
      const filesWithMetadata: FileWithMetadata[] = await Promise.all(
        selectedFiles.map(async (file) => {
          const fileWithMeta = file as FileWithMetadata;

          // Get page count
          try {
            fileWithMeta.pageCount = await getFilePageCount(file);
            fileWithMeta.pageCountError = undefined;
          } catch (error) {
            console.error(`Error counting pages for ${file.name}:`, error);
            fileWithMeta.pageCount = 1; // Default fallback
            fileWithMeta.pageCountError = "Could not determine page count";
          }

          // Validate file size and pages against plan limits
          if (usage) {
            const fileSizeMB = file.size / (1024 * 1024);
            const maxFileSize = usage.plan_limits.max_file_size_mb || 25;
            const maxPages = usage.plan_limits.max_pages_per_document || 50;

            if (fileSizeMB > maxFileSize) {
              fileWithMeta.isValid = false;
              fileWithMeta.validationError = `File size (${fileSizeMB.toFixed(
                2
              )} MB) exceeds plan limit of ${maxFileSize} MB`;
            } else if (
              fileWithMeta.pageCount &&
              fileWithMeta.pageCount > maxPages
            ) {
              fileWithMeta.isValid = false;
              fileWithMeta.validationError = `Page count (${fileWithMeta.pageCount}) exceeds plan limit of ${maxPages} pages`;
            } else {
              fileWithMeta.isValid = true;
              fileWithMeta.validationError = undefined;
            }
          } else {
            fileWithMeta.isValid = true;
          }

          return fileWithMeta;
        })
      );

      setFiles((prev) => [...prev, ...filesWithMetadata]);
    } catch (error) {
      console.error("Error processing files:", error);
      toast({
        variant: "destructive",
        title: "Error",
        description: "Failed to process selected files",
      });
    } finally {
      setLoadingPageCounts(false);
    }
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    // Only set dragging to false if we're leaving the drop zone itself
    if (!dropZoneRef.current?.contains(e.relatedTarget as Node)) {
      setIsDragging(false);
    }
  };

  const handleDrop = async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const droppedFiles = Array.from(e.dataTransfer.files);
    if (droppedFiles.length === 0) return;

    // Filter to only PDFs and images
    const validFiles = droppedFiles.filter(
      (file) =>
        file.type === "application/pdf" || file.type.startsWith("image/")
    );

    if (validFiles.length === 0) {
      toast({
        variant: "destructive",
        title: "Invalid file type",
        description: "Please drop PDF or image files only",
      });
      return;
    }

    // Process files similar to handleFileSelect
    setLoadingPageCounts(true);
    try {
      const filesWithMetadata: FileWithMetadata[] = await Promise.all(
        validFiles.map(async (file) => {
          const fileWithMeta = file as FileWithMetadata;

          // Get page count
          try {
            fileWithMeta.pageCount = await getFilePageCount(file);
            fileWithMeta.pageCountError = undefined;
          } catch (error) {
            console.error(`Error counting pages for ${file.name}:`, error);
            fileWithMeta.pageCount = 1; // Default fallback
            fileWithMeta.pageCountError = "Could not determine page count";
          }

          // Validate file size and pages against plan limits
          if (usage) {
            const fileSizeMB = file.size / (1024 * 1024);
            const maxFileSize = usage.plan_limits.max_file_size_mb || 25;
            const maxPages = usage.plan_limits.max_pages_per_document || 50;

            if (fileSizeMB > maxFileSize) {
              fileWithMeta.isValid = false;
              fileWithMeta.validationError = `File size (${fileSizeMB.toFixed(
                2
              )} MB) exceeds plan limit of ${maxFileSize} MB`;
            } else if (
              fileWithMeta.pageCount &&
              fileWithMeta.pageCount > maxPages
            ) {
              fileWithMeta.isValid = false;
              fileWithMeta.validationError = `Page count (${fileWithMeta.pageCount}) exceeds plan limit of ${maxPages} pages`;
            } else {
              fileWithMeta.isValid = true;
              fileWithMeta.validationError = undefined;
            }
          } else {
            fileWithMeta.isValid = true;
          }

          return fileWithMeta;
        })
      );

      setFiles((prev) => [...prev, ...filesWithMetadata]);
    } catch (error) {
      console.error("Error processing dropped files:", error);
      toast({
        variant: "destructive",
        title: "Error",
        description: "Failed to process dropped files",
      });
    } finally {
      setLoadingPageCounts(false);
    }
  };

  const handleUpload = async () => {
    if (files.length === 0) return;

    // Check for invalid files
    const invalidFiles = files.filter((f) => f.isValid === false);
    if (invalidFiles.length > 0) {
      toast({
        variant: "destructive",
        title: "Validation Error",
        description: `Please fix validation errors for ${invalidFiles.length} file(s) before uploading`,
      });
      return;
    }

    setUploading(true);
    setUploadedDocuments([]); // Reset uploaded documents
    setShowUploadModal(true); // Open modal
    try {
      for (const file of files) {
        await uploadMutation.mutateAsync(file);
      }
      toast({
        variant: "success",
        title: getSuccessMessage("upload", "document"),
        description: `${files.length} file${
          files.length > 1 ? "s" : ""
        } uploaded successfully`,
      });
      // Clear files after successful upload
      setFiles([]);
      // Don't redirect - stay on page to show OCR results
    } catch (error) {
      console.error("Upload failed:", error);
    } finally {
      setUploading(false);
      // Don't close modal automatically - let user see results and close manually
    }
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Upload documents</h1>
        <p className="text-muted-foreground">
          Upload PDFs, images, or scans up to 25 MB each.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Upload form</CardTitle>
          <CardDescription>
            Select files and configure processing options
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Label htmlFor="project">Project</Label>
              <HelpIcon content={getHelpText("upload.project")} />
            </div>
            <Select
              value={selectedProjectId}
              onValueChange={setSelectedProjectId}
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

          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Label htmlFor="ocr-language">OCR Language</Label>
              <HelpIcon content="Select the language of the document for better OCR accuracy. Greek (ell) is recommended for Greek documents." />
            </div>
            <Select value={ocrLanguage} onValueChange={setOcrLanguage}>
              <SelectTrigger id="ocr-language">
                <SelectValue placeholder="Select language" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="eng">English</SelectItem>
                <SelectItem value="ell">Greek</SelectItem>
                <SelectItem value="fra">French</SelectItem>
                <SelectItem value="deu">German</SelectItem>
                <SelectItem value="spa">Spanish</SelectItem>
                <SelectItem value="ita">Italian</SelectItem>
                <SelectItem value="por">Portuguese</SelectItem>
                <SelectItem value="rus">Russian</SelectItem>
                <SelectItem value="chi_sim">Chinese (Simplified)</SelectItem>
                <SelectItem value="chi_tra">Chinese (Traditional)</SelectItem>
                <SelectItem value="jpn">Japanese</SelectItem>
                <SelectItem value="kor">Korean</SelectItem>
                <SelectItem value="ara">Arabic</SelectItem>
                <SelectItem value="heb">Hebrew</SelectItem>
                <SelectItem value="tur">Turkish</SelectItem>
                <SelectItem value="pol">Polish</SelectItem>
                <SelectItem value="nld">Dutch</SelectItem>
                <SelectItem value="swe">Swedish</SelectItem>
                <SelectItem value="nor">Norwegian</SelectItem>
                <SelectItem value="dan">Danish</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Label htmlFor="template">Extraction template</Label>
              <HelpIcon content={getHelpText("upload.template")} />
            </div>
            <div className="space-y-2">
              <Select
                value={selectedTemplateId}
                onValueChange={setSelectedTemplateId}
                disabled={selectedProjectId === "__none__"}
              >
                <SelectTrigger id="template">
                  <SelectValue placeholder="Optional — choose template to auto-run" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">No template</SelectItem>
                  {templates?.map((template) => (
                    <SelectItem key={template.id} value={template.id}>
                      {template.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selectedProjectId === "__none__" && (
                <p className="text-xs text-muted-foreground">
                  Select a project first to see available templates
                </p>
              )}
              <div className="flex items-center gap-2">
                <Link
                  href={ROUTES.TEMPLATE_LIBRARY}
                  className="text-xs text-primary hover:underline flex items-center gap-1"
                >
                  <Library className="h-3 w-3" />
                  Browse Template Library
                </Link>
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Label htmlFor="files">Files</Label>
              <HelpIcon content={getHelpText("upload.file-limits")} />
            </div>
            <div
              ref={dropZoneRef}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              className={cn(
                "border-2 border-dashed rounded-lg p-8 text-center",
                "hover:border-primary/50 transition-colors",
                isDragging && "border-primary bg-primary/5"
              )}
            >
              <input
                id="files"
                type="file"
                multiple
                accept=".pdf,image/*"
                onChange={handleFileSelect}
                className="hidden"
              />
              <label htmlFor="files" className="cursor-pointer">
                <UploadCloud className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
                <p className="text-sm font-medium mb-1">
                  Click to upload or drag and drop
                </p>
                <p className="text-xs text-muted-foreground">
                  PDF, PNG, JPG up to 25 MB
                </p>
              </label>
            </div>
            <HelpText
              title="File requirements and limits"
              content={getHelpTextLong("upload.file-limits")}
            />
            {files.length > 0 && (
              <div className="mt-4 space-y-2">
                {files.map((file, index) => (
                  <div
                    key={index}
                    className={cn(
                      "p-3 border rounded-md",
                      file.isValid === false &&
                        "border-destructive bg-destructive/5"
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium truncate">
                            {file.name}
                          </span>
                          {file.isValid === false && (
                            <AlertCircle className="h-4 w-4 text-destructive flex-shrink-0" />
                          )}
                        </div>
                        <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                          <span>{(file.size / 1024 / 1024).toFixed(2)} MB</span>
                          {file.pageCount !== undefined && (
                            <span>
                              {file.pageCount} page
                              {file.pageCount !== 1 ? "s" : ""}
                            </span>
                          )}
                          {file.pageCountError && (
                            <span className="text-yellow-600">
                              {file.pageCountError}
                            </span>
                          )}
                        </div>
                        {file.validationError && (
                          <div className="mt-1 text-xs text-destructive">
                            {file.validationError}
                          </div>
                        )}
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeFile(index)}
                        className="ml-2 flex-shrink-0"
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {usage && (
              <div className="mt-2 p-3 bg-muted/50 rounded-md text-xs">
                <div className="font-medium mb-1">
                  Plan Limits ({usage.current_plan})
                </div>
                <div className="space-y-1 text-muted-foreground">
                  <div>
                    Max file size: {usage.plan_limits.max_file_size_mb || 25} MB
                  </div>
                  <div>
                    Max pages per document:{" "}
                    {usage.plan_limits.max_pages_per_document || 50}
                  </div>
                  <div>
                    Pages processed this month:{" "}
                    {usage.current_period.pages_processed} /{" "}
                    {usage.plan_limits.pages_per_month || "unlimited"}
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="flex items-center space-x-2">
            <Switch
              id="priority"
              checked={priority}
              onCheckedChange={setPriority}
              disabled={!supportsPriority}
            />
            <div className="flex items-center gap-2">
              <Label
                htmlFor="priority"
                className={cn(
                  "cursor-pointer",
                  !supportsPriority && "cursor-not-allowed opacity-50"
                )}
              >
                High priority
              </Label>
              <HelpIcon content={getHelpText("upload.priority")} />
            </div>
            <p className="text-xs text-muted-foreground">
              {supportsPriority
                ? "Send to the front of the processing queue where possible."
                : "Available on Pro and Enterprise plans only."}
            </p>
          </div>

          <div className="flex gap-2">
            <Button variant="outline" onClick={() => router.back()}>
              Cancel
            </Button>
            <Button
              onClick={handleUpload}
              disabled={
                files.length === 0 ||
                loadingPageCounts ||
                files.some((f) => f.isValid === false)
              }
              isLoading={uploading}
            >
              {loadingPageCounts ? "Processing files..." : "Upload and process"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Upload Progress Modal */}
      <Dialog open={showUploadModal} onOpenChange={setShowUploadModal}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Upload Progress</DialogTitle>
            <DialogDescription>
              {documentsData && documentsData.length > 0
                ? `Processing ${documentsData.length} document${
                    documentsData.length > 1 ? "s" : ""
                  }`
                : uploading
                ? "Uploading files..."
                : "Upload complete"}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 mt-4">
            {uploadedDocuments.length === 0 && uploading && (
              <div className="text-center py-8 text-muted-foreground">
                <Loader2 className="h-8 w-8 animate-spin mx-auto mb-2" />
                <p>Uploading files...</p>
              </div>
            )}

            {documentsData && documentsData.length > 0 && (
              <>
                {documentsData.map((document) => {
                  const isProcessing =
                    document.status === "processing" ||
                    document.status === "pending";
                  const isCompleted =
                    document.status === "completed" ||
                    document.status === "scanned" ||
                    document.status === "failed";

                  return (
                    <Card key={document.id}>
                      <CardHeader>
                        <div className="flex items-center justify-between">
                          <div>
                            <CardTitle className="flex items-center gap-2 text-base">
                              <FileText className="h-4 w-4" />
                              {document.file_name}
                            </CardTitle>
                            <CardDescription>
                              Status: {document.status}
                            </CardDescription>
                          </div>
                          {isProcessing && (
                            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                          )}
                          {isCompleted && (
                            <CheckCircle2 className="h-5 w-5 text-green-600" />
                          )}
                        </div>
                      </CardHeader>
                      <CardContent>
                        {isProcessing && (
                          <div className="text-center py-4 text-muted-foreground">
                            <Loader2 className="h-6 w-6 animate-spin mx-auto mb-2" />
                            <p className="text-sm">Processing document...</p>
                          </div>
                        )}

                        {isCompleted && (
                          <div className="text-center py-4 space-y-3">
                            <div className="flex flex-col items-center gap-2">
                              <CheckCircle2 className="h-8 w-8 text-green-600" />
                              <div>
                                <p className="font-medium">
                                  {document.status === "completed"
                                    ? "Processing complete"
                                    : document.status === "scanned"
                                    ? "Scanning complete"
                                    : "Processing failed"}
                                </p>
                                <p className="text-xs text-muted-foreground mt-1">
                                  {document.status === "completed"
                                    ? "Extraction completed successfully"
                                    : document.status === "scanned"
                                    ? "Document scanned. Apply a template to extract data."
                                    : document.status === "failed"
                                    ? "Processing completed with errors"
                                    : ""}
                                </p>
                              </div>
                            </div>
                            {document.status === "failed" &&
                              document.last_error && (
                                <div className="mt-2 rounded-md bg-destructive/10 p-2 text-xs text-destructive text-left">
                                  <strong>Error:</strong> {document.last_error}
                                </div>
                              )}
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  );
                })}

                {/* Show completion summary and actions when all are done */}
                {documentsData.every(
                  (doc) =>
                    doc.status === "completed" ||
                    doc.status === "scanned" ||
                    doc.status === "failed"
                ) && (
                  <div className="pt-4 border-t space-y-3">
                    <div className="flex flex-col sm:flex-row gap-2">
                      <Button
                        onClick={() => {
                          setShowUploadModal(false);
                          router.push(ROUTES.DOCUMENTS);
                        }}
                        className="flex-1"
                      >
                        View All Documents
                      </Button>
                      {documentsData.some(
                        (d) =>
                          d.status === "completed" || d.status === "scanned"
                      ) && (
                        <Button
                          variant="outline"
                          onClick={() => {
                            const completedDoc = documentsData.find(
                              (d) =>
                                d.status === "completed" ||
                                d.status === "scanned"
                            );
                            if (completedDoc) {
                              setShowUploadModal(false);
                              router.push(
                                `${ROUTES.DOCUMENTS}/${completedDoc.id}`
                              );
                            }
                          }}
                          className="flex-1"
                        >
                          View First Document
                          <ExternalLink className="ml-2 h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
