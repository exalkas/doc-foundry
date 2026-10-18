"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Folders,
  UploadCloud,
  FileCode2,
  FileText,
  Workflow,
  Settings,
  CreditCard,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { ROUTES } from "@/lib/constants";

const navigation = [
  {
    label: "Dashboard",
    icon: LayoutDashboard,
    href: ROUTES.DASHBOARD,
  },
  {
    label: "Projects",
    icon: Folders,
    href: ROUTES.PROJECTS,
  },
  {
    label: "Templates",
    icon: FileCode2,
    href: ROUTES.TEMPLATES,
  },
  {
    label: "Upload",
    icon: UploadCloud,
    href: ROUTES.UPLOAD,
  },
  {
    label: "Documents",
    icon: FileText,
    href: ROUTES.DOCUMENTS,
  },
  {
    label: "Integrations",
    icon: Workflow,
    href: ROUTES.INTEGRATIONS,
  },
  {
    label: "Usage & Billing",
    icon: CreditCard,
    href: ROUTES.USAGE_BILLING,
  },
  {
    label: "Settings",
    icon: Settings,
    href: ROUTES.SETTINGS,
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-64 border-r bg-background md:flex md:flex-col">
      <nav className="flex-1 space-y-1 px-2 py-4">
        {navigation.map((item) => {
          const Icon = item.icon;
          // Use exact match for root routes, startsWith only for nested routes
          // Special handling: Usage & Billing should not highlight Settings
          const isActive =
            pathname === item.href ||
            (item.href !== ROUTES.DASHBOARD &&
              item.href !== ROUTES.SETTINGS &&
              pathname?.startsWith(item.href + "/"));

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground",
                isActive
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground"
              )}
            >
              <Icon className="h-5 w-5" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
