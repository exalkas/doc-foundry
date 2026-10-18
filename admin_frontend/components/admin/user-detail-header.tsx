"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { formatDate, formatDateTime } from "@/lib/utils";
import type { User } from "@/lib/types";

interface UserDetailHeaderProps {
  user: User;
}

export function UserDetailHeader({ user }: UserDetailHeaderProps) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <h2 className="text-2xl font-bold">{user.email}</h2>
            <Badge variant={user.role === "admin" ? "success" : "default"}>
              {user.role}
            </Badge>
          </div>
          <div className="space-y-1 text-sm text-muted-foreground">
            <p>
              <span className="font-medium">ID:</span> {user.id}
            </p>
            {user.full_name && (
              <p>
                <span className="font-medium">Name:</span> {user.full_name}
              </p>
            )}
            <p>
              <span className="font-medium">Email Verified:</span>{" "}
              {user.is_email_verified ? "Yes" : "No"}
            </p>
            {user.workspaces_count !== undefined && (
              <p>
                <span className="font-medium">Workspaces:</span>{" "}
                {user.workspaces_count}
              </p>
            )}
            {user.last_login && (
              <p>
                <span className="font-medium">Last Login:</span>{" "}
                {formatDateTime(user.last_login)}
              </p>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
