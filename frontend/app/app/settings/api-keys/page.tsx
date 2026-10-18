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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { KeyRound, Clipboard, Trash2 } from "lucide-react";
import { get, post, del } from "@/lib/api-client";
import type { ApiKey } from "@/lib/types";
import { useToast } from "@/hooks/use-toast";
import { getSuccessMessage, getErrorMessage } from "@/lib/notifications";
import { HelpIcon } from "@/components/app/help-icon";
import { HelpText } from "@/components/app/help-text";
import { getHelpText, getHelpTextLong } from "@/lib/help-content";

export default function ApiKeysPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [createOpen, setCreateOpen] = useState(false);
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    name: "",
    scopes: [] as string[],
    expiration: "never",
  });

  const { data: apiKeys, isLoading } = useQuery<ApiKey[]>({
    queryKey: ["api-keys"],
    queryFn: () => get("/api/api-keys"),
  });

  const createMutation = useMutation({
    mutationFn: (data: any) =>
      post<{ api_key: ApiKey; plaintext_key: string }>("/api/api-keys", data),
    onSuccess: (data) => {
      toast({
        variant: "success",
        title: getSuccessMessage("create", "api-key"),
        description: "API key created successfully",
      });
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
      setCreatedKey(data.plaintext_key);
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Error",
        description: getErrorMessage(error, "create", "api-key"),
      });
    },
  });

  const revokeMutation = useMutation({
    mutationFn: (id: string) => post(`/api/api-keys/${id}/revoke`),
    onSuccess: () => {
      toast({
        variant: "success",
        title: "API key revoked",
        description: "API key has been revoked successfully",
      });
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Error",
        description: getErrorMessage(error, "delete", "api-key"),
      });
    },
  });

  const availableScopes = [
    "documents:write",
    "documents:read",
    "templates:read",
    "webhooks:manage",
  ];

  const humanizeScope = (scope: string): string => {
    const scopeMap: Record<string, string> = {
      "documents:write": "Write Documents",
      "documents:read": "Read Documents",
      "templates:read": "Read Templates",
      "webhooks:manage": "Manage Webhooks",
    };
    return scopeMap[scope] || scope;
  };

  const toggleScope = (scope: string) => {
    setFormData({
      ...formData,
      scopes: formData.scopes.includes(scope)
        ? formData.scopes.filter((s) => s !== scope)
        : [...formData.scopes, scope],
    });
  };

  const handleCreate = () => {
    createMutation.mutate({
      name: formData.name,
      scopes: formData.scopes,
      expires_at: formData.expiration === "never" ? null : formData.expiration,
    });
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">API keys</h1>
          <p className="text-muted-foreground">
            Use API keys to call DocFoundry.app from your apps and automation
            tools
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <KeyRound className="mr-2 h-4 w-4" />
          New API key
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>API keys</CardTitle>
          <CardDescription>Manage your company API keys</CardDescription>
        </CardHeader>
        <CardContent>
          {apiKeys && apiKeys.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Prefix</TableHead>
                  <TableHead>Created at</TableHead>
                  <TableHead>Last used</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Scopes</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {apiKeys.map((key) => (
                  <TableRow key={key.id}>
                    <TableCell className="font-medium">{key.name}</TableCell>
                    <TableCell className="font-mono text-xs">
                      {key.prefix}...
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {new Date(key.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {key.last_used_at
                        ? new Date(key.last_used_at).toLocaleDateString()
                        : "Never"}
                    </TableCell>
                    <TableCell>
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${
                          key.status === "active"
                            ? "bg-accent/10 text-accent"
                            : "bg-muted text-muted-foreground"
                        }`}
                      >
                        {key.status}
                      </span>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {Array.isArray(key.scopes) ? key.scopes.join(", ") : "-"}
                    </TableCell>
                    <TableCell>
                      {key.status === "active" && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => revokeMutation.mutate(key.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-sm text-muted-foreground">No API keys yet</p>
          )}
        </CardContent>
      </Card>

      {/* Create API Key Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create API key</DialogTitle>
            <DialogDescription>
              Keys are scoped to this company. Store the secret value securely.
            </DialogDescription>
          </DialogHeader>
          {!createdKey ? (
            <>
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Label htmlFor="key-name">Name</Label>
                    <HelpIcon content={getHelpText("api-keys.name")} />
                  </div>
                  <Input
                    id="key-name"
                    value={formData.name}
                    onChange={(e) =>
                      setFormData({ ...formData, name: e.target.value })
                    }
                    placeholder="e.g. Zapier invoices workflow"
                  />
                </div>
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Label>Scopes</Label>
                    <HelpIcon content={getHelpText("api-keys.scopes")} />
                  </div>
                  <div className="space-y-2">
                    {availableScopes.map((scope) => (
                      <div key={scope} className="flex items-center space-x-2">
                        <Checkbox
                          id={scope}
                          checked={formData.scopes.includes(scope)}
                          onCheckedChange={() => toggleScope(scope)}
                        />
                        <div className="flex items-center gap-2 flex-1">
                          <Label
                            htmlFor={scope}
                            className="cursor-pointer font-normal"
                          >
                            {humanizeScope(scope)}
                          </Label>
                          <HelpIcon
                            content={getHelpText(
                              `api-keys.scope.${scope}` as any
                            )}
                            side="right"
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Label htmlFor="expiration">Expiration</Label>
                    <HelpIcon content={getHelpText("api-keys.expiration")} />
                  </div>
                  <Select
                    value={formData.expiration}
                    onValueChange={(value: string) =>
                      setFormData({ ...formData, expiration: value })
                    }
                  >
                    <SelectTrigger id="expiration">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="never">Never</SelectItem>
                      <SelectItem value="7d">7 days</SelectItem>
                      <SelectItem value="30d">30 days</SelectItem>
                      <SelectItem value="90d">90 days</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <HelpText
                  title="API key security best practices"
                  content={getHelpTextLong("api-keys.security")}
                />
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setCreateOpen(false)}>
                  Cancel
                </Button>
                <Button
                  onClick={handleCreate}
                  disabled={
                    !formData.name ||
                    formData.scopes.length === 0 ||
                    createMutation.isPending
                  }
                >
                  Create
                </Button>
              </DialogFooter>
            </>
          ) : (
            <>
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label>API key</Label>
                  <div className="flex gap-2">
                    <Input value={createdKey} readOnly className="font-mono" />
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => copyToClipboard(createdKey)}
                    >
                      <Clipboard className="h-4 w-4" />
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Copy this value now. You won't be able to see it again.
                  </p>
                </div>
              </div>
              <DialogFooter>
                <Button
                  onClick={() => {
                    setCreateOpen(false);
                    setCreatedKey(null);
                    setFormData({ name: "", scopes: [], expiration: "never" });
                  }}
                >
                  Done
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
