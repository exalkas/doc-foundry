import { z } from "zod";
import type {
  User,
  Workspace,
  Affiliate,
  Commission,
  Payout,
  UsageAnalytics,
  AbuseDetection,
} from "./types";
import {
  UserSchema,
  WorkspaceSchema,
  AffiliateSchema,
  CommissionSchema,
  PayoutSchema,
  UsageAnalyticsSchema,
  AbuseDetectionSchema,
  UsersArraySchema,
  WorkspacesArraySchema,
  AffiliatesArraySchema,
  CommissionsArraySchema,
  PayoutsArraySchema,
} from "./schemas";

/**
 * Validation utilities for runtime type checking
 */

export class ValidationError extends Error {
  constructor(message: string, public readonly errors: z.ZodError) {
    super(message);
    this.name = "ValidationError";
  }
}

/**
 * Validate a single workspace
 */
export function validateWorkspace(data: unknown): Workspace {
  try {
    return WorkspaceSchema.parse(data);
  } catch (error) {
    if (error instanceof z.ZodError) {
      throw new ValidationError("Invalid workspace data", error);
    }
    throw error;
  }
}

/**
 * Validate a single user
 */
export function validateUser(data: unknown): User {
  try {
    return UserSchema.parse(data);
  } catch (error) {
    if (error instanceof z.ZodError) {
      throw new ValidationError("Invalid user data", error);
    }
    throw error;
  }
}

/**
 * Validate a single affiliate
 */
export function validateAffiliate(data: unknown): Affiliate {
  try {
    return AffiliateSchema.parse(data);
  } catch (error) {
    if (error instanceof z.ZodError) {
      throw new ValidationError("Invalid affiliate data", error);
    }
    throw error;
  }
}

/**
 * Validate a single commission
 */
export function validateCommission(data: unknown): Commission {
  try {
    return CommissionSchema.parse(data);
  } catch (error) {
    if (error instanceof z.ZodError) {
      throw new ValidationError("Invalid commission data", error);
    }
    throw error;
  }
}

/**
 * Validate a single payout
 */
export function validatePayout(data: unknown): Payout {
  try {
    return PayoutSchema.parse(data);
  } catch (error) {
    if (error instanceof z.ZodError) {
      throw new ValidationError("Invalid payout data", error);
    }
    throw error;
  }
}

/**
 * Validate usage analytics
 */
export function validateUsageAnalytics(data: unknown): UsageAnalytics {
  try {
    return UsageAnalyticsSchema.parse(data);
  } catch (error) {
    if (error instanceof z.ZodError) {
      throw new ValidationError("Invalid usage analytics data", error);
    }
    throw error;
  }
}

/**
 * Validate abuse detection data
 */
export function validateAbuseDetection(data: unknown): AbuseDetection {
  try {
    return AbuseDetectionSchema.parse(data);
  } catch (error) {
    if (error instanceof z.ZodError) {
      throw new ValidationError("Invalid abuse detection data", error);
    }
    throw error;
  }
}

/**
 * Validate an array of workspaces
 */
export function validateWorkspaces(data: unknown): Workspace[] {
  try {
    return WorkspacesArraySchema.parse(data);
  } catch (error) {
    if (error instanceof z.ZodError) {
      throw new ValidationError("Invalid workspaces data", error);
    }
    throw error;
  }
}

/**
 * Validate an array of users
 */
export function validateUsers(data: unknown): User[] {
  try {
    return UsersArraySchema.parse(data);
  } catch (error) {
    if (error instanceof z.ZodError) {
      throw new ValidationError("Invalid users data", error);
    }
    throw error;
  }
}

/**
 * Validate an array of affiliates
 */
export function validateAffiliates(data: unknown): Affiliate[] {
  try {
    return AffiliatesArraySchema.parse(data);
  } catch (error) {
    if (error instanceof z.ZodError) {
      throw new ValidationError("Invalid affiliates data", error);
    }
    throw error;
  }
}

/**
 * Validate an array of commissions
 */
export function validateCommissions(data: unknown): Commission[] {
  try {
    return CommissionsArraySchema.parse(data);
  } catch (error) {
    if (error instanceof z.ZodError) {
      throw new ValidationError("Invalid commissions data", error);
    }
    throw error;
  }
}

/**
 * Validate an array of payouts
 */
export function validatePayouts(data: unknown): Payout[] {
  try {
    return PayoutsArraySchema.parse(data);
  } catch (error) {
    if (error instanceof z.ZodError) {
      throw new ValidationError("Invalid payouts data", error);
    }
    throw error;
  }
}

/**
 * Safe validation - returns result object instead of throwing
 */
export function safeValidate<T>(
  schema: z.ZodSchema<T>,
  data: unknown
): { success: true; data: T } | { success: false; error: z.ZodError } {
  const result = schema.safeParse(data);
  if (result.success) {
    return { success: true, data: result.data };
  }
  return { success: false, error: result.error };
}
