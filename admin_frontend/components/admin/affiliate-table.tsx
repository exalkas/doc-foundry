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
import type { Affiliate } from "@/lib/types";
import { ExternalLink } from "lucide-react";
import { LoadingSpinner } from "@/components/ui/loading";

interface AffiliateTableProps {
  affiliates: Affiliate[];
  isLoading?: boolean;
}

export const AffiliateTable = React.memo(function AffiliateTable({
  affiliates,
  isLoading = false,
}: AffiliateTableProps) {
  if (isLoading) {
    return <LoadingSpinner message="Loading affiliates..." />;
  }

  if (affiliates.length === 0) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-sm text-muted-foreground">No affiliates found</p>
      </div>
    );
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Email</TableHead>
            <TableHead>Company</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Signups</TableHead>
            <TableHead>Earnings</TableHead>
            <TableHead>Created</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {affiliates.map((affiliate) => (
            <TableRow
              key={affiliate.id}
              className={affiliate.status === "pending" ? "bg-muted/50" : ""}
            >
              <TableCell className="font-medium">
                {affiliate.user_email}
              </TableCell>
              <TableCell>{affiliate.company_name || "-"}</TableCell>
              <TableCell>
                <Badge variant={getStatusColor(affiliate.status)}>
                  {affiliate.status}
                </Badge>
              </TableCell>
              <TableCell>{affiliate.stats?.total_signups || 0}</TableCell>
              <TableCell className="font-medium">
                {affiliate.stats
                  ? formatCurrency(affiliate.stats.total_earned, "EUR")
                  : "-"}
              </TableCell>
              <TableCell className="text-muted-foreground">
                {formatDate(affiliate.created_at)}
              </TableCell>
              <TableCell className="text-right">
                <Link href={`/affiliates/${affiliate.id}`}>
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
