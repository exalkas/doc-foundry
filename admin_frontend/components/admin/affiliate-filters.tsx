"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface AffiliateFiltersProps {
  statusFilter: string;
  onStatusChange: (status: string) => void;
}

export function AffiliateFilters({
  statusFilter,
  onStatusChange,
}: AffiliateFiltersProps) {
  return (
    <Select value={statusFilter} onValueChange={onStatusChange}>
      <SelectTrigger className="w-full sm:w-[180px]">
        <SelectValue placeholder="Filter by status" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="all">All Statuses</SelectItem>
        <SelectItem value="pending">Pending</SelectItem>
        <SelectItem value="approved">Approved</SelectItem>
        <SelectItem value="rejected">Rejected</SelectItem>
        <SelectItem value="blocked">Blocked</SelectItem>
      </SelectContent>
    </Select>
  );
}
