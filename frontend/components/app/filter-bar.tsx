"use client";

import * as React from "react";
import { Search, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

export interface FilterOption {
  label: string;
  value: string;
}

export interface FilterBarProps {
  searchValue?: string;
  onSearchChange?: (value: string) => void;
  searchPlaceholder?: string;
  sortBy?: string;
  onSortByChange?: (value: string) => void;
  sortOrder?: "asc" | "desc";
  onSortOrderChange?: (value: "asc" | "desc") => void;
  sortOptions?: FilterOption[];
  onClear?: () => void;
  className?: string;
  showSort?: boolean;
}

export function FilterBar({
  searchValue = "",
  onSearchChange,
  searchPlaceholder = "Search...",
  sortBy,
  onSortByChange,
  sortOrder = "desc",
  onSortOrderChange,
  sortOptions = [],
  onClear,
  className,
  showSort = true,
}: FilterBarProps) {
  const hasFilters =
    searchValue || (sortBy && sortBy !== "created_at") || sortOrder !== "desc";

  return (
    <div
      className={cn(
        "flex flex-col sm:flex-row gap-3 items-start sm:items-center",
        className
      )}
    >
      {/* Search Input */}
      <div className="relative flex-1 w-full sm:w-auto min-w-[200px]">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          type="text"
          placeholder={searchPlaceholder}
          value={searchValue}
          onChange={(e) => onSearchChange?.(e.target.value)}
          className="pl-9 pr-9 bg-background border-input text-foreground placeholder:text-muted-foreground dark:bg-background dark:border-input dark:text-foreground"
        />
        {searchValue && (
          <button
            type="button"
            onClick={() => onSearchChange?.("")}
            className="absolute right-3 top-1/2 transform -translate-y-1/2 text-muted-foreground hover:text-foreground"
            aria-label="Clear search"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Sort Controls */}
      {showSort && sortOptions.length > 0 && (
        <div className="flex gap-2 items-center">
          <Select
            value={sortBy || "created_at"}
            onValueChange={(value) => onSortByChange?.(value)}
          >
            <SelectTrigger className="w-[140px] bg-background border-input text-foreground dark:bg-background dark:border-input dark:text-foreground">
              <SelectValue placeholder="Sort by" />
            </SelectTrigger>
            <SelectContent>
              {sortOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={sortOrder}
            onValueChange={(value) =>
              onSortOrderChange?.(value as "asc" | "desc")
            }
          >
            <SelectTrigger className="w-[100px] bg-background border-input text-foreground dark:bg-background dark:border-input dark:text-foreground">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="desc">Desc</SelectItem>
              <SelectItem value="asc">Asc</SelectItem>
            </SelectContent>
          </Select>
        </div>
      )}

      {/* Clear Filters Button */}
      {hasFilters && onClear && (
        <Button
          variant="outline"
          size="sm"
          onClick={onClear}
          className="bg-background border-input text-foreground hover:bg-accent hover:text-accent-foreground dark:bg-background dark:border-input dark:text-foreground dark:hover:bg-accent dark:hover:text-accent-foreground"
        >
          <X className="mr-2 h-4 w-4" />
          Clear
        </Button>
      )}
    </div>
  );
}
