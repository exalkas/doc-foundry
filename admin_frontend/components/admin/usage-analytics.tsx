"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { formatNumber } from "@/lib/utils";
import type { UsageAnalytics } from "@/lib/types";
import { FileText, File, BarChart3 } from "lucide-react";

interface UsageAnalyticsProps {
  analytics: UsageAnalytics;
}

export function UsageAnalyticsDisplay({ analytics }: UsageAnalyticsProps) {
  const { current_period, breakdown, history } = analytics;

  return (
    <div className="space-y-6">
      {/* Current Period Summary */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Total Documents
            </CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatNumber(current_period.usage.total_documents)}
            </div>
            <p className="text-xs text-muted-foreground">
              Current billing period
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Pages</CardTitle>
            <File className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatNumber(current_period.usage.total_pages)}
            </div>
            <p className="text-xs text-muted-foreground">
              Current billing period
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Breakdown Sections */}
      {breakdown.by_project && Object.keys(breakdown.by_project).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Usage by Project</CardTitle>
            <CardDescription>
              Document count breakdown by project
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {Object.entries(breakdown.by_project).map(([project, count]) => (
                <div
                  key={project}
                  className="flex items-center justify-between rounded-md border p-3"
                >
                  <span className="font-medium">{project}</span>
                  <span className="text-muted-foreground">
                    {formatNumber(count)} documents
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {breakdown.by_template &&
        Object.keys(breakdown.by_template).length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Usage by Template</CardTitle>
              <CardDescription>
                Document count breakdown by template
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {Object.entries(breakdown.by_template).map(
                  ([template, count]) => (
                    <div
                      key={template}
                      className="flex items-center justify-between rounded-md border p-3"
                    >
                      <span className="font-medium">{template}</span>
                      <span className="text-muted-foreground">
                        {formatNumber(count)} documents
                      </span>
                    </div>
                  )
                )}
              </div>
            </CardContent>
          </Card>
        )}

      {breakdown.by_source && Object.keys(breakdown.by_source).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Usage by Source</CardTitle>
            <CardDescription>
              Document count breakdown by source (UI vs API)
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {Object.entries(breakdown.by_source).map(([source, count]) => (
                <div
                  key={source}
                  className="flex items-center justify-between rounded-md border p-3"
                >
                  <span className="font-medium capitalize">{source}</span>
                  <span className="text-muted-foreground">
                    {formatNumber(count)} documents
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* History Table */}
      {history && history.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Usage History</CardTitle>
            <CardDescription>
              Daily usage over the last {history.length} days
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {history.slice(0, 30).map((entry, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between rounded-md border p-3"
                >
                  <span className="font-medium">{entry.date}</span>
                  <div className="flex gap-4 text-sm text-muted-foreground">
                    <span>{formatNumber(entry.documents)} docs</span>
                    <span>{formatNumber(entry.pages)} pages</span>
                  </div>
                </div>
              ))}
              {history.length > 30 && (
                <p className="text-xs text-muted-foreground text-center pt-2">
                  Showing last 30 days of {history.length} total days
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
