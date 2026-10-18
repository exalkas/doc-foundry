"use client";

import * as React from "react";
import { User, Settings, LogOut, Shield } from "lucide-react";
import { useAuthContext } from "@/contexts/auth-context";
import { useRouter } from "next/navigation";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { ROUTES } from "@/lib/constants";

export function UserMenu() {
  const { user, logout } = useAuthContext();
  const router = useRouter();
  const isAdmin = user?.role === "admin";

  if (!user) {
    return null;
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 rounded-full text-foreground hover:bg-accent hover:text-accent-foreground"
        >
          <User className="h-5 w-5" />
          <span className="sr-only">User menu</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-56" align="end" forceMount>
        <DropdownMenuLabel className="font-normal">
          <div className="flex flex-col space-y-1">
            <p className="text-sm font-medium leading-none">
              {user.full_name || user.email}
            </p>
            <p className="text-xs leading-none text-muted-foreground">
              {user.email}
            </p>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => router.push(ROUTES.SETTINGS)}>
          <Settings className="mr-2 h-4 w-4" />
          <span>Company settings</span>
        </DropdownMenuItem>
        {isAdmin && (
          <DropdownMenuItem onClick={() => router.push(ROUTES.ADMIN)}>
            <Shield className="mr-2 h-4 w-4" />
            <span>Admin panel</span>
          </DropdownMenuItem>
        )}
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onClick={logout}
          data-testid="logout-button"
          className="text-red-600 dark:text-red-400 focus:text-red-600 dark:focus:text-red-400 focus:bg-red-50 dark:focus:bg-red-950/20 cursor-pointer"
        >
          <LogOut className="mr-2 h-4 w-4 flex-shrink-0 text-red-600 dark:text-red-400" />
          <span className="flex-1">Sign out</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
