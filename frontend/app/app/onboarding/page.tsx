"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
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
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { CheckCircle2, Circle } from "lucide-react";
import { post, uploadFile } from "@/lib/api-client";
import { ROUTES } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { useToast } from "@/hooks/use-toast";
import { getSuccessMessage, getErrorMessage } from "@/lib/notifications";

const steps = [
  { id: "welcome", label: "Welcome" },
  { id: "project", label: "Create project" },
  { id: "upload", label: "Upload sample" },
  { id: "template", label: "Define template" },
  { id: "review", label: "Review extraction" },
];

export default function OnboardingPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [currentStep, setCurrentStep] = useState(0);
  const [projectData, setProjectData] = useState({ name: "", description: "" });
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [uploadedDocumentId, setUploadedDocumentId] = useState<string | null>(
    null
  );
  const [templateData, setTemplateData] = useState({
    name: "",
    document_type: "",
    field_schema: {},
  });

  const createProjectMutation = useMutation({
    mutationFn: (data: { name: string; description?: string }) =>
      post<{ project: { id: string } }>("/api/projects", data),
    onSuccess: (data) => {
      toast({
        variant: "success",
        title: getSuccessMessage("create", "project"),
        description: "Project created successfully",
      });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setCurrentStep(1);
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Error",
        description: getErrorMessage(error, "create", "project"),
      });
    },
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) =>
      uploadFile<{ document: { id: string } }>("/api/documents", file, {
        project_id: createProjectMutation.data?.project.id,
      }),
    onSuccess: (data) => {
      toast({
        variant: "success",
        title: getSuccessMessage("upload", "document"),
        description: "Document uploaded successfully",
      });
      setUploadedDocumentId(data.document.id);
      setCurrentStep(2);
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Error",
        description: getErrorMessage(error, "upload", "document"),
      });
    },
  });

  const createTemplateMutation = useMutation({
    mutationFn: (data: any) =>
      post<{ template: { id: string } }>("/api/templates", {
        ...data,
        project_id: createProjectMutation.data?.project.id,
        field_schema: templateData.field_schema,
      }),
    onSuccess: () => {
      toast({
        variant: "success",
        title: getSuccessMessage("create", "template"),
        description: "Template created successfully",
      });
      setCurrentStep(4);
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Error",
        description: getErrorMessage(error, "create", "template"),
      });
    },
  });

  const completeOnboardingMutation = useMutation({
    mutationFn: () =>
      post<{ success: boolean; message: string }>(
        "/api/workspaces/complete-onboarding",
        {}
      ),
    onSuccess: () => {
      toast({
        variant: "success",
        title: getSuccessMessage("complete", "onboarding"),
        description: "Onboarding completed successfully",
      });
      queryClient.invalidateQueries({ queryKey: ["onboarding-status"] });
      router.push(ROUTES.DASHBOARD);
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Error",
        description: getErrorMessage(error, "complete", "onboarding"),
      });
    },
  });

  const handleProjectSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createProjectMutation.mutate(projectData);
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setUploadedFile(file);
      uploadMutation.mutate(file);
    }
  };

  const handleTemplateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createTemplateMutation.mutate(templateData);
  };

  const handleComplete = () => {
    completeOnboardingMutation.mutate();
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <Breadcrumb>
        <BreadcrumbList>
          {steps.map((step, index) => (
            <div key={step.id} className="flex items-center">
              <BreadcrumbItem>
                {index < currentStep ? (
                  <BreadcrumbPage className="flex items-center">
                    <CheckCircle2 className="mr-2 h-4 w-4 text-accent" />
                    {step.label}
                  </BreadcrumbPage>
                ) : index === currentStep ? (
                  <BreadcrumbPage className="flex items-center font-medium">
                    <Circle className="mr-2 h-4 w-4" />
                    {step.label}
                  </BreadcrumbPage>
                ) : (
                  <span className="flex items-center text-muted-foreground">
                    <Circle className="mr-2 h-4 w-4" />
                    {step.label}
                  </span>
                )}
              </BreadcrumbItem>
              {index < steps.length - 1 && <BreadcrumbSeparator />}
            </div>
          ))}
        </BreadcrumbList>
      </Breadcrumb>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Welcome to DocFoundry.app</CardTitle>
          <CardDescription>
            Let's get you started with your first document extraction
          </CardDescription>
        </CardHeader>
        <CardContent>
          {currentStep === 0 && (
            <div className="space-y-4">
              <p className="text-muted-foreground">
                We'll guide you through creating your first project, uploading a
                document, and setting up an extraction template.
              </p>
              <Button onClick={() => setCurrentStep(1)}>Get started</Button>
            </div>
          )}

          {currentStep === 1 && (
            <form onSubmit={handleProjectSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="project-name">Project name</Label>
                <Input
                  id="project-name"
                  value={projectData.name}
                  onChange={(e) =>
                    setProjectData({ ...projectData, name: e.target.value })
                  }
                  placeholder="e.g. Invoices Q4"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="project-description">
                  Description (optional)
                </Label>
                <Textarea
                  id="project-description"
                  value={projectData.description}
                  onChange={(e) =>
                    setProjectData({
                      ...projectData,
                      description: e.target.value,
                    })
                  }
                  placeholder="Optional description"
                />
              </div>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setCurrentStep(0)}
                >
                  Back
                </Button>
                <Button
                  type="submit"
                  disabled={
                    !projectData.name || createProjectMutation.isPending
                  }
                >
                  Create project
                </Button>
              </div>
            </form>
          )}

          {currentStep === 2 && (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="file-upload">Upload a sample document</Label>
                <Input
                  id="file-upload"
                  type="file"
                  accept=".pdf,image/*"
                  onChange={handleFileUpload}
                  disabled={uploadMutation.isPending}
                />
                {uploadedFile && (
                  <p className="text-sm text-muted-foreground">
                    Uploaded: {uploadedFile.name}
                  </p>
                )}
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setCurrentStep(1)}>
                  Back
                </Button>
                {uploadedDocumentId && (
                  <Button onClick={() => setCurrentStep(3)}>Continue</Button>
                )}
              </div>
            </div>
          )}

          {currentStep === 3 && (
            <form onSubmit={handleTemplateSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="template-name">Template name</Label>
                <Input
                  id="template-name"
                  value={templateData.name}
                  onChange={(e) =>
                    setTemplateData({ ...templateData, name: e.target.value })
                  }
                  placeholder="e.g. Invoice Template"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="document-type">Document type</Label>
                <Input
                  id="document-type"
                  value={templateData.document_type}
                  onChange={(e) =>
                    setTemplateData({
                      ...templateData,
                      document_type: e.target.value,
                    })
                  }
                  placeholder="e.g. Invoice, Receipt"
                />
              </div>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setCurrentStep(2)}
                >
                  Back
                </Button>
                <Button
                  type="submit"
                  disabled={
                    !templateData.name || createTemplateMutation.isPending
                  }
                >
                  Create template
                </Button>
              </div>
            </form>
          )}

          {currentStep === 4 && (
            <div className="space-y-4">
              <p className="text-muted-foreground">
                Great! Your template has been created. You can now view your
                extraction results and start processing more documents.
              </p>
              <Button
                onClick={handleComplete}
                disabled={completeOnboardingMutation.isPending}
              >
                {completeOnboardingMutation.isPending
                  ? "Completing..."
                  : "Go to dashboard"}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
