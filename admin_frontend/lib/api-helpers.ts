/**
 * API Helper Utilities
 *
 * Utility functions for handling API responses and data extraction.
 */

import type { PaginatedResponse } from "./types";

/**
 * Pagination metadata extracted from paginated responses
 */
export interface PaginationMeta {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

/**
 * Extract paginated data from API response
 *
 * Handles both paginated response format (`PaginatedResponse<T>`) and
 * legacy array format (`T[]`). Returns a consistent structure with items
 * and optional pagination metadata.
 *
 * @param data - API response data (either `T[]` or `PaginatedResponse<T>`)
 * @returns Object with `items` array and optional `pagination` metadata
 *
 * @example
 * ```ts
 * const { items, pagination } = extractPaginatedData(response);
 * if (pagination) {
 *   console.log(`Page ${pagination.page} of ${pagination.total_pages}`);
 * }
 * ```
 */
export function extractPaginatedData<T>(data: T[] | PaginatedResponse<T>): {
  items: T[];
  pagination: PaginationMeta | null;
} {
  if (data && typeof data === "object" && "items" in data) {
    const paginated = data as PaginatedResponse<T>;
    return {
      items: paginated.items,
      pagination: {
        total: paginated.total,
        page: paginated.page,
        page_size: paginated.page_size,
        total_pages: paginated.total_pages,
      },
    };
  }
  return { items: data as T[], pagination: null };
}
