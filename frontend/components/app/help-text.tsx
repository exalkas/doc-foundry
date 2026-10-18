"use client";

import * as React from "react";
import { ChevronDown, ChevronUp, HelpCircle } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface HelpTextProps {
  title?: string;
  content: React.ReactNode;
  link?: string;
  defaultOpen?: boolean;
  className?: string;
}

export function HelpText({
  title,
  content,
  link,
  defaultOpen = false,
  className,
}: HelpTextProps) {
  const [isOpen, setIsOpen] = React.useState(defaultOpen);

  return (
    <div
      className={cn("rounded-md border bg-muted/50 p-3 space-y-2", className)}
    >
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 w-full text-left focus:outline-none rounded-sm"
        aria-expanded={isOpen}
        aria-label={title || "Toggle help information"}
      >
        <HelpCircle className="h-4 w-4 text-muted-foreground flex-shrink-0" />
        {title && (
          <span className="text-sm font-medium text-foreground">{title}</span>
        )}
        {isOpen ? (
          <ChevronUp className="h-4 w-4 text-muted-foreground ml-auto" />
        ) : (
          <ChevronDown className="h-4 w-4 text-muted-foreground ml-auto" />
        )}
      </button>
      {isOpen && (
        <div className="pl-6 space-y-2 text-sm text-muted-foreground">
          {typeof content === "string" ? <p>{content}</p> : content}
          {link && (
            <div>
              <Link
                href={link}
                className="text-primary hover:underline font-medium inline-flex items-center gap-1"
              >
                Learn more
                <span>→</span>
              </Link>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
