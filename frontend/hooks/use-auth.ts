"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  getCurrentUser,
  getAuthToken,
  removeAuthToken,
  type User,
} from "@/lib/auth";
import { get } from "@/lib/api-client";

interface AuthState {
  user: User | null;
  loading: boolean;
  authenticated: boolean;
}

export function useAuth() {
  const router = useRouter();
  const [state, setState] = useState<AuthState>({
    user: null,
    loading: true,
    authenticated: false,
  });

  const checkAuth = useCallback(async () => {
    try {
      const token = getAuthToken();
      if (!token) {
        setState({
          user: null,
          loading: false,
          authenticated: false,
        });
        return;
      }

      // Verify token with backend
      try {
        const data = await get<{ user: User }>("/api/auth/me");
        setState({
          user: data.user,
          loading: false,
          authenticated: true,
        });
      } catch (error) {
        // Token invalid, clear it
        removeAuthToken();
        setState({
          user: null,
          loading: false,
          authenticated: false,
        });
      }
    } catch (error) {
      setState({
        user: null,
        loading: false,
        authenticated: false,
      });
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const logout = useCallback(() => {
    removeAuthToken();
    setState({
      user: null,
      loading: false,
      authenticated: false,
    });
    router.push("/login");
  }, [router]);

  const refresh = useCallback(() => {
    checkAuth();
  }, [checkAuth]);

  return {
    ...state,
    logout,
    refresh,
  };
}
