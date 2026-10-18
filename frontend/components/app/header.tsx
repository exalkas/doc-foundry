"use client";

import * as React from "react";
import Link from "next/link";
import Image from "next/image";
import { HelpCircle } from "lucide-react";
import { useWorkspaceContext } from "@/contexts/workspace-context";
import { WorkspaceSwitcher } from "./workspace-switcher";
import { UserMenu } from "./user-menu";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { Button } from "@/components/ui/button";
import { APP_NAME, ROUTES } from "@/lib/constants";

export function Header() {
  const { workspace } = useWorkspaceContext();

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 dark:border-slate-800 dark:bg-slate-900/95">
      <div className="flex h-14 items-center justify-between px-4 lg:px-8">
        <div className="flex items-center space-x-2">
          <Link href="/app" className="flex items-center space-x-2">
            {workspace?.logo_url ? (
              <Image
                src={workspace.logo_url}
                alt={workspace.name}
                width={24}
                height={24}
                className="h-6 w-6"
              />
            ) : (
              <span className="font-bold text-lg">{APP_NAME}</span>
            )}
          </Link>
          <WorkspaceSwitcher />
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant="ghost"
            size="icon"
            asChild
            title="Get help / Start onboarding"
          >
            <Link href={ROUTES.ONBOARDING}>
              <HelpCircle className="h-5 w-5" />
            </Link>
          </Button>
          <ThemeToggle />
          <UserMenu />
        </div>
      </div>
    </header>
  );
}
