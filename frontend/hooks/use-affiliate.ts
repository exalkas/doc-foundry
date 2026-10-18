"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { get, post, patch } from "@/lib/api-client";
import type {
  Affiliate,
  AffiliateStats,
  AffiliateLink,
  Commission,
  Customer,
  Payout,
} from "@/lib/types";

// Get current user's affiliate account
export function useAffiliate() {
  return useQuery<Affiliate>({
    queryKey: ["affiliate", "me"],
    queryFn: () => get<Affiliate>("/api/affiliates/me"),
    retry: (failureCount, error: any) => {
      // Don't retry on 404 (user hasn't registered as affiliate)
      if (error?.status === 404) {
        return false;
      }
      return failureCount < 2;
    },
    staleTime: 30 * 1000, // 30 seconds
  });
}

// Get affiliate stats
export function useAffiliateStats(enabled: boolean = true) {
  return useQuery<AffiliateStats>({
    queryKey: ["affiliate", "stats"],
    queryFn: () => get<AffiliateStats>("/api/affiliates/stats"),
    enabled,
    staleTime: 30 * 1000,
  });
}

// Get affiliate links
export function useAffiliateLinks(enabled: boolean = true) {
  return useQuery<AffiliateLink[]>({
    queryKey: ["affiliate", "links"],
    queryFn: () => get<AffiliateLink[]>("/api/affiliates/links"),
    enabled,
    staleTime: 30 * 1000,
  });
}

// Get commissions
export function useCommissions(status?: string, enabled: boolean = true) {
  return useQuery<Commission[]>({
    queryKey: ["affiliate", "commissions", status],
    queryFn: () => {
      const url = status
        ? `/api/affiliates/commissions?status=${status}`
        : "/api/affiliates/commissions";
      return get<Commission[]>(url);
    },
    enabled,
    staleTime: 30 * 1000,
  });
}

// Get referred customers
export function useReferredCustomers(enabled: boolean = true) {
  return useQuery<Customer[]>({
    queryKey: ["affiliate", "customers"],
    queryFn: () => get<Customer[]>("/api/affiliates/customers"),
    enabled,
    staleTime: 30 * 1000,
  });
}

// Get payouts
export function usePayouts(enabled: boolean = true) {
  return useQuery<Payout[]>({
    queryKey: ["affiliate", "payouts"],
    queryFn: () => get<Payout[]>("/api/affiliates/payouts"),
    enabled,
    staleTime: 30 * 1000,
  });
}

// Apply to become affiliate
export function useApplyAffiliate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      company_name?: string;
      website?: string;
      country?: string;
    }) => post<Affiliate>("/api/affiliates/apply", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["affiliate"] });
    },
  });
}

// Create affiliate link
export function useCreateAffiliateLink() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: { destination_url?: string; campaign_id?: string }) =>
      post<AffiliateLink>("/api/affiliates/links", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["affiliate", "links"] });
    },
  });
}

// Request payout
export function useRequestPayout() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: { amount: number; currency?: string }) =>
      post<Payout>("/api/affiliates/payout-request", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["affiliate", "payouts"] });
      queryClient.invalidateQueries({ queryKey: ["affiliate", "stats"] });
    },
  });
}

// Update affiliate profile
export function useUpdateAffiliateProfile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      company_name?: string;
      website?: string;
      payment_method_type?: string;
      payment_details?: string;
      country?: string;
      tax_id?: string;
    }) => patch<Affiliate>("/api/affiliates/profile", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["affiliate"] });
    },
  });
}
