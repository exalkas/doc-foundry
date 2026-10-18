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
import { formatDate } from "@/lib/utils";
import type { User } from "@/lib/types";
import { ExternalLink } from "lucide-react";
import { LoadingSpinner } from "@/components/ui/loading";

/**
 * Props for UserTable component
 */
interface UserTableProps {
  /** Array of users to display */
  users: User[];
  /** Whether data is currently loading */
  isLoading?: boolean;
}

export const UserTable = React.memo(function UserTable({
  users,
  isLoading = false,
}: UserTableProps) {
  if (isLoading) {
    return <LoadingSpinner message="Loading users..." />;
  }

  if (users.length === 0) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-sm text-muted-foreground">No users found</p>
      </div>
    );
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Email</TableHead>
            <TableHead>Name</TableHead>
            <TableHead>Role</TableHead>
            <TableHead>Workspaces</TableHead>
            <TableHead>Last Login</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {users.map((user) => (
            <TableRow key={user.id}>
              <TableCell className="font-medium">{user.email}</TableCell>
              <TableCell>{user.full_name || "-"}</TableCell>
              <TableCell>
                <Badge variant={user.role === "admin" ? "success" : "default"}>
                  {user.role}
                </Badge>
              </TableCell>
              <TableCell>{user.workspaces_count || 0}</TableCell>
              <TableCell className="text-muted-foreground">
                {user.last_login ? formatDate(user.last_login) : "Never"}
              </TableCell>
              <TableCell className="text-right">
                <Link href={`/users/${user.id}`}>
                  <Button variant="ghost" size="sm">
                    View
                    <ExternalLink className="ml-2 h-4 w-4" />
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
