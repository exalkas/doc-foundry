"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Download, FileText } from "lucide-react";
import type { LibraryTemplate } from "@/lib/types";
import { TEMPLATE_CATEGORY_LABELS } from "@/lib/constants";

interface TemplateLibraryCardProps {
  template: LibraryTemplate;
  onImport: () => void;
}

export function TemplateLibraryCard({
  template,
  onImport,
}: TemplateLibraryCardProps) {
  const fieldCount = template.field_schema?.fields?.length || 0;
  const categoryLabel =
    TEMPLATE_CATEGORY_LABELS[template.category] || template.category;

  return (
    <Card className="flex flex-col hover:shadow-md transition-shadow">
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <CardTitle className="text-lg">{template.name}</CardTitle>
            <CardDescription className="mt-1 line-clamp-2">
              {template.description || "No description available"}
            </CardDescription>
          </div>
        </div>
        <div className="flex items-center gap-2 mt-3">
          <Badge variant="secondary">{categoryLabel}</Badge>
          {template.document_type && (
            <Badge variant="outline">{template.document_type}</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="flex-1 flex flex-col justify-between">
        <div className="space-y-2 mb-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <FileText className="h-4 w-4" />
            <span>
              {fieldCount} field{fieldCount !== 1 ? "s" : ""}
            </span>
          </div>
          {template.tags && template.tags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {template.tags.slice(0, 3).map((tag, idx) => (
                <Badge key={idx} variant="outline" className="text-xs">
                  {tag}
                </Badge>
              ))}
              {template.tags.length > 3 && (
                <Badge variant="outline" className="text-xs">
                  +{template.tags.length - 3}
                </Badge>
              )}
            </div>
          )}
        </div>
        <Button onClick={onImport} className="w-full" size="sm">
          <Download className="mr-2 h-4 w-4" />
          Import Template
        </Button>
      </CardContent>
    </Card>
  );
}
