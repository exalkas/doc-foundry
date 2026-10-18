"use client";

import React from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { formatDate, getStatusColor } from "@/lib/utils";
import type { ApiKey } from "@/lib/types";
import { LoadingSpinner } from "@/components/ui/loading";

/**
 * Props for ApiKeyTable component
 */
interface ApiKeyTableProps {
  /** Array of API keys to display */
  apiKeys: ApiKey[];
  /** Whether data is currently loading */
  isLoading?: boolean;
  /** Callback when revoke button is clicked. Receives the API key ID. */
  onRevoke?: (apiKeyId: string) => void;
}

export const ApiKeyTable = React.memo(function ApiKeyTable({
  apiKeys,
  isLoading = false,
  onRevoke,
}: ApiKeyTableProps) {
  if (isLoading) {
    return <LoadingSpinner message="Loading API keys..." />;
  }

  if (apiKeys.length === 0) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-sm text-muted-foreground">No API keys found</p>
      </div>
    );
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Workspace</TableHead>
            <TableHead>Name</TableHead>
            <TableHead>Prefix</TableHead>
            <TableHead>Scopes</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Last Used</TableHead>
            {onRevoke && <TableHead className="text-right">Actions</TableHead>}
          </TableRow>
        </TableHeader>
        <TableBody>
          {apiKeys.map((apiKey) => (
            <TableRow key={apiKey.id}>
              <TableCell className="font-medium">
                {apiKey.workspace_name || "-"}
              </TableCell>
              <TableCell>{apiKey.name}</TableCell>
              <TableCell className="text-muted-foreground font-mono text-sm">
                {apiKey.prefix}...
              </TableCell>
              <TableCell className="text-muted-foreground">
                {apiKey.scopes.length > 0 ? apiKey.scopes.join(", ") : "-"}
              </TableCell>
              <TableCell>
                <Badge variant={getStatusColor(apiKey.status)}>
                  {apiKey.status}
                </Badge>
              </TableCell>
              <TableCell className="text-muted-foreground">
                {apiKey.last_used ? formatDate(apiKey.last_used) : "Never"}
              </TableCell>
              {onRevoke && (
                <TableCell className="text-right">
                  {apiKey.status === "active" && (
                    <button
                      onClick={() => onRevoke(apiKey.id)}
                      className="text-sm text-destructive hover:underline"
                      aria-label={`Revoke API key ${apiKey.name}`}
                    >
                      Revoke
                    </button>
                  )}
                </TableCell>
              )}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
});
