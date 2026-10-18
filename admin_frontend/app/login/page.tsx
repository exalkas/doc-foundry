"use client";

import { useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { setAuthToken, getAuthToken, removeAuthToken } from "@/lib/auth";
import { post, ApiClientError } from "@/lib/api-client";
import { Shield, Eye, EyeOff } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // If already authenticated, redirect to dashboard
    // But first verify the token is valid by checking if user can be fetched
    const token = getAuthToken();
    if (token) {
      // Verify token is valid by attempting to fetch admin user
      fetch("/api/admin/auth/me", {
        headers: {
          Authorization: `Bearer ${token}`,
        },
        credentials: "include",
      })
        .then((res) => {
          if (res.ok) {
            return res.json();
          }
          // Token invalid, clear it
          removeAuthToken();
          return null;
        })
        .then((data) => {
          if (data?.user?.global_role === "admin") {
            const redirect = searchParams.get("redirect") || "/";
            router.replace(redirect);
          } else {
            // Not admin, clear token
            removeAuthToken();
          }
        })
        .catch(() => {
          // Error fetching user, clear token
          removeAuthToken();
        });
    }
  }, [router, searchParams]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const response = await post<{
        token: string;
        user: any;
      }>("/api/admin/auth/login", {
        email,
        password,
      });

      console.log("Admin login response:", response);

      // Store token (backend also sets HTTPOnly cookie, but we store for Authorization header)
      if (response.token) {
        setAuthToken(response.token);
      }

      // Reset loading state
      setLoading(false);

      // Redirect to dashboard - use window.location for full page reload to ensure cookie is set
      // This prevents blank page issues where the auth context hasn't loaded yet
      const redirect = searchParams.get("redirect") || "/";
      console.log("Redirecting to:", redirect);

      // Use window.location for full page reload to ensure cookie is available
      // Small delay to ensure cookie is set
      setTimeout(() => {
        window.location.href = redirect;
      }, 100);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError(err.message || "Login failed. Please check your credentials.");
      } else {
        setError("An unexpected error occurred. Please try again.");
      }
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-12 dark:bg-slate-900 sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <div className="flex justify-center mb-4">
            <Shield className="h-12 w-12 text-primary" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
            Admin Login
          </h1>
          <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
            DocFoundry.app Admin Platform
          </p>
        </div>

        <div className="rounded-lg border bg-white p-8 shadow-sm dark:bg-slate-800 dark:border-slate-700">
          {error && (
            <Alert variant="destructive" className="mb-4">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  name="email"
                  required
                  placeholder="admin@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={loading}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    name="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={loading}
                    className="pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                    disabled={loading}
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </div>
            </div>

            <Button type="submit" className="w-full" isLoading={loading}>
              Sign in
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
