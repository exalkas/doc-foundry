"use client";

import React, { createContext, useContext, ReactNode } from "react";
import { useAuth } from "@/hooks/use-auth";
import type { User } from "@/lib/auth";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  authenticated: boolean;
  logout: () => void;
  refresh: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const auth = useAuth();

  return <AuthContext.Provider value={auth}>{children}</AuthContext.Provider>;
}

export function useAuthContext() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuthContext must be used within an AuthProvider");
  }
  return context;
}
