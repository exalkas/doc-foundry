"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { getStatusColor, formatDate, formatDateTime } from "@/lib/utils";
import type { Affiliate } from "@/lib/types";
import { ApproveAffiliateModal } from "./approve-affiliate-modal";
import { RejectAffiliateModal } from "./reject-affiliate-modal";
import { BlockAffiliateModal } from "./block-affiliate-modal";
import { CheckCircle2, XCircle, Ban } from "lucide-react";

interface AffiliateDetailHeaderProps {
  affiliate: Affiliate;
}

export function AffiliateDetailHeader({
  affiliate,
}: AffiliateDetailHeaderProps) {
  const [approveModalOpen, setApproveModalOpen] = useState(false);
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [blockModalOpen, setBlockModalOpen] = useState(false);

  const isPending = affiliate.status === "pending";
  const isApproved = affiliate.status === "approved";
  const isBlocked = affiliate.status === "blocked";

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="space-y-2">
              <div className="flex items-center gap-3">
                <h2 className="text-2xl font-bold">{affiliate.user_email}</h2>
                <Badge variant={getStatusColor(affiliate.status)}>
                  {affiliate.status}
                </Badge>
              </div>
              <div className="space-y-1 text-sm text-muted-foreground">
                <p>
                  <span className="font-medium">ID:</span> {affiliate.id}
                </p>
                {affiliate.company_name && (
                  <p>
                    <span className="font-medium">Company:</span>{" "}
                    {affiliate.company_name}
                  </p>
                )}
                {affiliate.website && (
                  <p>
                    <span className="font-medium">Website:</span>{" "}
                    <a
                      href={affiliate.website}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline"
                    >
                      {affiliate.website}
                    </a>
                  </p>
                )}
                {affiliate.slug && (
                  <p>
                    <span className="font-medium">Slug:</span> {affiliate.slug}
                  </p>
                )}
                <p>
                  <span className="font-medium">Created:</span>{" "}
                  {formatDateTime(affiliate.created_at)}
                </p>
                {affiliate.updated_at && (
                  <p>
                    <span className="font-medium">Updated:</span>{" "}
                    {formatDateTime(affiliate.updated_at)}
                  </p>
                )}
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              {isPending && (
                <>
                  <Button
                    variant="default"
                    onClick={() => setApproveModalOpen(true)}
                  >
                    <CheckCircle2 className="mr-2 h-4 w-4" />
                    Approve
                  </Button>
                  <Button
                    variant="destructive"
                    onClick={() => setRejectModalOpen(true)}
                  >
                    <XCircle className="mr-2 h-4 w-4" />
                    Reject
                  </Button>
                </>
              )}
              {isApproved && (
                <Button
                  variant="destructive"
                  onClick={() => setBlockModalOpen(true)}
                >
                  <Ban className="mr-2 h-4 w-4" />
                  Block
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      <ApproveAffiliateModal
        affiliateId={affiliate.id}
        affiliateEmail={affiliate.user_email}
        open={approveModalOpen}
        onOpenChange={setApproveModalOpen}
      />

      <RejectAffiliateModal
        affiliateId={affiliate.id}
        affiliateEmail={affiliate.user_email}
        open={rejectModalOpen}
        onOpenChange={setRejectModalOpen}
      />

      <BlockAffiliateModal
        affiliateId={affiliate.id}
        affiliateEmail={affiliate.user_email}
        open={blockModalOpen}
        onOpenChange={setBlockModalOpen}
      />
    </div>
  );
}
