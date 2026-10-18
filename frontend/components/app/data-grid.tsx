"use client";

import * as React from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";

export interface Column<T> {
  key: string;
  header: string;
  cell: (item: T) => React.ReactNode;
  sortable?: boolean;
  className?: string;
}

export interface DataGridProps<T> {
  data: T[];
  columns: Column<T>[];
  isLoading?: boolean;
  emptyMessage?: string;
  onRowClick?: (item: T) => void;
  className?: string;
  rowClassName?: (item: T) => string;
}

export function DataGrid<T extends { id?: string }>({
  data,
  columns,
  isLoading = false,
  emptyMessage = "No items found",
  onRowClick,
  className,
  rowClassName,
}: DataGridProps<T>) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner />
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center py-12 text-muted-foreground">
        <p>{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className={cn("rounded-md border bg-background", className)}>
      <Table>
        <TableHeader>
          <TableRow className="bg-muted/50 hover:bg-muted/50 dark:bg-muted/50 dark:hover:bg-muted/50">
            {columns.map((column) => (
              <TableHead
                key={column.key}
                className={cn("text-foreground font-medium", column.className)}
              >
                {column.header}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((item, index) => (
            <TableRow
              key={item.id || index}
              onClick={() => onRowClick?.(item)}
              className={cn(
                "cursor-pointer hover:bg-muted/50 dark:hover:bg-muted/50",
                rowClassName?.(item)
              )}
            >
              {columns.map((column) => (
                <TableCell
                  key={column.key}
                  className={cn("text-foreground", column.className)}
                >
                  {column.cell(item)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
