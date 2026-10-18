"use client";

import { useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AuditLog } from "@/hooks/use-audit-logs";

interface AuditLogTableProps {
  logs: AuditLog[];
  isLoading?: boolean;
}

export function AuditLogTable({ logs, isLoading }: AuditLogTableProps) {
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const toggleRow = (logId: string) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(logId)) {
      newExpanded.delete(logId);
    } else {
      newExpanded.add(logId);
    }
    setExpandedRows(newExpanded);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="text-muted-foreground">Loading audit logs...</div>
      </div>
    );
  }

  if (logs.length === 0) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="text-muted-foreground">No audit logs found</div>
      </div>
    );
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-12"></TableHead>
            <TableHead>Timestamp</TableHead>
            <TableHead>Actor</TableHead>
            <TableHead>Action</TableHead>
            <TableHead>Target</TableHead>
            <TableHead>Description</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {logs.map((log) => {
            const isExpanded = expandedRows.has(log.id);
            return (
              <>
                <TableRow key={log.id}>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => toggleRow(log.id)}
                      className="h-8 w-8 p-0"
                    >
                      {isExpanded ? (
                        <ChevronUp className="h-4 w-4" />
                      ) : (
                        <ChevronDown className="h-4 w-4" />
                      )}
                    </Button>
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {formatDate(log.created_at)}
                  </TableCell>
                  <TableCell>
                    <div className="space-y-1">
                      <Badge variant="outline">{log.actor_type}</Badge>
                      {log.user_id && (
                        <div className="text-xs text-muted-foreground">
                          User: {log.user_id.slice(0, 8)}...
                        </div>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary">{log.event_type}</Badge>
                  </TableCell>
                  <TableCell>
                    {log.workspace_id ? (
                      <div className="text-xs font-mono">
                        {log.workspace_id.slice(0, 8)}...
                      </div>
                    ) : (
                      <span className="text-muted-foreground">-</span>
                    )}
                  </TableCell>
                  <TableCell className="max-w-md truncate">
                    {log.description}
                  </TableCell>
                </TableRow>
                {isExpanded && (
                  <TableRow>
                    <TableCell colSpan={6} className="bg-muted/50">
                      <div className="space-y-2 p-4">
                        <div>
                          <strong className="text-sm">Full Details:</strong>
                          <pre className="mt-2 overflow-auto rounded bg-background p-2 text-xs">
                            {JSON.stringify(
                              {
                                id: log.id,
                                workspace_id: log.workspace_id,
                                user_id: log.user_id,
                                actor_type: log.actor_type,
                                event_type: log.event_type,
                                description: log.description,
                                metadata: log.metadata,
                                created_at: log.created_at,
                              },
                              null,
                              2
                            )}
                          </pre>
                        </div>
                      </div>
                    </TableCell>
                  </TableRow>
                )}
              </>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
