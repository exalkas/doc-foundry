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
import type { WebhookDelivery } from "@/lib/types";
import { LoadingSpinner } from "@/components/ui/loading";

interface WebhookDeliveryTableProps {
  deliveries: WebhookDelivery[];
  isLoading?: boolean;
  onRetry?: (deliveryId: string) => void;
}

export const WebhookDeliveryTable = React.memo(function WebhookDeliveryTable({
  deliveries,
  isLoading = false,
  onRetry,
}: WebhookDeliveryTableProps) {
  if (isLoading) {
    return <LoadingSpinner message="Loading deliveries..." />;
  }

  if (deliveries.length === 0) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-sm text-muted-foreground">No deliveries found</p>
      </div>
    );
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Event Type</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Status Code</TableHead>
            <TableHead>Attempts</TableHead>
            <TableHead>Last Error</TableHead>
            <TableHead>Created</TableHead>
            {onRetry && <TableHead className="text-right">Actions</TableHead>}
          </TableRow>
        </TableHeader>
        <TableBody>
          {deliveries.map((delivery) => (
            <TableRow key={delivery.id}>
              <TableCell className="font-medium">
                {delivery.event_type}
              </TableCell>
              <TableCell>
                <Badge variant={getStatusColor(delivery.status)}>
                  {delivery.status}
                </Badge>
              </TableCell>
              <TableCell className="text-muted-foreground">
                {delivery.status_code || "-"}
              </TableCell>
              <TableCell className="text-muted-foreground">
                {delivery.attempt_count}
                {delivery.max_attempts && ` / ${delivery.max_attempts}`}
              </TableCell>
              <TableCell className="text-muted-foreground max-w-md truncate">
                {delivery.last_error || "-"}
              </TableCell>
              <TableCell className="text-muted-foreground">
                {formatDateTime(delivery.created_at)}
              </TableCell>
              {onRetry && (
                <TableCell className="text-right">
                  {delivery.status === "failed" && (
                    <button
                      onClick={() => onRetry(delivery.id)}
                      className="text-sm text-primary hover:underline"
                    >
                      Retry
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
