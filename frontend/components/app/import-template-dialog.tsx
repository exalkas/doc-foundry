"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
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
import { Spinner } from "@/components/ui/spinner";
import type { LibraryTemplate, Project } from "@/lib/types";

interface ImportTemplateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  template: LibraryTemplate;
  projects: Project[];
  onConfirm: (name?: string, projectId?: string) => void;
  isLoading?: boolean;
}

export function ImportTemplateDialog({
  open,
  onOpenChange,
  template,
  projects,
  onConfirm,
  isLoading = false,
}: ImportTemplateDialogProps) {
  const [name, setName] = useState(template.name);
  const [projectId, setProjectId] = useState<string>("__none__");

  const handleConfirm = () => {
    onConfirm(
      name !== template.name ? name : undefined,
      projectId !== "__none__" ? projectId : undefined
    );
  };

  const handleOpenChange = (newOpen: boolean) => {
    if (!isLoading) {
      onOpenChange(newOpen);
      if (!newOpen) {
        // Reset form when closing
        setName(template.name);
        setProjectId("__none__");
      }
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Import Template</DialogTitle>
          <DialogDescription>
            Import "{template.name}" into your workspace. You can customize the
            name and assign it to a project.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="template-name">Template Name</Label>
            <Input
              id="template-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Enter template name"
              disabled={isLoading}
            />
            <p className="text-xs text-muted-foreground">
              Leave unchanged to use the original name
            </p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="project">Project (Optional)</Label>
            <Select
              value={projectId}
              onValueChange={setProjectId}
              disabled={isLoading}
            >
              <SelectTrigger id="project">
                <SelectValue placeholder="Select a project" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">No Project</SelectItem>
                {projects.map((project) => (
                  <SelectItem key={project.id} value={project.id}>
                    {project.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Assign this template to a project for better organization
            </p>
          </div>
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => handleOpenChange(false)}
            disabled={isLoading}
          >
            Cancel
          </Button>
          <Button onClick={handleConfirm} disabled={isLoading}>
            {isLoading ? (
              <>
                <Spinner className="mr-2 h-4 w-4" />
                Importing...
              </>
            ) : (
              "Import Template"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
