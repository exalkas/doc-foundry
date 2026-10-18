"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Building2,
  Users,
  UserCheck,
  CreditCard,
  FileText,
  FileSearch,
  Activity,
  BarChart3,
} from "lucide-react";

const navigation = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Workspaces", href: "/workspaces", icon: Building2 },
  { name: "Users", href: "/users", icon: Users },
  { name: "Affiliates", href: "/affiliates", icon: UserCheck },
  { name: "Billing", href: "/billing", icon: CreditCard },
  { name: "Support", href: "/support/documents", icon: FileText },
  { name: "Audit Logs", href: "/system/audit-logs", icon: FileSearch },
  { name: "Metrics", href: "/system/metrics", icon: Activity },
  { name: "Analytics", href: "/system/analytics", icon: BarChart3 },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-64 border-r bg-background md:flex md:flex-col">
      <nav className="flex-1 space-y-1 px-2 py-4">
        {navigation.map((item) => {
          const isActive =
            pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "group flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
              )}
            >
              <item.icon className="h-5 w-5" />
              {item.name}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
