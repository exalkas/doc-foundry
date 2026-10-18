"use client";

import * as React from "react";
import { HelpCircle } from "lucide-react";
import Link from "next/link";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface HelpIconProps {
  content: React.ReactNode;
  link?: string;
  className?: string;
  side?: "top" | "right" | "bottom" | "left";
  align?: "start" | "center" | "end";
}

export function HelpIcon({
  content,
  link,
  className,
  side = "top",
  align = "center",
}: HelpIconProps) {
  const icon = (
    <HelpCircle
      className={cn("h-4 w-4 text-muted-foreground", className)}
      aria-hidden="true"
    />
  );

  const tooltipContent = (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            className="inline-flex items-center focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 rounded-sm"
            aria-label="Help"
          >
            {icon}
          </button>
        </TooltipTrigger>
        <TooltipContent side={side} align={align} className="max-w-xs">
          <div className="space-y-1">
            {typeof content === "string" ? <p>{content}</p> : content}
            {link && (
              <div className="pt-1 border-t border-border">
                <Link
                  href={link}
                  className="text-primary hover:underline text-xs font-medium"
                  onClick={(e) => e.stopPropagation()}
                >
                  Learn more →
                </Link>
              </div>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );

  return tooltipContent;
}
