"use client";

import { useState } from "react";
import { AdminLayout } from "@/components/layout/admin-layout";
import { CouponTable } from "@/components/admin/coupon-table";
import { CouponFilters } from "@/components/admin/coupon-filters";
import { useCoupons } from "@/hooks/use-coupons";
import { PAGINATION } from "@/constants/pagination";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import Link from "next/link";

export default function CouponsPage() {
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [page, setPage] = useState(1);
  const pageSize = PAGINATION.DEFAULT_PAGE_SIZE;

  const status =
    statusFilter === "all"
      ? undefined
      : (statusFilter as "active" | "paused" | "expired");

  const { data: coupons = [], isLoading } = useCoupons({
    status,
    page,
    page_size: pageSize,
  });

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Coupons</h1>
            <p className="text-muted-foreground">
              Manage discount codes and affiliate promotions
            </p>
          </div>
          <Link href="/coupons/new">
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              Create Coupon
            </Button>
          </Link>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>All Coupons</CardTitle>
            <CardDescription>
              View and manage discount coupons across the platform
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex justify-end">
              <CouponFilters
                statusFilter={statusFilter}
                onStatusChange={setStatusFilter}
              />
            </div>

            <CouponTable coupons={coupons} isLoading={isLoading} />

            {coupons.length > 0 && (
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  Showing {coupons.length} coupon{coupons.length !== 1 ? "s" : ""}
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
                    disabled={coupons.length < pageSize}
                  >
                    Next
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </AdminLayout>
  );
}

