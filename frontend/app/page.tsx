"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getAuthToken } from "@/lib/auth";

export default function HomePage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const token = getAuthToken();
    const redirect = searchParams.get("redirect");

    if (token) {
      // User is authenticated, redirect to app or redirect param
      router.replace(redirect || "/app");
    } else {
      // User is not authenticated, redirect to login
      const loginUrl = redirect
        ? `/login?redirect=${encodeURIComponent(redirect)}`
        : "/login";
      router.replace(loginUrl);
    }
  }, [router, searchParams]);

  // Show loading state while redirecting
  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="text-center">
        <div className="mb-4 h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent mx-auto"></div>
        <p className="text-sm text-muted-foreground">Loading...</p>
      </div>
    </div>
  );
}
