"use client";

import { use, useState, useMemo } from "react";
import { AdminLayout } from "@/components/layout/admin-layout";
import { WebhookDeliveryTable } from "@/components/admin/webhook-delivery-table";
import { RetryDeliveryModal } from "@/components/admin/retry-delivery-modal";
import { useWebhookDeliveries } from "@/hooks/use-webhook-deliveries";
import { useWebhooks } from "@/hooks/use-webhooks";
import type { WebhookDelivery, Webhook, PaginatedResponse } from "@/lib/types";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import Link from "next/link";
import { ArrowLeft, ChevronLeft, ChevronRight } from "lucide-react";
import { PAGINATION } from "@/constants/pagination";

interface WebhookDeliveriesPageProps {
  params: Promise<{ id: string }>;
}

export default function WebhookDeliveriesPage({
  params,
}: WebhookDeliveriesPageProps) {
  const { id } = use(params);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [page, setPage] = useState(1);
  const [selectedDelivery, setSelectedDelivery] =
    useState<WebhookDelivery | null>(null);
  const pageSize = PAGINATION.DEFAULT_PAGE_SIZE;

  // Fetch webhook info to get URL
  const { data: webhooksData } = useWebhooks({});
  const webhook = useMemo(() => {
    if (!webhooksData) return null;
    const webhooks =
      typeof webhooksData === "object" && "items" in webhooksData
        ? (webhooksData as PaginatedResponse<Webhook>).items
        : (webhooksData as Webhook[]);
    return webhooks.find((w) => w.id === id);
  }, [webhooksData, id]);

  const status =
    statusFilter === "all"
      ? undefined
      : (statusFilter as "pending" | "success" | "failed");

  const { data: deliveriesData, isLoading } = useWebhookDeliveries({
    webhook_id: id,
    status,
    page,
    page_size: pageSize,
  });

  // Extract deliveries array and pagination metadata
  const { deliveries, pagination } = useMemo(() => {
    if (!deliveriesData) {
      return { deliveries: [], pagination: null };
    }

    // Check if response is paginated
    if (typeof deliveriesData === "object" && "items" in deliveriesData) {
      const paginated = deliveriesData as PaginatedResponse<WebhookDelivery>;
      return {
        deliveries: paginated.items,
        pagination: {
          total: paginated.total,
          page: paginated.page,
          page_size: paginated.page_size,
          total_pages: paginated.total_pages,
        },
      };
    }

    // Legacy array format
    const arrayData = deliveriesData as WebhookDelivery[];
    return { deliveries: arrayData, pagination: null };
  }, [deliveriesData]);

  const handleRetry = (deliveryId: string) => {
    const delivery = deliveries.find((d) => d.id === deliveryId);
    if (delivery) {
      setSelectedDelivery(delivery);
    }
  };

  if (isLoading) {
    return (
      <AdminLayout>
        <div className="flex items-center justify-center py-12">
          <Spinner />
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Link href="/support/webhooks">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Webhooks
            </Button>
          </Link>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Webhook Deliveries</CardTitle>
            <CardDescription>
              {webhook
                ? `Delivery history for ${webhook.url}`
                : "View delivery history for this webhook"}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <WebhookDeliveryTable
              deliveries={deliveries}
              isLoading={isLoading}
              onRetry={handleRetry}
            />

            {deliveries.length > 0 && (
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  {pagination
                    ? `Showing ${
                        (pagination.page - 1) * pagination.page_size + 1
                      }-${Math.min(
                        pagination.page * pagination.page_size,
                        pagination.total
                      )} of ${pagination.total} deliveries`
                    : `Showing ${deliveries.length} deliver${
                        deliveries.length !== 1 ? "ies" : "y"
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
                        : deliveries.length < pageSize
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

        {selectedDelivery && webhook && (
          <RetryDeliveryModal
            deliveryId={selectedDelivery.id}
            webhookUrl={webhook.url}
            open={!!selectedDelivery}
            onOpenChange={(open) => {
              if (!open) setSelectedDelivery(null);
            }}
          />
        )}
      </div>
    </AdminLayout>
  );
}
