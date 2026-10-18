"use client";

import { useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { AdminLayout } from "@/components/layout/admin-layout";
import { CommissionTable } from "@/components/admin/commission-table";
import { AdjustCommissionModal } from "@/components/admin/adjust-commission-modal";
import { useCommissions } from "@/hooks/use-commissions";
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
import { Spinner } from "@/components/ui/spinner";
import type { Commission } from "@/lib/types";
import { PAGINATION } from "@/constants/pagination";

function CommissionsContent() {
  const searchParams = useSearchParams();
  const affiliateIdParam = searchParams.get("affiliate_id");

  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [page, setPage] = useState(1);
  const [selectedCommission, setSelectedCommission] =
    useState<Commission | null>(null);
  const pageSize = PAGINATION.DEFAULT_PAGE_SIZE;

  const status =
    statusFilter === "all"
      ? undefined
      : (statusFilter as "pending" | "cleared" | "paid" | "reversed");

  const { data: commissions = [], isLoading } = useCommissions({
    affiliate_id: affiliateIdParam || undefined,
    status,
    page,
    page_size: pageSize,
  });

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Commissions</h1>
          <p className="text-muted-foreground">
            Manage and adjust affiliate commissions
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>All Commissions</CardTitle>
            <CardDescription>
              View and manage commissions across all affiliates
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
                  <SelectItem value="pending">Pending</SelectItem>
                  <SelectItem value="cleared">Cleared</SelectItem>
                  <SelectItem value="paid">Paid</SelectItem>
                  <SelectItem value="reversed">Reversed</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <CommissionTable
              commissions={commissions}
              isLoading={isLoading}
              onAdjust={setSelectedCommission}
            />

            {commissions.length > 0 && (
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  Showing {commissions.length} commission
                  {commissions.length !== 1 ? "s" : ""}
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
                    disabled={commissions.length < pageSize}
                  >
                    Next
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <AdjustCommissionModal
          commission={selectedCommission}
          open={!!selectedCommission}
          onOpenChange={(open) => !open && setSelectedCommission(null)}
        />
      </div>
    </AdminLayout>
  );
}

export default function CommissionsPage() {
  return (
    <Suspense
      fallback={
        <AdminLayout>
          <div className="flex items-center justify-center py-12">
            <Spinner />
          </div>
        </AdminLayout>
      }
    >
      <CommissionsContent />
    </Suspense>
  );
}
