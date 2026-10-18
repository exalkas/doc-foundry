"use client";

import { use, useState } from "react";
import { AdminLayout } from "@/components/layout/admin-layout";
import { useDocument } from "@/hooks/use-document";
import { RetryExtractionModal } from "@/components/admin/retry-extraction-modal";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import Link from "next/link";
import { ArrowLeft, RefreshCw, FileText, AlertCircle } from "lucide-react";
import { formatDate, formatDateTime, getStatusColor } from "@/lib/utils";

interface DocumentDetailPageProps {
  params: Promise<{ id: string }>;
}

export default function DocumentDetailPage({
  params,
}: DocumentDetailPageProps) {
  const { id } = use(params);
  const { data: document, isLoading, error } = useDocument(id);
  const [retryModalOpen, setRetryModalOpen] = useState(false);

  if (isLoading) {
    return (
      <AdminLayout>
        <div className="flex items-center justify-center py-12">
          <Spinner />
        </div>
      </AdminLayout>
    );
  }

  if (error || !document) {
    return (
      <AdminLayout>
        <div className="space-y-6">
          <div className="flex items-center gap-4">
            <Link href="/support/documents">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Documents
              </Button>
            </Link>
          </div>
          <Card>
            <CardContent className="pt-6">
              <p className="text-center text-muted-foreground">
                Document not found or error loading document
              </p>
            </CardContent>
          </Card>
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <Link href="/support/documents">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Documents
            </Button>
          </Link>
          {document.status === "failed" && (
            <Button
              onClick={() => setRetryModalOpen(true)}
              variant="outline"
              size="sm"
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              Retry Extraction
            </Button>
          )}
        </div>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <FileText className="h-5 w-5" />
                  {document.name}
                </CardTitle>
                <CardDescription>
                  Document details and extraction results
                </CardDescription>
              </div>
              <Badge variant={getStatusColor(document.status)}>
                {document.status}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="overview" className="space-y-4">
              <TabsList>
                <TabsTrigger value="overview">Overview</TabsTrigger>
                <TabsTrigger value="extraction">Extraction Results</TabsTrigger>
                {document.error_message && (
                  <TabsTrigger value="errors">
                    <AlertCircle className="mr-2 h-4 w-4" />
                    Errors
                  </TabsTrigger>
                )}
              </TabsList>

              <TabsContent value="overview" className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">
                      Document Name
                    </p>
                    <p className="mt-1">{document.name}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">
                      Status
                    </p>
                    <Badge
                      variant={getStatusColor(document.status)}
                      className="mt-1"
                    >
                      {document.status}
                    </Badge>
                  </div>
                  {document.workspace_name && (
                    <div>
                      <p className="text-sm font-medium text-muted-foreground">
                        Workspace
                      </p>
                      <p className="mt-1">{document.workspace_name}</p>
                    </div>
                  )}
                  {document.project_name && (
                    <div>
                      <p className="text-sm font-medium text-muted-foreground">
                        Project
                      </p>
                      <p className="mt-1">{document.project_name}</p>
                    </div>
                  )}
                  {document.template_name && (
                    <div>
                      <p className="text-sm font-medium text-muted-foreground">
                        Template
                      </p>
                      <p className="mt-1">{document.template_name}</p>
                    </div>
                  )}
                  {document.file_name && (
                    <div>
                      <p className="text-sm font-medium text-muted-foreground">
                        File Name
                      </p>
                      <p className="mt-1">{document.file_name}</p>
                    </div>
                  )}
                  {document.file_size && (
                    <div>
                      <p className="text-sm font-medium text-muted-foreground">
                        File Size
                      </p>
                      <p className="mt-1">
                        {(document.file_size / 1024).toFixed(2)} KB
                      </p>
                    </div>
                  )}
                  {document.file_type && (
                    <div>
                      <p className="text-sm font-medium text-muted-foreground">
                        File Type
                      </p>
                      <p className="mt-1">{document.file_type}</p>
                    </div>
                  )}
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">
                      Created At
                    </p>
                    <p className="mt-1">
                      {formatDateTime(document.created_at)}
                    </p>
                  </div>
                  {document.completed_at && (
                    <div>
                      <p className="text-sm font-medium text-muted-foreground">
                        Completed At
                      </p>
                      <p className="mt-1">
                        {formatDateTime(document.completed_at)}
                      </p>
                    </div>
                  )}
                </div>
              </TabsContent>

              <TabsContent value="extraction" className="space-y-4">
                {document.extraction_results ? (
                  <Card>
                    <CardHeader>
                      <CardTitle>Extraction Results</CardTitle>
                      <CardDescription>
                        Data extracted from the document
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <pre className="overflow-auto rounded-md bg-muted p-4 text-sm">
                        {JSON.stringify(document.extraction_results, null, 2)}
                      </pre>
                    </CardContent>
                  </Card>
                ) : (
                  <Card>
                    <CardContent className="pt-6">
                      <p className="text-center text-muted-foreground">
                        No extraction results available
                        {document.status === "processing" &&
                          " - Extraction is still in progress"}
                        {document.status === "queued" &&
                          " - Extraction is queued"}
                        {document.status === "failed" && " - Extraction failed"}
                      </p>
                    </CardContent>
                  </Card>
                )}
              </TabsContent>

              {document.error_message && (
                <TabsContent value="errors" className="space-y-4">
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <AlertCircle className="h-5 w-5 text-destructive" />
                        Error Details
                      </CardTitle>
                      <CardDescription>
                        Error that occurred during extraction
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="rounded-md bg-destructive/10 p-4">
                        <p className="text-sm text-destructive">
                          {document.error_message}
                        </p>
                      </div>
                    </CardContent>
                  </Card>
                </TabsContent>
              )}
            </Tabs>
          </CardContent>
        </Card>

        <RetryExtractionModal
          documentId={document.id}
          documentName={document.name}
          open={retryModalOpen}
          onOpenChange={setRetryModalOpen}
        />
      </div>
    </AdminLayout>
  );
}
