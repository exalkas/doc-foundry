"use client";

import { useState, useMemo } from "react";
import { AdminLayout } from "@/components/layout/admin-layout";
import { JobTable } from "@/components/admin/job-table";
import { JobFilters } from "@/components/admin/job-filters";
import { ReprocessJobModal } from "@/components/admin/reprocess-job-modal";
import { useJobs } from "@/hooks/use-jobs";
import type { Job, PaginatedResponse } from "@/lib/types";
import { PAGINATION } from "@/constants/pagination";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight } from "lucide-react";

export default function JobsPage() {
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [page, setPage] = useState(1);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const pageSize = PAGINATION.DEFAULT_PAGE_SIZE;

  const type =
    typeFilter === "all"
      ? undefined
      : (typeFilter as
          | "document_extraction"
          | "webhook_delivery"
          | "email_send"
          | "other");

  const status =
    statusFilter === "all"
      ? undefined
      : (statusFilter as "queued" | "processing" | "completed" | "failed");

  const { data: jobsData, isLoading } = useJobs({
    type,
    status,
    page,
    page_size: pageSize,
  });

  // Extract jobs array and pagination metadata
  const { jobs, pagination } = useMemo(() => {
    if (!jobsData) {
      return { jobs: [], pagination: null };
    }

    // Check if response is paginated
    if (typeof jobsData === "object" && "items" in jobsData) {
      const paginated = jobsData as PaginatedResponse<Job>;
      return {
        jobs: paginated.items,
        pagination: {
          total: paginated.total,
          page: paginated.page,
          page_size: paginated.page_size,
          total_pages: paginated.total_pages,
        },
      };
    }

    // Legacy array format
    const arrayData = jobsData as Job[];
    return { jobs: arrayData, pagination: null };
  }, [jobsData]);

  const handleReprocess = (jobId: string) => {
    const job = jobs.find((j) => j.id === jobId);
    if (job) {
      setSelectedJob(job);
    }
  };

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Jobs</h1>
          <p className="text-muted-foreground">
            View and manage background jobs across the platform
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>All Jobs</CardTitle>
            <CardDescription>
              Monitor and manage background processing jobs
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <JobFilters
              typeFilter={typeFilter}
              onTypeChange={setTypeFilter}
              statusFilter={statusFilter}
              onStatusChange={setStatusFilter}
            />

            <JobTable
              jobs={jobs}
              isLoading={isLoading}
              onReprocess={handleReprocess}
            />

            {jobs.length > 0 && (
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  {pagination
                    ? `Showing ${
                        (pagination.page - 1) * pagination.page_size + 1
                      }-${Math.min(
                        pagination.page * pagination.page_size,
                        pagination.total
                      )} of ${pagination.total} jobs`
                    : `Showing ${jobs.length} job${
                        jobs.length !== 1 ? "s" : ""
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
                        : jobs.length < pageSize
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

        {selectedJob && (
          <ReprocessJobModal
            jobId={selectedJob.id}
            jobType={selectedJob.type}
            open={!!selectedJob}
            onOpenChange={(open) => {
              if (!open) setSelectedJob(null);
            }}
          />
        )}
      </div>
    </AdminLayout>
  );
}
