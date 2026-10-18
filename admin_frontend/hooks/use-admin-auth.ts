"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { get, ApiClientError } from "@/lib/api-client";
import {
  getAuthToken,
  removeAuthToken,
  setAuthToken,
  type User,
} from "@/lib/auth";

interface UseAdminAuthReturn {
  user: User | null;
  loading: boolean;
  authenticated: boolean;
  logout: () => void;
  refresh: () => Promise<void>;
}

export function useAdminAuth(): UseAdminAuthReturn {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchUser = async () => {
    try {
      const token = getAuthToken();
      if (!token) {
        setUser(null);
        setLoading(false);
        return;
      }

      const data = await get<{ user: any }>("/api/admin/auth/me");

      // Admin endpoint already verifies admin role, but double-check
      if (data.user?.global_role !== "admin") {
        setUser(null);
        removeAuthToken();
        router.push("/login");
        return;
      }

      // Map global_role to role for User type compatibility
      // Backend returns global_role: "admin" | "user", map to admin role
      // Since we've already verified admin role above, we can safely set to "admin"
      const mappedUser: User = {
        id: data.user.id,
        email: data.user.email,
        full_name: data.user.full_name,
        is_email_verified: data.user.is_email_verified,
        role: "admin",
      };
      setUser(mappedUser);
    } catch (error) {
      if (error instanceof ApiClientError && error.status === 401) {
        // Not authenticated
        setUser(null);
        removeAuthToken();
      } else {
        console.error("Failed to fetch user:", error);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUser();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const logout = () => {
    removeAuthToken();
    setUser(null);
    router.push("/login");
  };

  const refresh = async () => {
    await fetchUser();
  };

  return {
    user,
    loading,
    authenticated: !!user && user.role === "admin",
    logout,
    refresh,
  };
}
