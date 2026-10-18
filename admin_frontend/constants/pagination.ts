/**
 * Pagination Configuration Constants
 *
 * Centralized constants for pagination to avoid magic numbers throughout the codebase.
 */

export const PAGINATION = {
  /** Default number of items per page */
  DEFAULT_PAGE_SIZE: 50,
  /** Maximum number of items per page */
  MAX_PAGE_SIZE: 100,
} as const;
