"use client";

import React from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface CouponFiltersProps {
  statusFilter: string;
  onStatusChange: (status: string) => void;
}

export const CouponFilters = React.memo(function CouponFilters({
  statusFilter,
  onStatusChange,
}: CouponFiltersProps) {
  return (
    <div className="flex items-center gap-4">
      <Select value={statusFilter} onValueChange={onStatusChange}>
        <SelectTrigger className="w-[180px]">
          <SelectValue placeholder="Filter by status" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Status</SelectItem>
          <SelectItem value="active">Active</SelectItem>
          <SelectItem value="paused">Paused</SelectItem>
          <SelectItem value="expired">Expired</SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
});
