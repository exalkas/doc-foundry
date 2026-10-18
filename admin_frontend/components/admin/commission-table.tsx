"use client";

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
import type { Commission } from "@/lib/types";
import { Edit } from "lucide-react";

interface CommissionTableProps {
  commissions: Commission[];
  isLoading?: boolean;
  onAdjust?: (commission: Commission) => void;
}

export function CommissionTable({
  commissions,
  isLoading = false,
  onAdjust,
}: CommissionTableProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-sm text-muted-foreground">Loading commissions...</p>
      </div>
    );
  }

  if (commissions.length === 0) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-sm text-muted-foreground">No commissions found</p>
      </div>
    );
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Affiliate ID</TableHead>
            <TableHead>Customer ID</TableHead>
            <TableHead>Event Type</TableHead>
            <TableHead>Amount</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Event Date</TableHead>
            {onAdjust && <TableHead className="text-right">Actions</TableHead>}
          </TableRow>
        </TableHeader>
        <TableBody>
          {commissions.map((commission) => (
            <TableRow key={commission.id}>
              <TableCell className="font-mono text-xs">
                {commission.affiliate_id.slice(0, 8)}...
              </TableCell>
              <TableCell className="font-mono text-xs">
                {commission.customer_id.slice(0, 8)}...
              </TableCell>
              <TableCell className="capitalize">
                {commission.event_type}
              </TableCell>
              <TableCell className="font-medium">
                {formatCurrency(commission.amount, commission.currency)}
              </TableCell>
              <TableCell>
                <Badge variant={getStatusColor(commission.status)}>
                  {commission.status}
                </Badge>
              </TableCell>
              <TableCell className="text-muted-foreground">
                {formatDate(commission.event_date)}
              </TableCell>
              {onAdjust && (
                <TableCell className="text-right">
                  {commission.status !== "paid" && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onAdjust(commission)}
                    >
                      <Edit className="h-4 w-4" />
                    </Button>
                  )}
                </TableCell>
              )}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
