"use client";

import { useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Spinner } from "@/components/ui/spinner";
import {
  Copy,
  ExternalLink,
  Plus,
  TrendingUp,
  Users,
  DollarSign,
  Link as LinkIcon,
  CheckCircle2,
  Clock,
  XCircle,
} from "lucide-react";
import {
  useAffiliate,
  useAffiliateStats,
  useAffiliateLinks,
  useCommissions,
  useReferredCustomers,
  usePayouts,
  useApplyAffiliate,
  useCreateAffiliateLink,
  useRequestPayout,
} from "@/hooks/use-affiliate";
import { useToast } from "@/hooks/use-toast";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  process.env.BACKEND_URL ||
  "http://localhost:8000";

export default function AffiliatesPage() {
  const { toast } = useToast();
  const [applyDialogOpen, setApplyDialogOpen] = useState(false);
  const [createLinkDialogOpen, setCreateLinkDialogOpen] = useState(false);
  const [payoutDialogOpen, setPayoutDialogOpen] = useState(false);
  const [applyFormData, setApplyFormData] = useState({
    company_name: "",
    website: "",
    country: "",
  });
  const [linkFormData, setLinkFormData] = useState({
    destination_url: "/",
    campaign_id: "",
  });
  const [payoutFormData, setPayoutFormData] = useState({
    amount: 0,
    currency: "EUR",
  });

  const {
    data: affiliate,
    isLoading: affiliateLoading,
    error: affiliateError,
  } = useAffiliate();

  const isAffiliateApproved = affiliate?.status === "approved";

  const { data: stats, isLoading: statsLoading } =
    useAffiliateStats(isAffiliateApproved);

  const { data: links, isLoading: linksLoading } =
    useAffiliateLinks(isAffiliateApproved);

  const { data: commissions, isLoading: commissionsLoading } = useCommissions(
    undefined,
    isAffiliateApproved
  );

  const { data: customers, isLoading: customersLoading } =
    useReferredCustomers(isAffiliateApproved);

  const { data: payouts, isLoading: payoutsLoading } =
    usePayouts(isAffiliateApproved);

  const applyMutation = useApplyAffiliate();
  const createLinkMutation = useCreateAffiliateLink();
  const requestPayoutMutation = useRequestPayout();

  const handleApply = async () => {
    try {
      await applyMutation.mutateAsync(applyFormData);
      setApplyDialogOpen(false);
      setApplyFormData({ company_name: "", website: "", country: "" });
      toast({
        variant: "success",
        title: "Application submitted",
        description:
          "Your affiliate application has been submitted for review.",
      });
    } catch (error: any) {
      toast({
        variant: "destructive",
        title: "Error",
        description: error?.message || "Failed to submit application",
      });
    }
  };

  const handleCreateLink = async () => {
    try {
      await createLinkMutation.mutateAsync(linkFormData);
      setCreateLinkDialogOpen(false);
      setLinkFormData({ destination_url: "/", campaign_id: "" });
      toast({
        variant: "success",
        title: "Link created",
        description: "Your affiliate link has been created successfully.",
      });
    } catch (error: any) {
      toast({
        variant: "destructive",
        title: "Error",
        description: error?.message || "Failed to create link",
      });
    }
  };

  const handleRequestPayout = async () => {
    try {
      await requestPayoutMutation.mutateAsync(payoutFormData);
      setPayoutDialogOpen(false);
      setPayoutFormData({ amount: 0, currency: "EUR" });
      toast({
        variant: "success",
        title: "Payout requested",
        description: "Your payout request has been submitted.",
      });
    } catch (error: any) {
      toast({
        variant: "destructive",
        title: "Error",
        description: error?.message || "Failed to request payout",
      });
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast({
      variant: "success",
      title: "Copied",
      description: "Link copied to clipboard",
    });
  };

  const getStatusBadge = (status: string) => {
    const variants: Record<string, "default" | "secondary" | "destructive"> = {
      approved: "default",
      pending: "secondary",
      rejected: "destructive",
      blocked: "destructive",
    };
    return <Badge variant={variants[status] || "secondary"}>{status}</Badge>;
  };

  const formatCurrency = (amount: number, currency: string = "EUR") => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  const getAffiliateUrl = (slug: string) => {
    const baseUrl =
      typeof window !== "undefined"
        ? window.location.origin
        : BACKEND_URL.replace("/api", "");
    return `${baseUrl}/r/${slug}`;
  };

  // Show loading state
  if (affiliateLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Spinner />
      </div>
    );
  }

  // Show apply dialog if user hasn't registered
  if (affiliateError && (affiliateError as any)?.status === 404) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            Affiliate Program
          </h1>
          <p className="text-muted-foreground">
            Earn commissions by referring customers to our platform
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Join Our Affiliate Program</CardTitle>
            <CardDescription>
              Apply to become an affiliate and start earning commissions
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                As an affiliate, you can earn commissions for every customer you
                refer. Apply now to get started!
              </p>
              <Button onClick={() => setApplyDialogOpen(true)}>
                Apply to Become an Affiliate
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Apply Dialog */}
        <Dialog open={applyDialogOpen} onOpenChange={setApplyDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Apply to Become an Affiliate</DialogTitle>
              <DialogDescription>
                Fill out the form below to apply for our affiliate program
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="company_name">Company Name (Optional)</Label>
                <Input
                  id="company_name"
                  value={applyFormData.company_name}
                  onChange={(e) =>
                    setApplyFormData({
                      ...applyFormData,
                      company_name: e.target.value,
                    })
                  }
                  placeholder="Your company name"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="website">Website (Optional)</Label>
                <Input
                  id="website"
                  type="url"
                  value={applyFormData.website}
                  onChange={(e) =>
                    setApplyFormData({
                      ...applyFormData,
                      website: e.target.value,
                    })
                  }
                  placeholder="https://example.com"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="country">Country (Optional)</Label>
                <Input
                  id="country"
                  value={applyFormData.country}
                  onChange={(e) =>
                    setApplyFormData({
                      ...applyFormData,
                      country: e.target.value,
                    })
                  }
                  placeholder="Your country"
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setApplyDialogOpen(false)}
              >
                Cancel
              </Button>
              <Button onClick={handleApply} disabled={applyMutation.isPending}>
                {applyMutation.isPending
                  ? "Submitting..."
                  : "Submit Application"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    );
  }

  // Show affiliate portal
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Affiliate Program</h1>
        <p className="text-muted-foreground">
          Manage your affiliate account, links, and earnings
        </p>
      </div>

      {/* Status Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Account Status</CardTitle>
              <CardDescription>
                Your affiliate account information
              </CardDescription>
            </div>
            {getStatusBadge(affiliate?.status || "pending")}
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-muted-foreground">Affiliate Slug</p>
              <p className="font-mono text-sm">{affiliate?.slug}</p>
            </div>
            {affiliate?.company_name && (
              <div>
                <p className="text-sm text-muted-foreground">Company</p>
                <p className="text-sm">{affiliate.company_name}</p>
              </div>
            )}
          </div>
          {affiliate?.status === "pending" && (
            <div className="mt-4 p-4 bg-yellow-50 dark:bg-yellow-900/20 rounded-md">
              <p className="text-sm text-yellow-800 dark:text-yellow-200">
                Your application is pending review. You will be notified once it
                has been approved.
              </p>
            </div>
          )}
          {affiliate?.status === "rejected" && (
            <div className="mt-4 p-4 bg-red-50 dark:bg-red-900/20 rounded-md">
              <p className="text-sm text-red-800 dark:text-red-200">
                Your application has been rejected. Please contact support for
                more information.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {affiliate?.status === "approved" && (
        <>
          {/* Stats Cards */}
          {stats && (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Total Clicks</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {stats.total_clicks.toLocaleString()}
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Total Signups</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {stats.total_signups.toLocaleString()}
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Paying Customers</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {stats.paying_customers.toLocaleString()}
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Total Earned</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {formatCurrency(stats.total_earned, "EUR")}
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          <Tabs defaultValue="links" className="space-y-4">
            <TabsList>
              <TabsTrigger value="links">Links</TabsTrigger>
              <TabsTrigger value="commissions">Commissions</TabsTrigger>
              <TabsTrigger value="customers">Customers</TabsTrigger>
              <TabsTrigger value="payouts">Payouts</TabsTrigger>
            </TabsList>

            {/* Links Tab */}
            <TabsContent value="links" className="space-y-4">
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle>Affiliate Links</CardTitle>
                      <CardDescription>
                        Create and manage your affiliate links
                      </CardDescription>
                    </div>
                    <Button onClick={() => setCreateLinkDialogOpen(true)}>
                      <Plus className="mr-2 h-4 w-4" />
                      Create Link
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  {linksLoading ? (
                    <div className="flex items-center justify-center py-8">
                      <Spinner />
                    </div>
                  ) : links && links.length > 0 ? (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Link</TableHead>
                          <TableHead>Destination</TableHead>
                          <TableHead>Campaign</TableHead>
                          <TableHead>Created</TableHead>
                          <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {links.map((link) => {
                          const fullUrl = getAffiliateUrl(link.slug);
                          return (
                            <TableRow key={link.id}>
                              <TableCell className="font-mono text-sm">
                                {fullUrl}
                              </TableCell>
                              <TableCell>{link.destination_url}</TableCell>
                              <TableCell>{link.campaign_id || "-"}</TableCell>
                              <TableCell>
                                {formatDate(link.created_at)}
                              </TableCell>
                              <TableCell className="text-right">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => copyToClipboard(fullUrl)}
                                >
                                  <Copy className="h-4 w-4" />
                                </Button>
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  ) : (
                    <div className="text-center py-8">
                      <p className="text-sm text-muted-foreground">
                        No affiliate links yet. Create your first link to get
                        started!
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* Commissions Tab */}
            <TabsContent value="commissions" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Commissions</CardTitle>
                  <CardDescription>
                    Track your commission earnings
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {commissionsLoading ? (
                    <div className="flex items-center justify-center py-8">
                      <Spinner />
                    </div>
                  ) : commissions && commissions.length > 0 ? (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Event Type</TableHead>
                          <TableHead>Amount</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Date</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {commissions.map((commission) => (
                          <TableRow key={commission.id}>
                            <TableCell className="capitalize">
                              {commission.event_type.replace("_", " ")}
                            </TableCell>
                            <TableCell>
                              {formatCurrency(
                                commission.amount,
                                commission.currency
                              )}
                            </TableCell>
                            <TableCell>
                              {getStatusBadge(commission.status)}
                            </TableCell>
                            <TableCell>
                              {formatDate(commission.event_date)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  ) : (
                    <div className="text-center py-8">
                      <p className="text-sm text-muted-foreground">
                        No commissions yet
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* Customers Tab */}
            <TabsContent value="customers" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Referred Customers</CardTitle>
                  <CardDescription>
                    Customers you have referred to our platform
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {customersLoading ? (
                    <div className="flex items-center justify-center py-8">
                      <Spinner />
                    </div>
                  ) : customers && customers.length > 0 ? (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Email</TableHead>
                          <TableHead>Plan</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Signup Date</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {customers.map((customer) => (
                          <TableRow key={customer.customer_id}>
                            <TableCell>{customer.email}</TableCell>
                            <TableCell>{customer.plan_id || "-"}</TableCell>
                            <TableCell>
                              {customer.status ? (
                                <Badge variant="default">
                                  {customer.status}
                                </Badge>
                              ) : (
                                "-"
                              )}
                            </TableCell>
                            <TableCell>
                              {formatDate(customer.signup_date)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  ) : (
                    <div className="text-center py-8">
                      <p className="text-sm text-muted-foreground">
                        No referred customers yet
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* Payouts Tab */}
            <TabsContent value="payouts" className="space-y-4">
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle>Payouts</CardTitle>
                      <CardDescription>
                        Request and track your payouts
                      </CardDescription>
                    </div>
                    {stats && stats.cleared_earned > 0 && (
                      <Button onClick={() => setPayoutDialogOpen(true)}>
                        Request Payout
                      </Button>
                    )}
                  </div>
                </CardHeader>
                <CardContent>
                  {payoutsLoading ? (
                    <div className="flex items-center justify-center py-8">
                      <Spinner />
                    </div>
                  ) : payouts && payouts.length > 0 ? (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Amount</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Requested</TableHead>
                          <TableHead>Processed</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {payouts.map((payout) => (
                          <TableRow key={payout.id}>
                            <TableCell>
                              {formatCurrency(payout.amount, payout.currency)}
                            </TableCell>
                            <TableCell>
                              {getStatusBadge(payout.status)}
                            </TableCell>
                            <TableCell>
                              {formatDate(payout.requested_at)}
                            </TableCell>
                            <TableCell>
                              {payout.processed_at
                                ? formatDate(payout.processed_at)
                                : "-"}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  ) : (
                    <div className="text-center py-8">
                      <p className="text-sm text-muted-foreground">
                        No payout requests yet
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </>
      )}

      {/* Create Link Dialog */}
      <Dialog
        open={createLinkDialogOpen}
        onOpenChange={setCreateLinkDialogOpen}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Affiliate Link</DialogTitle>
            <DialogDescription>
              Create a new affiliate link to share with your audience
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="destination_url">Destination URL</Label>
              <Input
                id="destination_url"
                value={linkFormData.destination_url}
                onChange={(e) =>
                  setLinkFormData({
                    ...linkFormData,
                    destination_url: e.target.value,
                  })
                }
                placeholder="/"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="campaign_id">Campaign ID (Optional)</Label>
              <Input
                id="campaign_id"
                value={linkFormData.campaign_id}
                onChange={(e) =>
                  setLinkFormData({
                    ...linkFormData,
                    campaign_id: e.target.value,
                  })
                }
                placeholder="campaign-name"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setCreateLinkDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreateLink}
              disabled={createLinkMutation.isPending}
            >
              {createLinkMutation.isPending ? "Creating..." : "Create Link"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Request Payout Dialog */}
      <Dialog open={payoutDialogOpen} onOpenChange={setPayoutDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Request Payout</DialogTitle>
            <DialogDescription>
              Request a payout from your cleared earnings
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            {stats && (
              <div className="p-4 bg-muted rounded-md">
                <p className="text-sm text-muted-foreground">
                  Available Balance
                </p>
                <p className="text-2xl font-bold">
                  {formatCurrency(stats.cleared_earned, "EUR")}
                </p>
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="payout_amount">Amount</Label>
              <Input
                id="payout_amount"
                type="number"
                step="0.01"
                min="0"
                value={payoutFormData.amount}
                onChange={(e) =>
                  setPayoutFormData({
                    ...payoutFormData,
                    amount: parseFloat(e.target.value) || 0,
                  })
                }
                placeholder="0.00"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="payout_currency">Currency</Label>
              <Input
                id="payout_currency"
                value={payoutFormData.currency}
                onChange={(e) =>
                  setPayoutFormData({
                    ...payoutFormData,
                    currency: e.target.value,
                  })
                }
                placeholder="EUR"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setPayoutDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleRequestPayout}
              disabled={requestPayoutMutation.isPending}
            >
              {requestPayoutMutation.isPending
                ? "Requesting..."
                : "Request Payout"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
