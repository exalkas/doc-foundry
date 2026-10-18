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
import type { Webhook } from "@/lib/types";
import { ExternalLink } from "lucide-react";
import { LoadingSpinner } from "@/components/ui/loading";

interface WebhookTableProps {
  webhooks: Webhook[];
  isLoading?: boolean;
}

export const WebhookTable = React.memo(function WebhookTable({
  webhooks,
  isLoading = false,
}: WebhookTableProps) {
  if (isLoading) {
    return <LoadingSpinner message="Loading webhooks..." />;
  }

  if (webhooks.length === 0) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-sm text-muted-foreground">No webhooks found</p>
      </div>
    );
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Workspace</TableHead>
            <TableHead>URL</TableHead>
            <TableHead>Events</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Last Delivery</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {webhooks.map((webhook) => (
            <TableRow key={webhook.id}>
              <TableCell className="font-medium">
                {webhook.workspace_name || "-"}
              </TableCell>
              <TableCell className="text-muted-foreground max-w-md truncate">
                {webhook.url}
              </TableCell>
              <TableCell className="text-muted-foreground">
                {webhook.events.length > 0 ? webhook.events.join(", ") : "-"}
              </TableCell>
              <TableCell>
                <Badge variant={getStatusColor(webhook.status)}>
                  {webhook.status}
                </Badge>
              </TableCell>
              <TableCell className="text-muted-foreground">
                {webhook.last_delivery
                  ? formatDate(webhook.last_delivery)
                  : "-"}
              </TableCell>
              <TableCell className="text-right">
                <Link href={`/support/webhooks/${webhook.id}/deliveries`}>
                  <Button variant="ghost" size="sm">
                    View Deliveries
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
