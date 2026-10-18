"use client";

import React from "react";
import Link from "next/link";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDate, getStatusColor } from "@/lib/utils";
import type { Coupon } from "@/lib/types";
import { ExternalLink } from "lucide-react";
import { LoadingSpinner } from "@/components/ui/loading";

interface CouponTableProps {
  coupons: Coupon[];
  isLoading?: boolean;
}

export const CouponTable = React.memo(function CouponTable({
  coupons,
  isLoading = false,
}: CouponTableProps) {
  if (isLoading) {
    return <LoadingSpinner message="Loading coupons..." />;
  }

  if (coupons.length === 0) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-sm text-muted-foreground">No coupons found</p>
      </div>
    );
  }

  const formatDiscount = (coupon: Coupon) => {
    if (coupon.discount_type === "percentage") {
      return `${coupon.discount_value}%`;
    }
    return `€${coupon.discount_value.toFixed(2)}`;
  };

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Code</TableHead>
            <TableHead>Discount</TableHead>
            <TableHead>Duration</TableHead>
            <TableHead>Affiliate</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Redemptions</TableHead>
            <TableHead>Expires</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {coupons.map((coupon) => (
            <TableRow
              key={coupon.id}
              className={coupon.status === "expired" ? "bg-muted/50" : ""}
            >
              <TableCell className="font-mono font-medium">
                {coupon.code}
              </TableCell>
              <TableCell>{formatDiscount(coupon)}</TableCell>
              <TableCell>
                {coupon.duration_type === "once"
                  ? "One-time"
                  : coupon.duration_type === "first_n_months"
                  ? `First ${coupon.duration_months || 0} months`
                  : "Until date"}
              </TableCell>
              <TableCell>
                {coupon.affiliate_name || "-"}
              </TableCell>
              <TableCell>
                <Badge variant={getStatusColor(coupon.status)}>
                  {coupon.status}
                </Badge>
              </TableCell>
              <TableCell>
                {coupon.redemption_count}
                {coupon.max_redemptions
                  ? ` / ${coupon.max_redemptions}`
                  : ""}
              </TableCell>
              <TableCell className="text-muted-foreground">
                {coupon.expires_at ? formatDate(coupon.expires_at) : "Never"}
              </TableCell>
              <TableCell className="text-right">
                <Link href={`/coupons/${coupon.id}`}>
                  <Button variant="ghost" size="sm">
                    View
                    <ExternalLink className="ml-2 h-3 w-3" />
                  </Button>
                </Link>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
});

