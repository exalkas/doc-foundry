"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatCurrency, getStatusColor } from "@/lib/utils";
import type { Subscription } from "@/lib/types";
import { ExternalLink } from "lucide-react";

interface SubscriptionDetailHeaderProps {
  subscription: Subscription;
}

export function SubscriptionDetailHeader({
  subscription,
}: SubscriptionDetailHeaderProps) {
  const stripeCustomerUrl = subscription.stripe_customer_id
    ? `https://dashboard.stripe.com/customers/${subscription.stripe_customer_id}`
    : null;

  return (
    <div className="flex items-center justify-between rounded-lg border bg-card p-6">
      <div className="space-y-1">
        <div className="flex items-center gap-3">
          <h2 className="text-2xl font-bold">{subscription.plan}</h2>
          <Badge variant={getStatusColor(subscription.status)}>
            {subscription.status}
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground">
          {subscription.user_email || "Unknown user"}
        </p>
        <p className="text-sm font-medium">
          {formatCurrency(subscription.amount, subscription.currency)} /{" "}
          {subscription.billing_period}
        </p>
      </div>
      {stripeCustomerUrl && (
        <Button variant="outline" size="sm" asChild>
          <a href={stripeCustomerUrl} target="_blank" rel="noopener noreferrer">
            View in Stripe
            <ExternalLink className="ml-2 h-4 w-4" />
          </a>
        </Button>
      )}
    </div>
  );
}
