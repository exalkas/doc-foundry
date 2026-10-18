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
import type { Workspace } from "@/lib/types";
import { ArrowUpDown, ExternalLink } from "lucide-react";
import { LoadingSpinner } from "@/components/ui/loading";

/**
 * Props for WorkspaceTable component
 */
interface WorkspaceTableProps {
  /** Array of workspaces to display */
  workspaces: Workspace[];
  /** Whether data is currently loading */
  isLoading?: boolean;
}

export const WorkspaceTable = React.memo(function WorkspaceTable({
  workspaces,
  isLoading = false,
}: WorkspaceTableProps) {
  if (isLoading) {
    return <LoadingSpinner message="Loading workspaces..." />;
  }

  if (workspaces.length === 0) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-sm text-muted-foreground">No workspaces found</p>
      </div>
    );
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Owner</TableHead>
            <TableHead>Plan</TableHead>
            <TableHead>
              <div className="flex items-center gap-2">
                Status
                <ArrowUpDown className="h-4 w-4" />
              </div>
            </TableHead>
            <TableHead>
              <div className="flex items-center gap-2">
                Created
                <ArrowUpDown className="h-4 w-4" />
              </div>
            </TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {workspaces.map((workspace) => (
            <TableRow key={workspace.id}>
              <TableCell className="font-medium">{workspace.name}</TableCell>
              <TableCell className="text-muted-foreground">
                {workspace.owner_email || "-"}
              </TableCell>
              <TableCell>{workspace.plan || "-"}</TableCell>
              <TableCell>
                <Badge variant={getStatusColor(workspace.status)}>
                  {workspace.status}
                </Badge>
              </TableCell>
              <TableCell className="text-muted-foreground">
                {formatDate(workspace.created_at)}
              </TableCell>
              <TableCell className="text-right">
                <Link href={`/workspaces/${workspace.id}`}>
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
