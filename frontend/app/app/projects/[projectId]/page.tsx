"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Spinner } from "@/components/ui/spinner";
import { UploadCloud, FileCode2, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { get } from "@/lib/api-client";
import type { Project, Document, Template } from "@/lib/types";
import { ROUTES } from "@/lib/constants";

export default function ProjectDetailPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = useMemo(
    () => params?.projectId as string,
    [params?.projectId]
  );

  const { data: project, isLoading: projectLoading } = useQuery<Project>({
    queryKey: ["project", projectId],
    queryFn: () => get(`/api/projects/${projectId}`),
    enabled: !!projectId,
  });

  const { data: documents, isLoading: documentsLoading } = useQuery<Document[]>(
    {
      queryKey: ["documents", projectId],
      queryFn: () => get(`/api/documents?project_id=${projectId}`),
      enabled: !!projectId,
    }
  );

  const { data: templates, isLoading: templatesLoading } = useQuery<Template[]>(
    {
      queryKey: ["templates", projectId],
      queryFn: () => get(`/api/templates?project_id=${projectId}`),
      enabled: !!projectId,
    }
  );

  const documentsRoute = ROUTES.DOCUMENTS || "/app/documents";

  if (projectLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Spinner />
      </div>
    );
  }

  if (!project) {
    return <div>Project not found</div>;
  }

  return (
    <div className="space-y-6">
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link href={ROUTES.PROJECTS}>Projects</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>{project.name}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <div>
        <h1 className="text-3xl font-bold tracking-tight">{project.name}</h1>
        {project.description && (
          <p className="text-muted-foreground mt-2">{project.description}</p>
        )}
      </div>

      <Tabs defaultValue="documents" className="space-y-4">
        <TabsList>
          <TabsTrigger value="documents">Documents</TabsTrigger>
          <TabsTrigger value="templates">Templates</TabsTrigger>
        </TabsList>

        <TabsContent value="documents" className="space-y-4">
          <div className="flex items-center justify-between">
            <CardDescription>Documents in this project</CardDescription>
            <Button asChild>
              <Link href={`${ROUTES.UPLOAD}?projectId=${projectId}`}>
                <UploadCloud className="mr-2 h-4 w-4" />
                Upload documents
              </Link>
            </Button>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Documents</CardTitle>
            </CardHeader>
            <CardContent>
              {documentsLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Spinner />
                </div>
              ) : documents && documents.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>File name</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Template</TableHead>
                      <TableHead>Uploaded by</TableHead>
                      <TableHead>Uploaded at</TableHead>
                      <TableHead>Pages</TableHead>
                      <TableHead></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {documents.map((doc) => (
                      <TableRow key={doc.id}>
                        <TableCell>
                          <Link
                            href={`${documentsRoute}/${doc.id}`}
                            className="font-medium hover:underline"
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
                          -
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          -
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {new Date(doc.created_at).toLocaleDateString()}
                        </TableCell>
                        <TableCell>{doc.pages || "-"}</TableCell>
                        <TableCell>
                          {doc.status === "failed" && (
                            <Button variant="ghost" size="sm">
                              <RotateCcw className="h-4 w-4" />
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No documents in this project yet
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="templates" className="space-y-4">
          <div className="flex items-center justify-between">
            <CardDescription>Templates in this project</CardDescription>
            <Button asChild>
              <Link href={`${ROUTES.TEMPLATES}?projectId=${projectId}`}>
                <FileCode2 className="mr-2 h-4 w-4" />
                New template
              </Link>
            </Button>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Templates</CardTitle>
            </CardHeader>
            <CardContent>
              {templatesLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Spinner />
                </div>
              ) : templates && templates.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Document type</TableHead>
                      <TableHead>Last run</TableHead>
                      <TableHead>Success rate</TableHead>
                      <TableHead></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {templates.map((template) => (
                      <TableRow key={template.id}>
                        <TableCell>
                          <Link
                            href={`/app/templates/${template.id}/edit`}
                            className="font-medium hover:underline"
                          >
                            {template.name}
                          </Link>
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {template.document_type || "-"}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {template.last_run_at
                            ? new Date(
                                template.last_run_at
                              ).toLocaleDateString()
                            : "-"}
                        </TableCell>
                        <TableCell>
                          {template.success_count + template.failure_count > 0
                            ? `${Math.round(
                                (template.success_count /
                                  (template.success_count +
                                    template.failure_count)) *
                                  100
                              )}%`
                            : "-"}
                        </TableCell>
                        <TableCell></TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No templates in this project yet
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
