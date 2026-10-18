"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { formatCurrency } from "@/lib/utils";
import type { AffiliateStats } from "@/lib/types";
import { MousePointerClick, Users, DollarSign, TrendingUp } from "lucide-react";

interface AffiliateStatsProps {
  stats: AffiliateStats;
}

export function AffiliateStatsDisplay({ stats }: AffiliateStatsProps) {
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Total Clicks</CardTitle>
          <MousePointerClick className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{stats.total_clicks}</div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Total Signups</CardTitle>
          <Users className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{stats.total_signups}</div>
          <p className="text-xs text-muted-foreground">
            {stats.paying_customers} paying customers
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Total Earned</CardTitle>
          <DollarSign className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">
            {formatCurrency(stats.total_earned, "EUR")}
          </div>
          <div className="mt-2 space-y-1 text-xs text-muted-foreground">
            <p>Pending: {formatCurrency(stats.pending_earned, "EUR")}</p>
            <p>Cleared: {formatCurrency(stats.cleared_earned, "EUR")}</p>
            <p>Paid: {formatCurrency(stats.paid_earned, "EUR")}</p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">MRR Generated</CardTitle>
          <TrendingUp className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">
            {formatCurrency(stats.mrr_generated, "EUR")}
          </div>
          <p className="text-xs text-muted-foreground">Monthly recurring</p>
        </CardContent>
      </Card>
    </div>
  );
}
