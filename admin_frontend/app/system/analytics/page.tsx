"use client";

import { useState } from "react";
import { AdminLayout } from "@/components/layout/admin-layout";
import { useAnalytics } from "@/hooks/use-analytics";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Download,
  Building2,
  Users,
  CreditCard,
  TrendingUp,
} from "lucide-react";

export default function AnalyticsPage() {
  const [fromDate, setFromDate] = useState<string>("");
  const [toDate, setToDate] = useState<string>("");

  const { data: analytics, isLoading } = useAnalytics({
    from: fromDate || undefined,
    to: toDate || undefined,
  });

  const handleExportCSV = () => {
    if (!analytics) return;

    const headers = ["Date", "Workspaces Created", "Subscriptions Created"];
    const rows = analytics.growth_trends.workspaces.map((item, idx) => [
      item.date,
      item.count.toString(),
      analytics.growth_trends.subscriptions[idx]?.count.toString() || "0",
    ]);

    const csvContent = [
      headers.join(","),
      ...rows.map((row) => row.join(",")),
    ].join("\n");

    const blob = new Blob([csvContent], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `analytics-${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleExportJSON = () => {
    if (!analytics) return;

    const jsonContent = JSON.stringify(analytics, null, 2);
    const blob = new Blob([jsonContent], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `analytics-${new Date().toISOString().split("T")[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            Platform Analytics
          </h1>
          <p className="text-muted-foreground">
            Platform-wide metrics and growth trends
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Date Range Filter</CardTitle>
            <CardDescription>
              Select a date range to analyze platform growth
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="from-date">From Date</Label>
                <Input
                  id="from-date"
                  type="date"
                  value={fromDate}
                  onChange={(e) => setFromDate(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="to-date">To Date</Label>
                <Input
                  id="to-date"
                  type="date"
                  value={toDate}
                  onChange={(e) => setToDate(e.target.value)}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                Total Workspaces
              </CardTitle>
              <Building2 className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <Skeleton className="h-8 w-20" />
              ) : (
                <div className="text-2xl font-bold">
                  {analytics?.total_workspaces || 0}
                </div>
              )}
              <p className="text-xs text-muted-foreground">
                All workspaces on platform
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                Active Workspaces
              </CardTitle>
              <Building2 className="h-4 w-4 text-green-600" />
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <Skeleton className="h-8 w-20" />
              ) : (
                <div className="text-2xl font-bold">
                  {analytics?.active_workspaces || 0}
                </div>
              )}
              <p className="text-xs text-muted-foreground">
                Currently active workspaces
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                Active Subscriptions
              </CardTitle>
              <CreditCard className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <Skeleton className="h-8 w-20" />
              ) : (
                <div className="text-2xl font-bold">
                  {analytics?.active_subscriptions || 0}
                </div>
              )}
              <p className="text-xs text-muted-foreground">
                Active and trialing subscriptions
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total MRR</CardTitle>
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <Skeleton className="h-8 w-20" />
              ) : (
                <div className="text-2xl font-bold">
                  ${(analytics?.total_mrr || 0).toFixed(2)}
                </div>
              )}
              <p className="text-xs text-muted-foreground">
                Monthly recurring revenue
              </p>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Growth Trends</CardTitle>
                <CardDescription>
                  Workspace and subscription growth over time
                </CardDescription>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={handleExportCSV}>
                  <Download className="mr-2 h-4 w-4" />
                  Export CSV
                </Button>
                <Button variant="outline" size="sm" onClick={handleExportJSON}>
                  <Download className="mr-2 h-4 w-4" />
                  Export JSON
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-64 w-full" />
            ) : (
              <div className="space-y-6">
                <div>
                  <h3 className="text-sm font-medium mb-4">
                    Workspaces Created
                  </h3>
                  <div className="grid grid-cols-7 gap-2">
                    {analytics?.growth_trends.workspaces
                      .slice(-7)
                      .map((item) => (
                        <div
                          key={item.date}
                          className="flex flex-col items-center space-y-1"
                        >
                          <div className="text-xs text-muted-foreground">
                            {new Date(item.date).toLocaleDateString("en-US", {
                              month: "short",
                              day: "numeric",
                            })}
                          </div>
                          <div className="text-sm font-semibold">
                            {item.count}
                          </div>
                        </div>
                      ))}
                  </div>
                </div>
                <div>
                  <h3 className="text-sm font-medium mb-4">
                    Subscriptions Created
                  </h3>
                  <div className="grid grid-cols-7 gap-2">
                    {analytics?.growth_trends.subscriptions
                      .slice(-7)
                      .map((item) => (
                        <div
                          key={item.date}
                          className="flex flex-col items-center space-y-1"
                        >
                          <div className="text-xs text-muted-foreground">
                            {new Date(item.date).toLocaleDateString("en-US", {
                              month: "short",
                              day: "numeric",
                            })}
                          </div>
                          <div className="text-sm font-semibold">
                            {item.count}
                          </div>
                        </div>
                      ))}
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </AdminLayout>
  );
}
