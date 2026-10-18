"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface SubscriptionFiltersProps {
  planFilter: string;
  onPlanChange: (plan: string) => void;
  statusFilter: string;
  onStatusChange: (status: string) => void;
}

export function SubscriptionFilters({
  planFilter,
  onPlanChange,
  statusFilter,
  onStatusChange,
}: SubscriptionFiltersProps) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
      <Select value={planFilter} onValueChange={onPlanChange}>
        <SelectTrigger className="w-full sm:w-[180px]">
          <SelectValue placeholder="Filter by plan" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Plans</SelectItem>
          <SelectItem value="free">Free</SelectItem>
          <SelectItem value="pro">Pro</SelectItem>
          <SelectItem value="enterprise">Enterprise</SelectItem>
        </SelectContent>
      </Select>
      <Select value={statusFilter} onValueChange={onStatusChange}>
        <SelectTrigger className="w-full sm:w-[180px]">
          <SelectValue placeholder="Filter by status" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Statuses</SelectItem>
          <SelectItem value="active">Active</SelectItem>
          <SelectItem value="canceled">Canceled</SelectItem>
          <SelectItem value="past_due">Past Due</SelectItem>
          <SelectItem value="trialing">Trialing</SelectItem>
          <SelectItem value="incomplete">Incomplete</SelectItem>
          <SelectItem value="incomplete_expired">Incomplete Expired</SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
}
