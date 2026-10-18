"use client";

import { AdminLayout } from "@/components/layout/admin-layout";
import { useMetrics } from "@/hooks/use-metrics";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Activity, Clock, FileText, AlertCircle } from "lucide-react";

export default function MetricsPage() {
  const { data: metrics, isLoading } = useMetrics();

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">System Metrics</h1>
          <p className="text-muted-foreground">
            Real-time system health and performance metrics
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Queue Depth</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <Skeleton className="h-8 w-20" />
              ) : (
                <div className="text-2xl font-bold">
                  {metrics?.queue_depth || 0}
                </div>
              )}
              <p className="text-xs text-muted-foreground">
                Jobs waiting in queue
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                Avg Processing Time
              </CardTitle>
              <Clock className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <Skeleton className="h-8 w-20" />
              ) : (
                <div className="text-2xl font-bold">
                  {metrics?.avg_processing_time_ms
                    ? `${Math.round(metrics.avg_processing_time_ms)}ms`
                    : "N/A"}
                </div>
              )}
              <p className="text-xs text-muted-foreground">
                Average job processing time
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                Documents Today
              </CardTitle>
              <FileText className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <Skeleton className="h-8 w-20" />
              ) : (
                <div className="text-2xl font-bold">
                  {metrics?.daily_documents_processed || 0}
                </div>
              )}
              <p className="text-xs text-muted-foreground">
                Documents processed in last 24h
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                Errors (24h)
              </CardTitle>
              <AlertCircle className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <Skeleton className="h-8 w-20" />
              ) : (
                <div className="text-2xl font-bold">
                  {metrics?.errors_last_24h || 0}
                </div>
              )}
              <p className="text-xs text-muted-foreground">
                Failed jobs in last 24h
              </p>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>7-Day Trends</CardTitle>
            <CardDescription>
              Document processing and job success/failure trends
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-4">
                <Skeleton className="h-64 w-full" />
              </div>
            ) : (
              <div className="space-y-4">
                <div>
                  <h3 className="text-sm font-medium mb-2">
                    Documents Processed
                  </h3>
                  <div className="grid grid-cols-7 gap-2">
                    {metrics?.trends_7d.documents_processed.map((item) => (
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
                  <h3 className="text-sm font-medium mb-2">Job Status</h3>
                  <div className="grid grid-cols-7 gap-2">
                    {metrics?.trends_7d.jobs_succeeded.map((item, idx) => (
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
                        <div className="flex gap-1">
                          <div className="text-xs text-green-600">
                            ✓
                            {metrics?.trends_7d.jobs_succeeded[idx]?.count || 0}
                          </div>
                          <div className="text-xs text-red-600">
                            ✗{metrics?.trends_7d.jobs_failed[idx]?.count || 0}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>30-Day Trends</CardTitle>
            <CardDescription>
              Weekly aggregated trends over the last 30 days
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-64 w-full" />
            ) : (
              <div className="space-y-4">
                <div>
                  <h3 className="text-sm font-medium mb-2">
                    Documents Processed (Weekly)
                  </h3>
                  <div className="grid grid-cols-5 gap-2">
                    {metrics?.trends_30d.documents_processed.map((item) => (
                      <div
                        key={item.week_start}
                        className="flex flex-col items-center space-y-1"
                      >
                        <div className="text-xs text-muted-foreground">
                          {new Date(item.week_start).toLocaleDateString(
                            "en-US",
                            {
                              month: "short",
                              day: "numeric",
                            }
                          )}
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
