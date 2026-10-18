"use client";

import { use } from "react";
import { AdminLayout } from "@/components/layout/admin-layout";
import { SubscriptionDetailHeader } from "@/components/admin/subscription-detail-header";
import { useSubscription } from "@/hooks/use-subscription";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { Badge } from "@/components/ui/badge";
import Link from "next/link";
import { ArrowLeft, ExternalLink } from "lucide-react";
import {
  formatCurrency,
  formatDate,
  formatDateTime,
  getStatusColor,
} from "@/lib/utils";

interface SubscriptionDetailPageProps {
  params: Promise<{ id: string }>;
}

export default function SubscriptionDetailPage({
  params,
}: SubscriptionDetailPageProps) {
  const { id } = use(params);
  const { data: subscription, isLoading, error } = useSubscription(id);

  if (isLoading) {
    return (
      <AdminLayout>
        <div className="flex items-center justify-center py-12">
          <Spinner />
        </div>
      </AdminLayout>
    );
  }

  if (error || !subscription) {
    return (
      <AdminLayout>
        <div className="space-y-6">
          <div className="flex items-center gap-4">
            <Link href="/billing">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Subscriptions
              </Button>
            </Link>
          </div>
          <Card>
            <CardContent className="pt-6">
              <p className="text-center text-muted-foreground">
                Subscription not found or error loading subscription
              </p>
            </CardContent>
          </Card>
        </div>
      </AdminLayout>
    );
  }

  const stripeCustomerUrl = subscription.stripe_customer_id
    ? `https://dashboard.stripe.com/customers/${subscription.stripe_customer_id}`
    : null;

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Link href="/billing">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Subscriptions
            </Button>
          </Link>
        </div>

        <SubscriptionDetailHeader subscription={subscription} />

        <div className="grid gap-6 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Subscription Information</CardTitle>
              <CardDescription>
                Basic information about this subscription
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <p className="text-sm font-medium text-muted-foreground">
                  Plan
                </p>
                <p className="mt-1">{subscription.plan}</p>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">
                  Status
                </p>
                <Badge
                  variant={getStatusColor(subscription.status)}
                  className="mt-1"
                >
                  {subscription.status}
                </Badge>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">
                  Billing Period
                </p>
                <p className="mt-1 capitalize">{subscription.billing_period}</p>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">
                  Amount
                </p>
                <p className="mt-1">
                  {formatCurrency(subscription.amount, subscription.currency)}
                </p>
              </div>
              {subscription.current_period_start && (
                <div>
                  <p className="text-sm font-medium text-muted-foreground">
                    Current Period Start
                  </p>
                  <p className="mt-1">
                    {formatDateTime(subscription.current_period_start)}
                  </p>
                </div>
              )}
              {subscription.current_period_end && (
                <div>
                  <p className="text-sm font-medium text-muted-foreground">
                    Current Period End
                  </p>
                  <p className="mt-1">
                    {formatDateTime(subscription.current_period_end)}
                  </p>
                </div>
              )}
              {subscription.cancel_at_period_end && (
                <div>
                  <p className="text-sm font-medium text-muted-foreground">
                    Cancellation
                  </p>
                  <p className="mt-1">Will cancel at end of current period</p>
                </div>
              )}
              {subscription.canceled_at && (
                <div>
                  <p className="text-sm font-medium text-muted-foreground">
                    Canceled At
                  </p>
                  <p className="mt-1">
                    {formatDateTime(subscription.canceled_at)}
                  </p>
                </div>
              )}
              {stripeCustomerUrl && (
                <div>
                  <Button variant="outline" size="sm" asChild>
                    <a
                      href={stripeCustomerUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      View in Stripe
                      <ExternalLink className="ml-2 h-4 w-4" />
                    </a>
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          {subscription.usage_vs_limits && (
            <Card>
              <CardHeader>
                <CardTitle>Usage vs Limits</CardTitle>
                <CardDescription>
                  Current usage compared to plan limits
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Documents</span>
                    <span className="font-medium">
                      {subscription.usage_vs_limits.documents_used} /{" "}
                      {subscription.usage_vs_limits.documents_limit === -1
                        ? "∞"
                        : subscription.usage_vs_limits.documents_limit}
                    </span>
                  </div>
                  <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full bg-primary"
                      style={{
                        width: `${
                          subscription.usage_vs_limits.documents_limit === -1
                            ? 0
                            : Math.min(
                                100,
                                (subscription.usage_vs_limits.documents_used /
                                  subscription.usage_vs_limits
                                    .documents_limit) *
                                  100
                              )
                        }%`,
                      }}
                    />
                  </div>
                </div>
                <div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Pages</span>
                    <span className="font-medium">
                      {subscription.usage_vs_limits.pages_used} /{" "}
                      {subscription.usage_vs_limits.pages_limit === -1
                        ? "∞"
                        : subscription.usage_vs_limits.pages_limit}
                    </span>
                  </div>
                  <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full bg-primary"
                      style={{
                        width: `${
                          subscription.usage_vs_limits.pages_limit === -1
                            ? 0
                            : Math.min(
                                100,
                                (subscription.usage_vs_limits.pages_used /
                                  subscription.usage_vs_limits.pages_limit) *
                                  100
                              )
                        }%`,
                      }}
                    />
                  </div>
                </div>
                {subscription.usage_vs_limits.projects_used !== undefined &&
                  subscription.usage_vs_limits.projects_limit !== undefined && (
                    <div>
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">Projects</span>
                        <span className="font-medium">
                          {subscription.usage_vs_limits.projects_used} /{" "}
                          {subscription.usage_vs_limits.projects_limit === -1
                            ? "∞"
                            : subscription.usage_vs_limits.projects_limit}
                        </span>
                      </div>
                      <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-muted">
                        <div
                          className="h-full bg-primary"
                          style={{
                            width: `${
                              subscription.usage_vs_limits.projects_limit === -1
                                ? 0
                                : Math.min(
                                    100,
                                    (subscription.usage_vs_limits
                                      .projects_used /
                                      subscription.usage_vs_limits
                                        .projects_limit) *
                                      100
                                  )
                            }%`,
                          }}
                        />
                      </div>
                    </div>
                  )}
              </CardContent>
            </Card>
          )}

          {subscription.billing_history &&
            subscription.billing_history.length > 0 && (
              <Card className="md:col-span-2">
                <CardHeader>
                  <CardTitle>Billing History</CardTitle>
                  <CardDescription>
                    Payment history for this subscription
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {subscription.billing_history.map((item) => (
                      <div
                        key={item.id}
                        className="flex items-center justify-between rounded-md border p-4"
                      >
                        <div>
                          <p className="font-medium">
                            {formatCurrency(item.amount, item.currency)}
                          </p>
                          <p className="text-sm text-muted-foreground">
                            {formatDate(item.created_at)}
                          </p>
                        </div>
                        <div className="flex items-center gap-4">
                          <Badge
                            variant={
                              item.status === "paid"
                                ? "success"
                                : item.status === "pending"
                                ? "warning"
                                : "destructive"
                            }
                          >
                            {item.status}
                          </Badge>
                          {item.invoice_url && (
                            <Button variant="outline" size="sm" asChild>
                              <a
                                href={item.invoice_url}
                                target="_blank"
                                rel="noopener noreferrer"
                              >
                                View Invoice
                                <ExternalLink className="ml-2 h-4 w-4" />
                              </a>
                            </Button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
        </div>
      </div>
    </AdminLayout>
  );
}
