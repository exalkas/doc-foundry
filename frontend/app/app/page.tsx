"use client";

import { useEffect, useState, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  UploadCloud,
  FileCode,
  KeyRound,
  Activity,
  HelpCircle,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ROUTES } from "@/lib/constants";
import { get } from "@/lib/api-client";
import type {
  Project,
  Document,
  UsageRecord,
  PaginatedDocumentsResponse,
} from "@/lib/types";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useToast } from "@/hooks/use-toast";

interface UsageSummary {
  current_period: {
    documents_processed: number;
    pages_processed: number;
  };
  plan_limits: {
    documents_per_month: number;
    pages_per_month: number;
  };
  current_plan: string;
}

interface OnboardingStatus {
  completed: boolean;
}

export default function DashboardPage() {
  const router = useRouter();
  const { toast } = useToast();
  const previousStatusesRef = useRef<Map<string, string>>(new Map());

  const { data: usage } = useQuery<UsageSummary>({
    queryKey: ["usage"],
    queryFn: () => get("/api/usage/summary"),
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

  const { data: onboardingStatus } = useQuery<OnboardingStatus>({
    queryKey: ["onboarding-status"],
    queryFn: () => get("/api/workspaces/onboarding-status"),
  });

  const { data: recentDocumentsResponse } =
    useQuery<PaginatedDocumentsResponse>({
      queryKey: ["documents", "recent"],
      queryFn: () =>
        get("/api/documents?page=1&page_size=5&sort=created_at&order=desc"),
      refetchInterval: (query) => {
        const data = query.state.data;
        if (!data || !data.documents || data.documents.length === 0)
          return false;
        // Poll if any document is still processing or pending
        const hasProcessing = data.documents.some(
          (doc) => doc.status === "processing" || doc.status === "pending"
        );
        // Only poll every 5 seconds if there are processing documents
        return hasProcessing ? 5000 : false;
      },
    });

  const recentDocuments = recentDocumentsResponse?.documents;

  const showOnboardingPrompt =
    !onboardingStatus?.completed && (!projects || projects.length === 0);

  const documentsProcessed = usage?.current_period.documents_processed || 0;
  const pagesProcessed = usage?.current_period.pages_processed || 0;
  const documentsLimit = usage?.plan_limits.documents_per_month || 1000;
  const pagesLimit = usage?.plan_limits.pages_per_month || 1000;
  const usagePercent = Math.min(
    100,
    (documentsProcessed / documentsLimit) * 100
  );

  // Track status changes and show notifications
  useEffect(() => {
    if (!recentDocuments) return;

    recentDocuments.forEach((doc) => {
      const previousStatus = previousStatusesRef.current.get(doc.id);
      const currentStatus = doc.status;

      // Only notify on transitions from processing/pending to final states
      if (
        previousStatus &&
        (previousStatus === "processing" || previousStatus === "pending") &&
        currentStatus !== previousStatus
      ) {
        if (currentStatus === "completed") {
          toast({
            variant: "success",
            title: "Extraction completed",
            description: `${doc.file_name} has been processed successfully`,
          });
        } else if (currentStatus === "failed") {
          toast({
            variant: "destructive",
            title: "Extraction failed",
            description: `${doc.file_name} failed to process${
              doc.last_error ? `: ${doc.last_error.substring(0, 100)}` : ""
            }`,
          });
        }
      }

      // Update stored status
      previousStatusesRef.current.set(doc.id, currentStatus);
    });
  }, [recentDocuments, toast]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">
          Overview of your company activity and usage
        </p>
      </div>

      {/* Onboarding Prompt */}
      {showOnboardingPrompt && (
        <Alert className="border-primary/50 bg-primary/5">
          <HelpCircle className="h-4 w-4" />
          <AlertTitle>Get started with onboarding</AlertTitle>
          <AlertDescription className="flex items-center justify-between">
            <span>
              Complete the onboarding flow to create your first project, upload
              a document, and set up an extraction template.
            </span>
            <Button
              onClick={() => router.push(ROUTES.ONBOARDING)}
              className="ml-4"
              size="sm"
            >
              Start onboarding
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {/* Usage Summary */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>This period</CardTitle>
              <CardDescription>
                Current plan: {usage?.current_plan || "Basic"}
              </CardDescription>
            </div>
            <Activity className="h-5 w-5 text-muted-foreground" />
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <div className="text-2xl font-bold">{documentsProcessed}</div>
              <p className="text-sm text-muted-foreground">
                Documents processed this month
              </p>
              <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-secondary">
                <div
                  className="h-full bg-primary transition-all"
                  style={{ width: `${usagePercent}%` }}
                />
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                {documentsProcessed} / {documentsLimit} documents
              </p>
            </div>
            <div>
              <div className="text-2xl font-bold">{pagesProcessed}</div>
              <p className="text-sm text-muted-foreground">
                Pages processed this month
              </p>
              <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-secondary">
                <div
                  className="h-full bg-accent transition-all"
                  style={{
                    width: `${Math.min(
                      100,
                      (pagesProcessed / pagesLimit) * 100
                    )}%`,
                  }}
                />
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                {pagesProcessed} / {pagesLimit} pages
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Quick Actions */}
      <div className="flex flex-wrap gap-2">
        <Button asChild>
          <Link href={ROUTES.UPLOAD}>
            <UploadCloud className="mr-2 h-4 w-4" />
            Upload documents
          </Link>
        </Button>
        <Button variant="outline" asChild>
          <Link href={ROUTES.TEMPLATES}>
            <FileCode className="mr-2 h-4 w-4" />
            New template
          </Link>
        </Button>
        <Button variant="ghost" asChild>
          <Link href={ROUTES.API_KEYS}>
            <KeyRound className="mr-2 h-4 w-4" />
            API keys
          </Link>
        </Button>
      </div>

      {/* Recent Projects and Extractions */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Recent Projects */}
        <Card>
          <CardHeader>
            <CardTitle>Recent projects</CardTitle>
            <CardDescription>
              Your most recently updated projects
            </CardDescription>
          </CardHeader>
          <CardContent>
            {projects && projects.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Documents</TableHead>
                    <TableHead>Updated</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {projects.slice(0, 5).map((project) => (
                    <TableRow key={project.id}>
                      <TableCell>
                        <Link
                          href={`${ROUTES.PROJECTS}/${project.id}`}
                          className="font-medium hover:underline"
                        >
                          {project.name}
                        </Link>
                      </TableCell>
                      <TableCell>-</TableCell>
                      <TableCell className="text-muted-foreground">
                        {new Date(project.updated_at).toLocaleDateString()}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <p className="text-sm text-muted-foreground">No projects yet</p>
            )}
          </CardContent>
        </Card>

        {/* Latest Extractions */}
        <Card>
          <CardHeader>
            <CardTitle>Latest extractions</CardTitle>
            <CardDescription>Most recently processed documents</CardDescription>
          </CardHeader>
          <CardContent>
            {recentDocuments && recentDocuments.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Document</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Processed</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {recentDocuments.map((doc) => (
                    <TableRow key={doc.id}>
                      <TableCell className="font-medium">
                        <Link
                          href={`${ROUTES.DOCUMENTS}/${doc.id}`}
                          className="hover:underline"
                        >
                          {doc.file_name}
                        </Link>
                      </TableCell>
                      <TableCell>
                        <span
                          className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${
                            doc.status === "completed"
                              ? "bg-accent/10 text-accent"
                              : doc.status === "failed"
                              ? "bg-destructive/10 text-destructive"
                              : "bg-muted text-muted-foreground"
                          }`}
                        >
                          {doc.status}
                        </span>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {new Date(doc.updated_at).toLocaleString()}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <p className="text-sm text-muted-foreground">
                No documents processed yet
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
