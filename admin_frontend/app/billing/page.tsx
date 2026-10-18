"use client";

import { useState, useMemo } from "react";
import { AdminLayout } from "@/components/layout/admin-layout";
import { SubscriptionTable } from "@/components/admin/subscription-table";
import { SubscriptionFilters } from "@/components/admin/subscription-filters";
import { useSubscriptions } from "@/hooks/use-subscriptions";
import type { Subscription, PaginatedResponse } from "@/lib/types";
import { PAGINATION } from "@/constants/pagination";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight, ExternalLink } from "lucide-react";

export default function BillingPage() {
  const [planFilter, setPlanFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [page, setPage] = useState(1);
  const pageSize = PAGINATION.DEFAULT_PAGE_SIZE;

  const plan = planFilter === "all" ? undefined : planFilter;

  const status =
    statusFilter === "all"
      ? undefined
      : (statusFilter as
          | "active"
          | "canceled"
          | "past_due"
          | "trialing"
          | "incomplete"
          | "incomplete_expired");

  const { data: subscriptionsData, isLoading } = useSubscriptions({
    plan,
    status,
    page,
    page_size: pageSize,
  });

  // Extract subscriptions array and pagination metadata
  const { subscriptions, pagination } = useMemo(() => {
    if (!subscriptionsData) {
      return { subscriptions: [], pagination: null };
    }

    // Check if response is paginated
    if (typeof subscriptionsData === "object" && "items" in subscriptionsData) {
      const paginated = subscriptionsData as PaginatedResponse<Subscription>;
      return {
        subscriptions: paginated.items,
        pagination: {
          total: paginated.total,
          page: paginated.page,
          page_size: paginated.page_size,
          total_pages: paginated.total_pages,
        },
      };
    }

    // Legacy array format
    const arrayData = subscriptionsData as Subscription[];
    return { subscriptions: arrayData, pagination: null };
  }, [subscriptionsData]);

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Subscriptions</h1>
            <p className="text-muted-foreground">
              View and manage all subscriptions on the platform
            </p>
          </div>
          <Button variant="outline" size="sm" asChild>
            <a
              href="https://dashboard.stripe.com"
              target="_blank"
              rel="noopener noreferrer"
            >
              Stripe Dashboard
              <ExternalLink className="ml-2 h-4 w-4" />
            </a>
          </Button>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>All Subscriptions</CardTitle>
            <CardDescription>
              View and manage subscriptions across the platform
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <SubscriptionFilters
              planFilter={planFilter}
              onPlanChange={setPlanFilter}
              statusFilter={statusFilter}
              onStatusChange={setStatusFilter}
            />

            <SubscriptionTable
              subscriptions={subscriptions}
              isLoading={isLoading}
            />

            {subscriptions.length > 0 && (
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  {pagination
                    ? `Showing ${
                        (pagination.page - 1) * pagination.page_size + 1
                      }-${Math.min(
                        pagination.page * pagination.page_size,
                        pagination.total
                      )} of ${pagination.total} subscriptions`
                    : `Showing ${subscriptions.length} subscription${
                        subscriptions.length !== 1 ? "s" : ""
                      }`}
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1 || pagination?.page === 1}
                  >
                    <ChevronLeft className="h-4 w-4" />
                    Previous
                  </Button>
                  <span className="text-sm text-muted-foreground">
                    Page {page}
                    {pagination && ` of ${pagination.total_pages}`}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => p + 1)}
                    disabled={
                      pagination
                        ? pagination.page >= pagination.total_pages
                        : subscriptions.length < pageSize
                    }
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
