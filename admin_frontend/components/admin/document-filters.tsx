"use client";

import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Search } from "lucide-react";

interface DocumentFiltersProps {
  statusFilter: string;
  onStatusChange: (status: string) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  fromDate?: string;
  onFromDateChange?: (date: string) => void;
  toDate?: string;
  onToDateChange?: (date: string) => void;
}

export function DocumentFilters({
  statusFilter,
  onStatusChange,
  searchQuery,
  onSearchChange,
  fromDate,
  onFromDateChange,
  toDate,
  onToDateChange,
}: DocumentFiltersProps) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search documents..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={statusFilter} onValueChange={onStatusChange}>
          <SelectTrigger className="w-full sm:w-[180px]">
            <SelectValue placeholder="Filter by status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            <SelectItem value="queued">Queued</SelectItem>
            <SelectItem value="processing">Processing</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
            <SelectItem value="failed">Failed</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {(onFromDateChange || onToDateChange) && (
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
          {onFromDateChange && (
            <div className="flex-1">
              <Label htmlFor="from-date">From Date</Label>
              <Input
                id="from-date"
                type="date"
                value={fromDate || ""}
                onChange={(e) => onFromDateChange(e.target.value)}
                className="mt-1"
              />
            </div>
          )}
          {onToDateChange && (
            <div className="flex-1">
              <Label htmlFor="to-date">To Date</Label>
              <Input
                id="to-date"
                type="date"
                value={toDate || ""}
                onChange={(e) => onToDateChange(e.target.value)}
                className="mt-1"
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
