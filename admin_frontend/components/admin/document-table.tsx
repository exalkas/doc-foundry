"use client";

import React from "react";
import Link from "next/link";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDate, getStatusColor } from "@/lib/utils";
import type { Document } from "@/lib/types";
import { ExternalLink } from "lucide-react";
import { LoadingSpinner } from "@/components/ui/loading";

interface DocumentTableProps {
  documents: Document[];
  isLoading?: boolean;
}

export const DocumentTable = React.memo(function DocumentTable({
  documents,
  isLoading = false,
}: DocumentTableProps) {
  if (isLoading) {
    return <LoadingSpinner message="Loading documents..." />;
  }

  if (documents.length === 0) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-sm text-muted-foreground">No documents found</p>
      </div>
    );
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Workspace</TableHead>
            <TableHead>Project</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Created</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {documents.map((document) => (
            <TableRow key={document.id}>
              <TableCell className="font-medium">{document.name}</TableCell>
              <TableCell className="text-muted-foreground">
                {document.workspace_name || "-"}
              </TableCell>
              <TableCell className="text-muted-foreground">
                {document.project_name || "-"}
              </TableCell>
              <TableCell>
                <Badge variant={getStatusColor(document.status)}>
                  {document.status}
                </Badge>
              </TableCell>
              <TableCell className="text-muted-foreground">
                {formatDate(document.created_at)}
              </TableCell>
              <TableCell className="text-right">
                <Link href={`/support/documents/${document.id}`}>
                  <Button variant="ghost" size="sm">
                    View
                    <ExternalLink className="ml-2 h-4 w-4" />
                  </Button>
                </Link>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
});
