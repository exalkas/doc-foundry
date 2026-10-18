"use client";

import { useState, useEffect } from "react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { UserPlus, MoreVertical, Pencil, Trash2 } from "lucide-react";
import Link from "next/link";
import { useWorkspaceContext } from "@/contexts/workspace-context";
import { useAuthContext } from "@/contexts/auth-context";
import { get, post, patch, del, uploadFile } from "@/lib/api-client";
import type { Workspace } from "@/lib/auth";
import { useToast } from "@/hooks/use-toast";
import { getSuccessMessage, getErrorMessage } from "@/lib/notifications";
import { ROUTES } from "@/lib/constants";

interface WorkspaceMember {
  id: string;
  user_id: string;
  email: string;
  role: "owner" | "member" | "readonly";
  invited_at: string;
  joined_at?: string;
}

export default function SettingsPage() {
  const { workspace } = useWorkspaceContext();
  const { user } = useAuthContext();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteData, setInviteData] = useState({
    email: "",
    role: "member" as "member" | "readonly",
  });
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const [primaryColor, setPrimaryColor] = useState<string>(
    workspace?.primary_color || "#2563EB"
  );

  // Update primary color when workspace changes
  useEffect(() => {
    if (workspace?.primary_color) {
      setPrimaryColor(workspace.primary_color);
    }
  }, [workspace?.primary_color]);

  const { data: members } = useQuery<WorkspaceMember[]>({
    queryKey: ["workspace", "members"],
    queryFn: () => get("/api/workspaces/current/members"),
  });

  const updateWorkspaceMutation = useMutation({
    mutationFn: (data: {
      name?: string;
      custom_domain?: string;
      primary_color?: string;
    }) => patch<Workspace>("/api/workspaces/current", data),
    onSuccess: () => {
      toast({
        variant: "success",
        title: getSuccessMessage("update", "workspace"),
        description: "Workspace settings updated successfully",
      });
      queryClient.invalidateQueries({ queryKey: ["workspace"] });
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Error",
        description: getErrorMessage(error, "update", "workspace"),
      });
    },
  });

  const uploadLogoMutation = useMutation({
    mutationFn: (file: File) =>
      uploadFile<Workspace>("/api/workspaces/current/upload-logo", file),
    onSuccess: (data) => {
      toast({
        variant: "success",
        title: "Logo uploaded",
        description: "Logo uploaded successfully",
      });
      queryClient.invalidateQueries({ queryKey: ["workspace"] });
      if (data.logo_url) {
        setLogoPreview(null); // Clear preview after successful upload
      }
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Error",
        description: getErrorMessage(error, "upload", "workspace"),
      });
    },
  });

  const inviteMutation = useMutation({
    mutationFn: (data: { email: string; role: string }) =>
      post("/api/workspaces/current/invite", data),
    onSuccess: () => {
      toast({
        variant: "success",
        title: "Invitation sent",
        description: "Team member invitation sent successfully",
      });
      queryClient.invalidateQueries({ queryKey: ["workspace", "members"] });
      setInviteOpen(false);
      setInviteData({ email: "", role: "member" });
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Error",
        description: getErrorMessage(error, "create", "workspace"),
      });
    },
  });

  const updateRoleMutation = useMutation({
    mutationFn: ({ memberId, role }: { memberId: string; role: string }) =>
      patch(`/api/workspaces/current/members/${memberId}`, { role }),
    onSuccess: () => {
      toast({
        variant: "success",
        title: "Role updated",
        description: "Member role updated successfully",
      });
      queryClient.invalidateQueries({ queryKey: ["workspace", "members"] });
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Error",
        description: getErrorMessage(error, "update", "workspace"),
      });
    },
  });

  const removeMemberMutation = useMutation({
    mutationFn: (memberId: string) =>
      del(`/api/workspaces/current/members/${memberId}`),
    onSuccess: () => {
      toast({
        variant: "success",
        title: "Member removed",
        description: "Team member removed successfully",
      });
      queryClient.invalidateQueries({ queryKey: ["workspace", "members"] });
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Error",
        description: getErrorMessage(error, "delete", "workspace"),
      });
    },
  });

  const isOwner = user?.role === "owner";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">
          Manage company settings and members
        </p>
      </div>

      <Tabs defaultValue="workspace" className="space-y-4">
        <TabsList>
          <TabsTrigger value="workspace">Company</TabsTrigger>
          <TabsTrigger value="members">Members</TabsTrigger>
          <TabsTrigger value="affiliates">Affiliates</TabsTrigger>
          {isOwner && (
            <TabsTrigger value="billing">Usage & Billing</TabsTrigger>
          )}
          {isOwner && <TabsTrigger value="branding">Branding</TabsTrigger>}
        </TabsList>

        <TabsContent value="workspace" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Company details</CardTitle>
              <CardDescription>Update company name and domain</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="workspace-name">Company name</Label>
                <Input
                  id="workspace-name"
                  defaultValue={workspace?.name || ""}
                  onBlur={(e) => {
                    if (e.target.value !== workspace?.name && isOwner) {
                      updateWorkspaceMutation.mutate({ name: e.target.value });
                    }
                  }}
                  disabled={!isOwner}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="custom-domain">Custom domain</Label>
                <Input
                  id="custom-domain"
                  defaultValue={workspace?.custom_domain || ""}
                  placeholder="Optional"
                  onBlur={(e) => {
                    if (
                      e.target.value !== workspace?.custom_domain &&
                      isOwner
                    ) {
                      updateWorkspaceMutation.mutate({
                        custom_domain: e.target.value,
                      });
                    }
                  }}
                  disabled={!isOwner}
                />
              </div>
              {isOwner && (
                <Button
                  onClick={() => {
                    const nameEl = document.getElementById(
                      "workspace-name"
                    ) as HTMLInputElement;
                    const domainEl = document.getElementById(
                      "custom-domain"
                    ) as HTMLInputElement;
                    updateWorkspaceMutation.mutate({
                      name: nameEl.value,
                      custom_domain: domainEl.value,
                    });
                  }}
                  disabled={updateWorkspaceMutation.isPending}
                >
                  Save changes
                </Button>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="members" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Company members</CardTitle>
                  <CardDescription>
                    Manage team members and their roles
                  </CardDescription>
                </div>
                {isOwner && (
                  <Button onClick={() => setInviteOpen(true)}>
                    <UserPlus className="mr-2 h-4 w-4" />
                    Invite
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {members && members.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Email</TableHead>
                      <TableHead>Role</TableHead>
                      <TableHead>Invited at</TableHead>
                      <TableHead>Joined at</TableHead>
                      {isOwner && <TableHead></TableHead>}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {members.map((member) => (
                      <TableRow key={member.id}>
                        <TableCell>{member.email}</TableCell>
                        <TableCell>
                          <span className="capitalize">{member.role}</span>
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {new Date(member.invited_at).toLocaleDateString()}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {member.joined_at
                            ? new Date(member.joined_at).toLocaleDateString()
                            : "-"}
                        </TableCell>
                        {isOwner && (
                          <TableCell>
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="ghost" className="h-8 w-8 p-0">
                                  <MoreVertical className="h-4 w-4" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuItem
                                  onClick={() =>
                                    removeMemberMutation.mutate(member.id)
                                  }
                                  className="text-destructive"
                                >
                                  <Trash2 className="mr-2 h-4 w-4" />
                                  Remove member
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </TableCell>
                        )}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <p className="text-sm text-muted-foreground">No members yet</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="affiliates" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Affiliate Program</CardTitle>
              <CardDescription>
                Manage your affiliate account, links, and earnings
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Link href="/app/settings/affiliates">
                <Button>Go to Affiliate Portal</Button>
              </Link>
            </CardContent>
          </Card>
        </TabsContent>

        {isOwner && (
          <TabsContent value="billing" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Usage & Billing</CardTitle>
                <CardDescription>
                  Manage your subscription, view usage, and payment history
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Link href={ROUTES.USAGE_BILLING}>
                  <Button>Go to Usage & Billing</Button>
                </Link>
              </CardContent>
            </Card>
          </TabsContent>
        )}

        {isOwner && (
          <TabsContent value="branding" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Branding</CardTitle>
                <CardDescription>
                  Customize logo and primary color for this company
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="logo">Logo</Label>
                  {workspace?.logo_url && !logoPreview && (
                    <div className="mb-2">
                      <img
                        src={
                          workspace.logo_url.startsWith("http")
                            ? workspace.logo_url
                            : `${
                                process.env.NEXT_PUBLIC_BACKEND_URL ||
                                "http://localhost:8000"
                              }${workspace.logo_url}`
                        }
                        alt="Current logo"
                        className="h-16 w-auto object-contain rounded"
                      />
                    </div>
                  )}
                  {logoPreview && (
                    <div className="mb-2">
                      <img
                        src={logoPreview}
                        alt="Logo preview"
                        className="h-16 w-auto object-contain rounded"
                      />
                    </div>
                  )}
                  <Input
                    id="logo"
                    type="file"
                    accept="image/png,image/jpeg,image/jpg,image/svg+xml,image/gif,image/webp"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) {
                        // Validate file size (5MB max)
                        if (file.size > 5 * 1024 * 1024) {
                          toast({
                            variant: "destructive",
                            title: "File too large",
                            description: "Logo file must be less than 5MB",
                          });
                          return;
                        }
                        // Create preview
                        const reader = new FileReader();
                        reader.onloadend = () => {
                          setLogoPreview(reader.result as string);
                        };
                        reader.readAsDataURL(file);
                        // Upload logo
                        uploadLogoMutation.mutate(file);
                      }
                    }}
                    disabled={uploadLogoMutation.isPending}
                  />
                  <p className="text-xs text-muted-foreground">
                    Supported formats: PNG, JPEG, SVG, GIF, WebP (max 5MB)
                  </p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="primary-color">Primary color</Label>
                  <div className="flex items-center gap-4">
                    <Input
                      id="primary-color"
                      type="color"
                      value={primaryColor}
                      onChange={(e) => {
                        setPrimaryColor(e.target.value);
                      }}
                      className="h-10 w-20 cursor-pointer"
                    />
                    <Input
                      type="text"
                      value={primaryColor}
                      onChange={(e) => {
                        // Validate hex color format
                        const hexPattern = /^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$/;
                        if (
                          hexPattern.test(e.target.value) ||
                          e.target.value === ""
                        ) {
                          setPrimaryColor(e.target.value);
                        }
                      }}
                      placeholder="#2563EB"
                      className="flex-1"
                    />
                  </div>
                </div>
                <Button
                  onClick={() => {
                    if (primaryColor !== workspace?.primary_color) {
                      updateWorkspaceMutation.mutate({
                        primary_color: primaryColor,
                      });
                    }
                  }}
                  disabled={
                    updateWorkspaceMutation.isPending ||
                    primaryColor === workspace?.primary_color
                  }
                >
                  {updateWorkspaceMutation.isPending
                    ? "Saving..."
                    : "Save branding"}
                </Button>
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>

      {/* Invite Member Dialog */}
      <Dialog open={inviteOpen} onOpenChange={setInviteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Invite member</DialogTitle>
            <DialogDescription>
              Send an invitation to join this company
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="invite-email">Email</Label>
              <Input
                id="invite-email"
                type="email"
                value={inviteData.email}
                onChange={(e) =>
                  setInviteData({ ...inviteData, email: e.target.value })
                }
                placeholder="user@example.com"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="invite-role">Role</Label>
              <Select
                value={inviteData.role}
                onValueChange={(value: "member" | "readonly") =>
                  setInviteData({ ...inviteData, role: value })
                }
              >
                <SelectTrigger id="invite-role">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="member">Member</SelectItem>
                  <SelectItem value="readonly">Readonly</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setInviteOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => inviteMutation.mutate(inviteData)}
              disabled={!inviteData.email || inviteMutation.isPending}
            >
              Send invitation
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
