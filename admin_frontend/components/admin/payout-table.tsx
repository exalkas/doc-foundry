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
import type { Payout } from "@/lib/types";
import { CheckCircle2, XCircle, DollarSign } from "lucide-react";

interface PayoutTableProps {
  payouts: Payout[];
  isLoading?: boolean;
  onApprove?: (payout: Payout) => void;
  onMarkPaid?: (payout: Payout) => void;
  onReject?: (payout: Payout) => void;
}

export function PayoutTable({
  payouts,
  isLoading = false,
  onApprove,
  onMarkPaid,
  onReject,
}: PayoutTableProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-sm text-muted-foreground">Loading payouts...</p>
      </div>
    );
  }

  if (payouts.length === 0) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-sm text-muted-foreground">No payouts found</p>
      </div>
    );
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Affiliate ID</TableHead>
            <TableHead>Amount</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Requested</TableHead>
            <TableHead>Processed</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {payouts.map((payout) => (
            <TableRow key={payout.id}>
              <TableCell className="font-mono text-xs">
                {payout.affiliate_id.slice(0, 8)}...
              </TableCell>
              <TableCell className="font-medium">
                {formatCurrency(payout.amount, payout.currency)}
              </TableCell>
              <TableCell>
                <Badge variant={getStatusColor(payout.status)}>
                  {payout.status}
                </Badge>
              </TableCell>
              <TableCell className="text-muted-foreground">
                {formatDate(payout.requested_at)}
              </TableCell>
              <TableCell className="text-muted-foreground">
                {payout.processed_at ? formatDate(payout.processed_at) : "-"}
              </TableCell>
              <TableCell className="text-right">
                <div className="flex justify-end gap-2">
                  {payout.status === "requested" && onApprove && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onApprove(payout)}
                    >
                      <CheckCircle2 className="h-4 w-4" />
                    </Button>
                  )}
                  {payout.status === "approved" && onMarkPaid && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onMarkPaid(payout)}
                    >
                      <DollarSign className="h-4 w-4" />
                    </Button>
                  )}
                  {payout.status === "requested" && onReject && (
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => onReject(payout)}
                    >
                      <XCircle className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
