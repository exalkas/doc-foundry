"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
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
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Send, Eye, RotateCcw } from "lucide-react";
import { get, post } from "@/lib/api-client";
import type { WebhookConfig, WebhookDelivery } from "@/lib/types";
import { useToast } from "@/hooks/use-toast";
import { getSuccessMessage, getErrorMessage } from "@/lib/notifications";
import { HelpIcon } from "@/components/app/help-icon";
import { HelpText } from "@/components/app/help-text";
import { getHelpText, getHelpTextLong } from "@/lib/help-content";

const availableEvents = [
  "document.succeeded",
  "document.failed",
  "usage.threshold_80",
  "usage.threshold_100",
];

export default function WebhooksPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [configData, setConfigData] = useState({
    target_url: "",
    secret: "",
    events: [] as string[],
    retry_policy: "exponential_backoff",
    enabled: true,
  });

  const { data: webhookConfig } = useQuery<WebhookConfig>({
    queryKey: ["webhook-config"],
    queryFn: () => get("/api/webhooks"),
  });

  const { data: deliveries } = useQuery<WebhookDelivery[]>({
    queryKey: ["webhook-deliveries"],
    queryFn: () => get("/api/webhooks/deliveries"),
  });

  const saveMutation = useMutation({
    mutationFn: (data: any) =>
      post<{ webhook: WebhookConfig }>("/api/webhooks", data),
    onSuccess: () => {
      toast({
        variant: "success",
        title: getSuccessMessage("create", "webhook"),
        description: "Webhook configuration saved successfully",
      });
      queryClient.invalidateQueries({ queryKey: ["webhook-config"] });
      setConfigData({
        target_url: "",
        secret: "",
        events: [],
        retry_policy: "exponential_backoff",
        enabled: true,
      });
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Error",
        description: getErrorMessage(error, "create", "webhook"),
      });
    },
  });

  const testMutation = useMutation({
    mutationFn: () =>
      post("/api/webhooks/test", { webhook_id: webhookConfig?.id }),
    onSuccess: () => {
      toast({
        variant: "success",
        title: "Webhook test sent",
        description: "Test webhook has been sent successfully",
      });
      queryClient.invalidateQueries({ queryKey: ["webhook-deliveries"] });
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Error",
        description: getErrorMessage(error, "test", "webhook"),
      });
    },
  });

  const toggleEvent = (event: string) => {
    setConfigData({
      ...configData,
      events: configData.events.includes(event)
        ? configData.events.filter((e) => e !== event)
        : [...configData.events, event],
    });
  };

  const handleSave = () => {
    saveMutation.mutate(configData);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Webhooks</h1>
        <p className="text-muted-foreground">
          Get notified when documents finish processing or when key events
          happen
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Configuration */}
        <Card>
          <CardHeader>
            <CardTitle>Configuration</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Label htmlFor="target-url">Target URL</Label>
                <HelpIcon content={getHelpText("webhooks.target-url")} />
              </div>
              <Input
                id="target-url"
                value={configData.target_url}
                onChange={(e) =>
                  setConfigData({ ...configData, target_url: e.target.value })
                }
                placeholder="https://your-app.com/webhooks/docfoundry"
              />
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Label htmlFor="secret">Signing secret</Label>
                <HelpIcon content={getHelpText("webhooks.signing-secret")} />
              </div>
              <Input
                id="secret"
                type="password"
                value={configData.secret}
                onChange={(e) =>
                  setConfigData({ ...configData, secret: e.target.value })
                }
                placeholder="Used to verify signatures (HMAC)"
              />
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Label>Events</Label>
                <HelpIcon content={getHelpText("webhooks.events")} />
              </div>
              <div className="space-y-2">
                {availableEvents.map((event) => (
                  <div key={event} className="flex items-center space-x-2">
                    <Checkbox
                      id={event}
                      checked={configData.events.includes(event)}
                      onCheckedChange={() => toggleEvent(event)}
                    />
                    <div className="flex items-center gap-2 flex-1">
                      <Label
                        htmlFor={event}
                        className="cursor-pointer font-normal"
                      >
                        {event}
                      </Label>
                      <HelpIcon
                        content={getHelpText(`webhooks.event.${event}` as any)}
                        side="right"
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Label htmlFor="retry-policy">Retry policy</Label>
                <HelpIcon content={getHelpText("webhooks.retry-policy")} />
              </div>
              <Select
                value={configData.retry_policy}
                onValueChange={(value: string) =>
                  setConfigData({ ...configData, retry_policy: value })
                }
              >
                <SelectTrigger id="retry-policy">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="exponential_backoff">
                    Exponential backoff (recommended)
                  </SelectItem>
                  <SelectItem value="no_retries">No retries</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center space-x-2">
              <Switch
                id="enabled"
                checked={configData.enabled}
                onCheckedChange={(checked) =>
                  setConfigData({ ...configData, enabled: checked })
                }
              />
              <Label htmlFor="enabled" className="cursor-pointer">
                Enabled
              </Label>
            </div>
            <div className="flex gap-2">
              <Button onClick={handleSave} disabled={saveMutation.isPending}>
                Save
              </Button>
              <Button variant="outline" onClick={() => testMutation.mutate()}>
                <Send className="mr-2 h-4 w-4" />
                Send test event
              </Button>
            </div>
            <HelpText
              title="Webhook setup and troubleshooting"
              content={getHelpTextLong("webhooks.setup")}
            />
          </CardContent>
        </Card>

        {/* Recent Deliveries */}
        <Card>
          <CardHeader>
            <CardTitle>Recent deliveries</CardTitle>
          </CardHeader>
          <CardContent>
            {deliveries && deliveries.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Timestamp</TableHead>
                    <TableHead>Event</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {deliveries.slice(0, 10).map((delivery) => (
                    <TableRow key={delivery.id}>
                      <TableCell className="text-xs text-muted-foreground">
                        {new Date(delivery.created_at).toLocaleString()}
                      </TableCell>
                      <TableCell className="text-xs">
                        {delivery.event_type}
                      </TableCell>
                      <TableCell>
                        <span
                          className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${
                            delivery.delivery_status === "succeeded"
                              ? "bg-accent/10 text-accent"
                              : delivery.delivery_status === "failed"
                              ? "bg-destructive/10 text-destructive"
                              : "bg-muted text-muted-foreground"
                          }`}
                        >
                          {delivery.delivery_status}
                        </span>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button variant="ghost" size="sm">
                            <Eye className="h-4 w-4" />
                          </Button>
                          {delivery.delivery_status === "failed" && (
                            <Button variant="ghost" size="sm">
                              <RotateCcw className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <p className="text-sm text-muted-foreground">No deliveries yet</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
