"use client";

import * as React from "react";
import { useState } from "react";
import { useWorkspaceContext } from "@/contexts/workspace-context";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { getSuccessMessage, getErrorMessage } from "@/lib/notifications";
import { Building2 } from "lucide-react";

interface CreateWorkspaceDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CreateWorkspaceDialog({
  open,
  onOpenChange,
}: CreateWorkspaceDialogProps) {
  const { createWorkspace } = useWorkspaceContext();
  const { toast } = useToast();
  const [name, setName] = useState("");
  const [primaryColor, setPrimaryColor] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!name.trim()) {
      toast({
        variant: "destructive",
        title: "Validation Error",
        description: "Workspace name is required",
      });
      return;
    }

    setIsSubmitting(true);
    try {
      await createWorkspace(name.trim(), primaryColor || undefined);
      toast({
        variant: "default",
        title: getSuccessMessage("create", "workspace"),
      });
      setName("");
      setPrimaryColor("");
      onOpenChange(false);
    } catch (error: any) {
      toast({
        variant: "destructive",
        title: getErrorMessage(error, "create", "workspace"),
        description: error?.message || "Failed to create workspace",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Building2 className="h-5 w-5" />
            Create New Workspace
          </DialogTitle>
          <DialogDescription>
            Create a new workspace to organize your projects and templates. Each
            workspace is separate and can be used for different clients or
            projects.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="name">Workspace Name</Label>
              <Input
                id="name"
                placeholder="e.g. Acme Corp"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={isSubmitting}
                required
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="primary_color">Primary Color (Optional)</Label>
              <Input
                id="primary_color"
                type="color"
                value={primaryColor || "#2563EB"}
                onChange={(e) => setPrimaryColor(e.target.value)}
                disabled={isSubmitting}
                className="h-10 w-full cursor-pointer"
              />
              <p className="text-sm text-muted-foreground">
                Choose a color to customize your workspace theme
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Creating..." : "Create Workspace"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
