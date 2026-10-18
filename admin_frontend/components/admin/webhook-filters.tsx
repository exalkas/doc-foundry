"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface WebhookFiltersProps {
  statusFilter: string;
  onStatusChange: (status: string) => void;
}

export function WebhookFilters({
  statusFilter,
  onStatusChange,
}: WebhookFiltersProps) {
  return (
    <Select value={statusFilter} onValueChange={onStatusChange}>
      <SelectTrigger className="w-full sm:w-[180px]">
        <SelectValue placeholder="Filter by status" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="all">All Statuses</SelectItem>
        <SelectItem value="active">Active</SelectItem>
        <SelectItem value="inactive">Inactive</SelectItem>
        <SelectItem value="failed">Failed</SelectItem>
      </SelectContent>
    </Select>
  );
}
