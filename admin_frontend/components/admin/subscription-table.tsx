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
import { formatCurrency, formatDate, getStatusColor } from "@/lib/utils";
import type { Subscription } from "@/lib/types";
import { ExternalLink } from "lucide-react";
import { LoadingSpinner } from "@/components/ui/loading";

/**
 * Props for SubscriptionTable component
 */
interface SubscriptionTableProps {
  /** Array of subscriptions to display */
  subscriptions: Subscription[];
  /** Whether data is currently loading */
  isLoading?: boolean;
}

export const SubscriptionTable = React.memo(function SubscriptionTable({
  subscriptions,
  isLoading = false,
}: SubscriptionTableProps) {
  if (isLoading) {
    return <LoadingSpinner message="Loading subscriptions..." />;
  }

  if (subscriptions.length === 0) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-sm text-muted-foreground">No subscriptions found</p>
      </div>
    );
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>User</TableHead>
            <TableHead>Plan</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Billing Period</TableHead>
            <TableHead>Amount</TableHead>
            <TableHead>Created</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {subscriptions.map((subscription) => (
            <TableRow key={subscription.id}>
              <TableCell className="font-medium">
                {subscription.user_email || "-"}
              </TableCell>
              <TableCell>{subscription.plan}</TableCell>
              <TableCell>
                <Badge variant={getStatusColor(subscription.status)}>
                  {subscription.status}
                </Badge>
              </TableCell>
              <TableCell className="text-muted-foreground capitalize">
                {subscription.billing_period}
              </TableCell>
              <TableCell className="font-medium">
                {formatCurrency(subscription.amount, subscription.currency)}
              </TableCell>
              <TableCell className="text-muted-foreground">
                {formatDate(subscription.created_at)}
              </TableCell>
              <TableCell className="text-right">
                <Link href={`/billing/${subscription.id}`}>
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
