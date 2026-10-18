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
import { formatDateTime, getStatusColor } from "@/lib/utils";
import type { Job } from "@/lib/types";
import { LoadingSpinner } from "@/components/ui/loading";

interface JobTableProps {
  jobs: Job[];
  isLoading?: boolean;
  onReprocess?: (jobId: string) => void;
}

export const JobTable = React.memo(function JobTable({
  jobs,
  isLoading = false,
  onReprocess,
}: JobTableProps) {
  if (isLoading) {
    return <LoadingSpinner message="Loading jobs..." />;
  }

  if (jobs.length === 0) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-sm text-muted-foreground">No jobs found</p>
      </div>
    );
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Type</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Attempts</TableHead>
            <TableHead>Error</TableHead>
            <TableHead>Created</TableHead>
            {onReprocess && (
              <TableHead className="text-right">Actions</TableHead>
            )}
          </TableRow>
        </TableHeader>
        <TableBody>
          {jobs.map((job) => (
            <TableRow key={job.id}>
              <TableCell className="font-medium">
                {job.type.replace("_", " ")}
              </TableCell>
              <TableCell>
                <Badge variant={getStatusColor(job.status)}>{job.status}</Badge>
              </TableCell>
              <TableCell className="text-muted-foreground">
                {job.attempts}
                {job.max_attempts && ` / ${job.max_attempts}`}
              </TableCell>
              <TableCell className="text-muted-foreground max-w-md truncate">
                {job.error || "-"}
              </TableCell>
              <TableCell className="text-muted-foreground">
                {formatDateTime(job.created_at)}
              </TableCell>
              {onReprocess && (
                <TableCell className="text-right">
                  {job.status === "failed" && (
                    <button
                      onClick={() => onReprocess(job.id)}
                      className="text-sm text-primary hover:underline"
                    >
                      Reprocess
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
