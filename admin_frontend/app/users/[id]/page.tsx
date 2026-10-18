"use client";

import { use } from "react";
import { AdminLayout } from "@/components/layout/admin-layout";
import { UserDetailHeader } from "@/components/admin/user-detail-header";
import { useUser } from "@/hooks/use-user";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ArrowLeft, AlertCircle } from "lucide-react";

interface UserDetailPageProps {
  params: Promise<{ id: string }>;
}

export default function UserDetailPage({ params }: UserDetailPageProps) {
  const { id } = use(params);
  const { data: user, isLoading, error } = useUser(id);

  if (isLoading) {
    return (
      <AdminLayout>
        <div className="flex items-center justify-center py-12">
          <Spinner />
        </div>
      </AdminLayout>
    );
  }

  if (error || !user) {
    return (
      <AdminLayout>
        <div className="space-y-6">
          <div className="flex items-center gap-4">
            <Link href="/users">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Users
              </Button>
            </Link>
          </div>
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>User Not Found</AlertTitle>
            <AlertDescription>
              {error
                ? "The user endpoint may not be implemented yet. Please check with the backend team."
                : "User not found or error loading user"}
            </AlertDescription>
          </Alert>
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Link href="/users">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Users
            </Button>
          </Link>
        </div>

        <UserDetailHeader user={user} />

        <Card>
          <CardHeader>
            <CardTitle>User Information</CardTitle>
            <CardDescription>
              Detailed information about this user
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <p className="text-sm font-medium text-muted-foreground">
                  User ID
                </p>
                <p className="text-sm font-mono">{user.id}</p>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">
                  Email
                </p>
                <p className="text-sm">{user.email}</p>
              </div>
              {user.full_name && (
                <div>
                  <p className="text-sm font-medium text-muted-foreground">
                    Full Name
                  </p>
                  <p className="text-sm">{user.full_name}</p>
                </div>
              )}
              <div>
                <p className="text-sm font-medium text-muted-foreground">
                  Role
                </p>
                <p className="text-sm capitalize">{user.role}</p>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">
                  Email Verified
                </p>
                <p className="text-sm">
                  {user.is_email_verified ? "Yes" : "No"}
                </p>
              </div>
              {user.workspaces_count !== undefined && (
                <div>
                  <p className="text-sm font-medium text-muted-foreground">
                    Workspaces
                  </p>
                  <p className="text-sm">{user.workspaces_count}</p>
                </div>
              )}
              {user.last_login && (
                <div>
                  <p className="text-sm font-medium text-muted-foreground">
                    Last Login
                  </p>
                  <p className="text-sm">
                    {new Date(user.last_login).toLocaleString()}
                  </p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </AdminLayout>
  );
}
