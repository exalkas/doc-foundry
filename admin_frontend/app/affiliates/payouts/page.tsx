"use client";

import { useState } from "react";
import { AdminLayout } from "@/components/layout/admin-layout";
import { PayoutTable } from "@/components/admin/payout-table";
import { ApprovePayoutModal } from "@/components/admin/approve-payout-modal";
import { MarkPaidModal } from "@/components/admin/mark-paid-modal";
import { RejectPayoutModal } from "@/components/admin/reject-payout-modal";
import { usePayouts } from "@/hooks/use-payouts";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { Payout } from "@/lib/types";
import { PAGINATION } from "@/constants/pagination";

export default function PayoutsPage() {
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [page, setPage] = useState(1);
  const [selectedPayout, setSelectedPayout] = useState<Payout | null>(null);
  const [actionType, setActionType] = useState<
    "approve" | "markPaid" | "reject" | null
  >(null);
  const pageSize = PAGINATION.DEFAULT_PAGE_SIZE;

  const status =
    statusFilter === "all"
      ? undefined
      : (statusFilter as "requested" | "approved" | "paid" | "rejected");

  const { data: payouts = [], isLoading } = usePayouts({
    status,
    page,
    page_size: pageSize,
  });

  const handleApprove = (payout: Payout) => {
    setSelectedPayout(payout);
    setActionType("approve");
  };

  const handleMarkPaid = (payout: Payout) => {
    setSelectedPayout(payout);
    setActionType("markPaid");
  };

  const handleReject = (payout: Payout) => {
    setSelectedPayout(payout);
    setActionType("reject");
  };

  const closeModal = () => {
    setSelectedPayout(null);
    setActionType(null);
  };

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Payouts</h1>
          <p className="text-muted-foreground">
            Manage affiliate payout requests
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>All Payouts</CardTitle>
            <CardDescription>
              View and manage payout requests across all affiliates
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex justify-end">
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-full sm:w-[180px]">
                  <SelectValue placeholder="Filter by status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Statuses</SelectItem>
                  <SelectItem value="requested">Requested</SelectItem>
                  <SelectItem value="approved">Approved</SelectItem>
                  <SelectItem value="paid">Paid</SelectItem>
                  <SelectItem value="rejected">Rejected</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <PayoutTable
              payouts={payouts}
              isLoading={isLoading}
              onApprove={handleApprove}
              onMarkPaid={handleMarkPaid}
              onReject={handleReject}
            />

            {payouts.length > 0 && (
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  Showing {payouts.length} payout
                  {payouts.length !== 1 ? "s" : ""}
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                  >
                    <ChevronLeft className="h-4 w-4" />
                    Previous
                  </Button>
                  <span className="text-sm text-muted-foreground">
                    Page {page}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => p + 1)}
                    disabled={payouts.length < pageSize}
                  >
                    Next
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {actionType === "approve" && (
          <ApprovePayoutModal
            payout={selectedPayout}
            open={!!selectedPayout}
            onOpenChange={(open) => !open && closeModal()}
          />
        )}

        {actionType === "markPaid" && (
          <MarkPaidModal
            payout={selectedPayout}
            open={!!selectedPayout}
            onOpenChange={(open) => !open && closeModal()}
          />
        )}

        {actionType === "reject" && (
          <RejectPayoutModal
            payout={selectedPayout}
            open={!!selectedPayout}
            onOpenChange={(open) => !open && closeModal()}
          />
        )}
      </div>
    </AdminLayout>
  );
}
