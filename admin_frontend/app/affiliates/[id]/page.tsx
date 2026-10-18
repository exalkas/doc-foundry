"use client";

import { useParams } from "next/navigation";
import { AdminLayout } from "@/components/layout/admin-layout";
import { AffiliateDetailHeader } from "@/components/admin/affiliate-detail-header";
import { AffiliateStatsDisplay } from "@/components/admin/affiliate-stats";
import { useAffiliate } from "@/hooks/use-affiliate";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Spinner } from "@/components/ui/spinner";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ArrowLeft, DollarSign, CreditCard } from "lucide-react";

export default function AffiliateDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const { data: affiliate, isLoading, error } = useAffiliate(id);

  if (isLoading) {
    return (
      <AdminLayout>
        <div className="flex items-center justify-center py-12">
          <Spinner />
        </div>
      </AdminLayout>
    );
  }

  if (error || !affiliate) {
    return (
      <AdminLayout>
        <div className="space-y-6">
          <div className="flex items-center gap-4">
            <Link href="/affiliates">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Affiliates
              </Button>
            </Link>
          </div>
          <Card>
            <CardContent className="pt-6">
              <p className="text-center text-muted-foreground">
                Affiliate not found or error loading affiliate
              </p>
            </CardContent>
          </Card>
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Link href="/affiliates">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Affiliates
            </Button>
          </Link>
        </div>

        <AffiliateDetailHeader affiliate={affiliate} />

        {affiliate.stats && <AffiliateStatsDisplay stats={affiliate.stats} />}

        <Tabs defaultValue="overview" className="space-y-4">
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="commissions">
              <DollarSign className="mr-2 h-4 w-4" />
              Commissions
            </TabsTrigger>
            <TabsTrigger value="payouts">
              <CreditCard className="mr-2 h-4 w-4" />
              Payouts
            </TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Affiliate Information</CardTitle>
                <CardDescription>
                  Detailed information about this affiliate
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">
                      User ID
                    </p>
                    <p className="text-sm font-mono">{affiliate.user_id}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">
                      Status
                    </p>
                    <p className="text-sm capitalize">{affiliate.status}</p>
                  </div>
                  {affiliate.company_name && (
                    <div>
                      <p className="text-sm font-medium text-muted-foreground">
                        Company Name
                      </p>
                      <p className="text-sm">{affiliate.company_name}</p>
                    </div>
                  )}
                  {affiliate.website && (
                    <div>
                      <p className="text-sm font-medium text-muted-foreground">
                        Website
                      </p>
                      <p className="text-sm">
                        <a
                          href={affiliate.website}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-primary hover:underline"
                        >
                          {affiliate.website}
                        </a>
                      </p>
                    </div>
                  )}
                  {affiliate.payment_method_type && (
                    <div>
                      <p className="text-sm font-medium text-muted-foreground">
                        Payment Method
                      </p>
                      <p className="text-sm capitalize">
                        {affiliate.payment_method_type}
                      </p>
                    </div>
                  )}
                  {affiliate.country && (
                    <div>
                      <p className="text-sm font-medium text-muted-foreground">
                        Country
                      </p>
                      <p className="text-sm">{affiliate.country}</p>
                    </div>
                  )}
                  {affiliate.notes && (
                    <div className="md:col-span-2">
                      <p className="text-sm font-medium text-muted-foreground">
                        Notes
                      </p>
                      <p className="text-sm">{affiliate.notes}</p>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="commissions">
            <Card>
              <CardHeader>
                <CardTitle>Commissions</CardTitle>
                <CardDescription>
                  View all commissions for this affiliate
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Link href={`/affiliates/commissions?affiliate_id=${id}`}>
                  <Button variant="outline">
                    View All Commissions
                    <DollarSign className="ml-2 h-4 w-4" />
                  </Button>
                </Link>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="payouts">
            <Card>
              <CardHeader>
                <CardTitle>Payouts</CardTitle>
                <CardDescription>
                  View all payout requests for this affiliate
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Link href={`/affiliates/payouts?affiliate_id=${id}`}>
                  <Button variant="outline">
                    View All Payouts
                    <CreditCard className="ml-2 h-4 w-4" />
                  </Button>
                </Link>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </AdminLayout>
  );
}
