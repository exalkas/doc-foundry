"use client";

import { useState, useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  ArrowUpRight,
  ArrowDownRight,
  ExternalLink,
  Check,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { get, post } from "@/lib/api-client";
import { useToast } from "@/hooks/use-toast";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { HelpIcon } from "@/components/app/help-icon";
import { HelpText } from "@/components/app/help-text";
import { getHelpText, getHelpTextLong } from "@/lib/help-content";

interface UsageSummary {
  current_period: {
    documents_processed: number;
    pages_processed: number;
  };
  plan_limits: {
    documents_per_month: number;
    pages_per_month: number;
  };
  current_plan: string;
}

interface UsageHistory {
  date: string;
  documents_processed: number;
  pages_processed: number;
}

interface Plan {
  id: string;
  name: string;
  price: number;
  interval: string;
  features: string[];
}

interface Subscription {
  id: string;
  stripe_subscription_id: string;
  plan_id: string;
  status: string;
  current_period_start: string;
  current_period_end: string;
  cancel_at_period_end: boolean;
}

interface PaymentHistoryItem {
  id: string;
  amount: number;
  currency: string;
  status: string;
  created: string;
  description: string;
}

interface PaymentHistoryResponse {
  data: PaymentHistoryItem[];
  has_more: boolean;
  total: number;
  page: number;
  page_size: number;
}

export default function UsageBillingPage() {
  const [loadingCheckout, setLoadingCheckout] = useState<string | null>(null);
  const [downgradeDialogOpen, setDowngradeDialogOpen] = useState(false);
  const [pendingPlanId, setPendingPlanId] = useState<string | null>(null);
  const [couponCode, setCouponCode] = useState<string>("");
  const [validatingCoupon, setValidatingCoupon] = useState(false);
  const [couponInfo, setCouponInfo] = useState<{
    valid: boolean;
    discount_info?: any;
    error?: string;
  } | null>(null);
  const { toast } = useToast();
  const searchParams = useSearchParams();
  const router = useRouter();
  const queryClient = useQueryClient();

  // Handle success/cancel query parameters from Stripe redirect
  useEffect(() => {
    const success = searchParams.get("success");
    const canceled = searchParams.get("canceled");

    if (success === "true") {
      // Sync subscription from Stripe before showing success message
      // This ensures we have the latest data even if webhook hasn't arrived yet
      (async () => {
        try {
          await post("/api/billing/sync-subscription", {});
        } catch (error) {
          console.warn(
            "Failed to sync subscription, will rely on webhook:",
            error
          );
        }

        toast({
          variant: "default",
          title: "Payment successful",
          description: "Your subscription has been updated successfully.",
        });
        // Remove query parameter from URL
        router.replace("/app/settings/usage-billing");
        // Refetch subscription and usage data to show updated plan
        queryClient.invalidateQueries({
          queryKey: ["billing", "subscription"],
        });
        queryClient.invalidateQueries({ queryKey: ["usage"] });
      })();
    } else if (canceled === "true") {
      toast({
        variant: "default",
        title: "Checkout canceled",
        description: "Your subscription was not changed.",
      });
      // Remove query parameter from URL
      router.replace("/app/settings/usage-billing");
    }
  }, [searchParams, router, toast, queryClient]);

  const { data: usage } = useQuery<UsageSummary>({
    queryKey: ["usage"],
    queryFn: () => get("/api/usage/summary"),
  });

  const { data: plans } = useQuery<Plan[]>({
    queryKey: ["billing", "plans"],
    queryFn: () => get("/api/billing/plans"),
  });

  const { data: subscription } = useQuery<Subscription>({
    queryKey: ["billing", "subscription"],
    queryFn: () => get("/api/billing/subscription"),
  });

  const [paymentHistoryPage, setPaymentHistoryPage] = useState(1);
  const [paymentHistoryFromDate, setPaymentHistoryFromDate] =
    useState<string>("");
  const [paymentHistoryToDate, setPaymentHistoryToDate] = useState<string>("");

  const { data: paymentHistory } = useQuery<PaymentHistoryResponse>({
    queryKey: [
      "billing",
      "payment-history",
      paymentHistoryPage,
      paymentHistoryFromDate,
      paymentHistoryToDate,
    ],
    queryFn: () => {
      const params = new URLSearchParams({
        page: paymentHistoryPage.toString(),
        page_size: "10",
      });
      if (paymentHistoryFromDate)
        params.append("from_date", paymentHistoryFromDate);
      if (paymentHistoryToDate) params.append("to_date", paymentHistoryToDate);
      return get(`/api/billing/payment-history?${params.toString()}`);
    },
  });

  const { data: history } = useQuery<UsageHistory[]>({
    queryKey: ["usage", "history"],
    queryFn: () => get("/api/usage/daily"),
  });

  const documentsProcessed = usage?.current_period.documents_processed || 0;
  const pagesProcessed = usage?.current_period.pages_processed || 0;
  const documentsLimit = usage?.plan_limits.documents_per_month || 1000;
  const pagesLimit = usage?.plan_limits.pages_per_month || 1000;

  // Fix plan ID comparison - normalize to lowercase and handle "starter" -> "basic" mapping
  const normalizePlanId = (planId: string | undefined): string => {
    if (!planId) return "free";
    const normalized = planId.toLowerCase();
    // Map "starter" to "basic" for consistency
    return normalized === "starter" ? "basic" : normalized;
  };

  const currentPlanId = normalizePlanId(
    subscription?.plan_id || usage?.current_plan
  );

  const handleBillingPortal = async () => {
    if (!subscription || !subscription.stripe_subscription_id) {
      return;
    }
    try {
      const data = await post<{ url: string }>(
        "/api/billing/portal-session",
        {}
      );
      if (data.url) {
        // Stripe billing portal is an external URL, so we use window.location.href
        window.location.href = data.url;
      }
    } catch (error) {
      console.error("Failed to create portal session:", error);
    }
  };

  const handlePlanChange = async (planId: string) => {
    // Handle free plan
    if (planId === "free") {
      toast({
        variant: "destructive",
        title: "Free Plan",
        description:
          "Free plan is automatically assigned. Please contact support to downgrade.",
      });
      return;
    }

    // Handle enterprise plan
    if (planId === "enterprise") {
      toast({
        variant: "default",
        title: "Enterprise Plan",
        description:
          "Enterprise plan requires custom pricing. Please contact sales at sales@example.com",
      });
      return;
    }

    // Check if this is a downgrade
    const planHierarchy = ["free", "basic", "pro", "enterprise"];
    const currentIndex = planHierarchy.indexOf(currentPlanId);
    const planIndex = planHierarchy.indexOf(normalizePlanId(planId));

    if (planIndex < currentIndex && currentIndex >= 0) {
      // This is a downgrade - show confirmation dialog
      setPendingPlanId(planId);
      setDowngradeDialogOpen(true);
      return;
    }

    // Proceed with checkout for upgrades or same tier
    await proceedWithCheckout(planId);
  };

  const validateCoupon = async (code: string, planId: string) => {
    if (!code.trim()) {
      setCouponInfo(null);
      return;
    }

    setValidatingCoupon(true);
    try {
      const response = await post<{
        valid: boolean;
        error?: string;
        discount_info?: any;
      }>("/api/billing/validate-coupon", {
        code: code.trim(),
        plan_id: planId,
      });

      setCouponInfo(response);
      if (response.valid && response.discount_info) {
        toast({
          variant: "default",
          title: "Coupon applied",
          description: `Discount: ${response.discount_info.discount_type === "percentage" ? `${response.discount_info.discount_value}%` : `€${response.discount_info.discount_value}`}`,
        });
      } else if (response.error) {
        toast({
          variant: "destructive",
          title: "Invalid coupon",
          description: response.error,
        });
      }
    } catch (error: any) {
      const errorMessage =
        error?.message || error?.detail || "Failed to validate coupon";
      setCouponInfo({ valid: false, error: errorMessage });
      toast({
        variant: "destructive",
        title: "Error",
        description: errorMessage,
      });
    } finally {
      setValidatingCoupon(false);
    }
  };

  const proceedWithCheckout = async (planId: string, coupon: string | null = null) => {
    setLoadingCheckout(planId);
    try {
      const couponToUse = coupon || couponCode.trim();
      const couponParam = couponToUse ? `&coupon_code=${encodeURIComponent(couponToUse)}` : "";
      const data = await post<{ url: string; session_id: string }>(
        `/api/billing/checkout?plan_id=${planId}${couponParam}`,
        {}
      );
      if (data.url) {
        // Stripe checkout is an external URL, so we use window.location.href
        window.location.href = data.url;
      }
    } catch (error: any) {
      console.error("Failed to create checkout session:", error);
      // Extract error message properly - handle both ApiClientError and raw errors
      let errorMessage = "Failed to create checkout session";
      if (error) {
        if (typeof error === "string") {
          errorMessage = error;
        } else if (error.message) {
          errorMessage = error.message;
        } else if (error.details) {
          // If details is an object, extract the detail field (FastAPI format)
          if (typeof error.details === "object" && error.details.detail) {
            errorMessage = error.details.detail;
          } else if (typeof error.details === "string") {
            errorMessage = error.details;
          }
        } else if (error.detail) {
          errorMessage = error.detail;
        }
      }
      toast({
        variant: "destructive",
        title: "Error",
        description: errorMessage,
      });
      setLoadingCheckout(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Usage & billing</h1>
        <p className="text-muted-foreground">
          Monitor usage and manage your subscription
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Plan Summary */}
        <Card>
          <CardHeader>
            <CardTitle>Current Subscription</CardTitle>
            <div className="text-sm text-muted-foreground">
              {subscription ? (
                <>
                  {subscription.status === "active" ? (
                    <Badge className="bg-green-500">Active</Badge>
                  ) : subscription.status === "trialing" ? (
                    <Badge className="bg-blue-500">Trial</Badge>
                  ) : (
                    <Badge variant="destructive">{subscription.status}</Badge>
                  )}
                </>
              ) : (
                <Badge variant="outline">No active subscription</Badge>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-sm font-medium">Current plan</p>
              <p className="text-2xl font-bold capitalize">{currentPlanId}</p>
            </div>
            {subscription && (
              <>
                <div>
                  <p className="text-sm font-medium">Billing period</p>
                  <p className="text-sm text-muted-foreground">
                    {new Date(
                      subscription.current_period_start
                    ).toLocaleDateString()}{" "}
                    -{" "}
                    {new Date(
                      subscription.current_period_end
                    ).toLocaleDateString()}
                  </p>
                </div>
                {subscription.cancel_at_period_end && (
                  <div className="rounded-md bg-yellow-50 dark:bg-yellow-900/20 p-3">
                    <p className="text-sm text-yellow-800 dark:text-yellow-200">
                      Subscription will cancel at the end of the billing period
                    </p>
                  </div>
                )}
              </>
            )}
            <div>
              <div className="flex items-center gap-2">
                <p className="text-sm font-medium">Monthly quota</p>
                <HelpIcon content={getHelpText("billing.plan-limits")} />
              </div>
              <p className="text-sm text-muted-foreground">
                {documentsLimit.toLocaleString()} documents /{" "}
                {pagesLimit.toLocaleString()} pages
              </p>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <p className="text-sm font-medium">Used this period</p>
                <HelpIcon content={getHelpText("billing.usage-metrics")} />
              </div>
              <p className="text-sm text-muted-foreground">
                {documentsProcessed.toLocaleString()} documents /{" "}
                {pagesProcessed.toLocaleString()} pages
              </p>
            </div>
            <Button
              variant="outline"
              onClick={handleBillingPortal}
              disabled={!subscription || !subscription.stripe_subscription_id}
            >
              <ExternalLink className="mr-2 h-4 w-4" />
              Manage billing
            </Button>
          </CardContent>
        </Card>

        {/* Usage Chart */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <CardTitle>Usage over time</CardTitle>
              <HelpIcon content={getHelpText("billing.usage-metrics")} />
            </div>
          </CardHeader>
          <CardContent>
            {history && history.length > 0 ? (
              <div className="space-y-2">
                {history.slice(-7).map((day) => (
                  <div
                    key={day.date}
                    className="flex items-center justify-between text-sm"
                  >
                    <span>{new Date(day.date).toLocaleDateString()}</span>
                    <span className="text-muted-foreground">
                      {day.documents_processed} docs, {day.pages_processed}{" "}
                      pages
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No usage data yet</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Plan Comparison */}
      {plans && plans.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <CardTitle>Available Plans</CardTitle>
              <HelpIcon content={getHelpText("billing.plan-comparison")} />
            </div>
            <CardDescription>
              Choose the plan that fits your needs
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Coupon Input */}
            <div className="space-y-2">
              <Label htmlFor="coupon-code">Coupon Code (Optional)</Label>
              <div className="flex gap-2">
                <Input
                  id="coupon-code"
                  placeholder="Enter coupon code"
                  value={couponCode}
                  onChange={(e) => {
                    const newCode = e.target.value;
                    setCouponCode(newCode);
                    if (!newCode.trim()) {
                      setCouponInfo(null);
                    }
                  }}
                  onBlur={() => {
                    if (couponCode.trim()) {
                      const selectedPlan = plans.find((p) => normalizePlanId(p.id) !== "free" && normalizePlanId(p.id) !== "enterprise");
                      if (selectedPlan) {
                        validateCoupon(couponCode, selectedPlan.id);
                      }
                    }
                  }}
                  disabled={validatingCoupon}
                />
                {couponCode.trim() && (
                  <Button
                    variant="outline"
                    onClick={() => {
                      setCouponCode("");
                      setCouponInfo(null);
                    }}
                  >
                    Clear
                  </Button>
                )}
              </div>
              {couponInfo?.valid && couponInfo.discount_info && (
                <p className="text-sm text-green-600">
                  ✓ Coupon applied: {couponInfo.discount_info.discount_type === "percentage"
                    ? `${couponInfo.discount_info.discount_value}% off`
                    : `€${couponInfo.discount_info.discount_value} off`}
                  {couponInfo.discount_info.duration_type === "first_n_months" &&
                    couponInfo.discount_info.duration_months &&
                    ` for first ${couponInfo.discount_info.duration_months} months`}
                </p>
              )}
              {couponInfo && !couponInfo.valid && couponInfo.error && (
                <p className="text-sm text-red-600">{couponInfo.error}</p>
              )}
            </div>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              {plans.map((plan) => {
                // Normalize plan IDs for comparison
                const normalizedPlanId = normalizePlanId(plan.id);
                const isCurrentPlan = normalizedPlanId === currentPlanId;

                // Determine if this is an upgrade or downgrade
                const planHierarchy = ["free", "basic", "pro", "enterprise"];
                const currentIndex = planHierarchy.indexOf(currentPlanId);
                const planIndex = planHierarchy.indexOf(normalizedPlanId);

                const isUpgrade = planIndex > currentIndex && currentIndex >= 0;
                const isDowngrade = planIndex < currentIndex && planIndex >= 0;

                return (
                  <Card
                    key={plan.id}
                    className={`flex flex-col ${
                      isCurrentPlan ? "border-primary" : ""
                    }`}
                  >
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <CardTitle className="capitalize">
                          {plan.name}
                        </CardTitle>
                        {isCurrentPlan && <Badge>Current</Badge>}
                      </div>
                      <CardDescription>
                        {plan.price === 0 && plan.id === "enterprise"
                          ? "Custom pricing"
                          : `$${plan.price}/${plan.interval}`}
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="flex flex-col flex-1 space-y-4">
                      <ul className="space-y-2 flex-1">
                        {plan.features.map((feature, idx) => (
                          <li key={idx} className="flex items-start text-sm">
                            <Check className="mr-2 h-4 w-4 text-primary flex-shrink-0 mt-0.5" />
                            <span>{feature}</span>
                          </li>
                        ))}
                      </ul>
                      {!isCurrentPlan && (
                        <Button
                          className="w-full mt-auto"
                          variant={isUpgrade ? "default" : "outline"}
                          onClick={async () => {
                            // If coupon code is entered but not validated, validate it first
                            if (couponCode.trim() && !couponInfo?.valid) {
                              await validateCoupon(couponCode, plan.id);
                              // After validation, check if it's valid before proceeding
                              // Note: couponInfo state might not be updated immediately, so we'll proceed anyway
                              // The backend will validate again
                            }
                            handlePlanChange(plan.id);
                          }}
                          isLoading={loadingCheckout === plan.id}
                        >
                          {plan.id === "enterprise" ? (
                            "Contact Sales"
                          ) : plan.id === "free" ? (
                            "Select Plan"
                          ) : isUpgrade ? (
                            <>
                              <ArrowUpRight className="mr-2 h-4 w-4" />
                              Upgrade
                            </>
                          ) : isDowngrade ? (
                            <>
                              <ArrowDownRight className="mr-2 h-4 w-4" />
                              Downgrade
                            </>
                          ) : (
                            "Select Plan"
                          )}
                        </Button>
                      )}
                    </CardContent>
                  </Card>
                );
              })}
            </div>
            <div className="mt-6">
              <HelpText
                title="Understanding plans and billing"
                content={
                  <>
                    <p className="mb-2">
                      {getHelpTextLong("billing.plan-comparison")}
                    </p>
                    <p className="mb-2">
                      {getHelpTextLong("billing.soft-hard-limits")}
                    </p>
                    <p>{getHelpTextLong("billing.overage")}</p>
                  </>
                }
              />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Payment History */}
      {paymentHistory && (
        <Card>
          <CardHeader>
            <CardTitle>Payment History</CardTitle>
            <CardDescription>Recent payments and charges</CardDescription>
          </CardHeader>
          <CardContent>
            {/* Date Filters */}
            <div className="flex gap-4 mb-4">
              <div className="flex-1">
                <label className="text-sm font-medium mb-1 block">
                  From Date
                </label>
                <input
                  type="date"
                  value={paymentHistoryFromDate}
                  onChange={(e) => {
                    setPaymentHistoryFromDate(e.target.value);
                    setPaymentHistoryPage(1);
                  }}
                  className="w-full px-3 py-2 border rounded-md"
                />
              </div>
              <div className="flex-1">
                <label className="text-sm font-medium mb-1 block">
                  To Date
                </label>
                <input
                  type="date"
                  value={paymentHistoryToDate}
                  onChange={(e) => {
                    setPaymentHistoryToDate(e.target.value);
                    setPaymentHistoryPage(1);
                  }}
                  className="w-full px-3 py-2 border rounded-md"
                />
              </div>
              {(paymentHistoryFromDate || paymentHistoryToDate) && (
                <div className="flex items-end">
                  <Button
                    variant="outline"
                    onClick={() => {
                      setPaymentHistoryFromDate("");
                      setPaymentHistoryToDate("");
                      setPaymentHistoryPage(1);
                    }}
                  >
                    Clear Filters
                  </Button>
                </div>
              )}
            </div>

            {paymentHistory.data.length > 0 ? (
              <>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead>Amount</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {paymentHistory.data.map((payment) => (
                      <TableRow key={payment.id}>
                        <TableCell>
                          {new Date(payment.created).toLocaleDateString()}
                        </TableCell>
                        <TableCell>
                          {payment.description || "Subscription"}
                        </TableCell>
                        <TableCell>
                          ${payment.amount.toFixed(2)}{" "}
                          {payment.currency.toUpperCase()}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              payment.status === "succeeded"
                                ? "default"
                                : "destructive"
                            }
                          >
                            {payment.status}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>

                {/* Pagination */}
                <div className="flex items-center justify-between mt-4">
                  <div className="text-sm text-muted-foreground">
                    Showing {paymentHistory.data.length} of{" "}
                    {paymentHistory.total} payments
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        setPaymentHistoryPage((p) => Math.max(1, p - 1))
                      }
                      disabled={paymentHistoryPage === 1}
                    >
                      <ChevronLeft className="h-4 w-4" />
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPaymentHistoryPage((p) => p + 1)}
                      disabled={!paymentHistory.has_more}
                    >
                      Next
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </>
            ) : (
              <p className="text-sm text-muted-foreground py-4">
                No payment history found for the selected date range.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Downgrade Confirmation Dialog */}
      <AlertDialog
        open={downgradeDialogOpen}
        onOpenChange={setDowngradeDialogOpen}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirm Plan Downgrade</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to downgrade your plan? This may result in:
              <ul className="list-disc list-inside mt-2 space-y-1">
                <li>Reduced monthly quotas and limits</li>
                <li>Loss of premium features</li>
                <li>Potential data loss if you exceed the new plan limits</li>
              </ul>
              Changes will take effect at the end of your current billing
              period.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (pendingPlanId) {
                  setDowngradeDialogOpen(false);
                  proceedWithCheckout(pendingPlanId);
                  setPendingPlanId(null);
                }
              }}
            >
              Confirm Downgrade
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
