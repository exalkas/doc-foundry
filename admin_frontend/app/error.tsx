"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { AlertTriangle, Home, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const router = useRouter();

  useEffect(() => {
    // Log error to console for debugging
    console.error("Route error:", error);

    // In production, you could send this to an error tracking service
    // Example: Sentry.captureException(error);
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-12 dark:bg-slate-900">
      <Card className="w-full max-w-md">
        <CardHeader>
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-destructive" />
            <CardTitle>Something went wrong</CardTitle>
          </div>
          <CardDescription>
            An error occurred while loading this page. Please try again or
            return to the dashboard.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {process.env.NODE_ENV === "development" && (
            <div className="rounded-md bg-slate-100 p-3 dark:bg-slate-800">
              <p className="text-xs font-mono text-slate-600 dark:text-slate-400">
                {error.message}
              </p>
              {error.digest && (
                <p className="mt-2 text-xs text-slate-500 dark:text-slate-500">
                  Error ID: {error.digest}
                </p>
              )}
              {error.stack && (
                <details className="mt-2">
                  <summary className="cursor-pointer text-xs text-slate-500 dark:text-slate-500">
                    Stack trace
                  </summary>
                  <pre className="mt-2 overflow-auto text-xs text-slate-600 dark:text-slate-400">
                    {error.stack}
                  </pre>
                </details>
              )}
            </div>
          )}
          <div className="flex gap-2">
            <Button onClick={reset} variant="default" className="flex-1">
              <RefreshCw className="mr-2 h-4 w-4" />
              Try again
            </Button>
            <Link href="/" className="flex-1">
              <Button variant="outline" className="w-full">
                <Home className="mr-2 h-4 w-4" />
                Go to dashboard
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
