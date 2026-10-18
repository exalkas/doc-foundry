"use client";

import React, { createContext, useContext, ReactNode } from "react";
import { useAdminAuth } from "@/hooks/use-admin-auth";
import type { User } from "@/lib/auth";

interface AdminAuthContextType {
  user: User | null;
  loading: boolean;
  authenticated: boolean;
  logout: () => void;
  refresh: () => Promise<void>;
}

const AdminAuthContext = createContext<AdminAuthContextType | undefined>(
  undefined
);

export function AdminAuthProvider({ children }: { children: ReactNode }) {
  const auth = useAdminAuth();

  return (
    <AdminAuthContext.Provider value={auth}>
      {children}
    </AdminAuthContext.Provider>
  );
}

export function useAdminAuthContext() {
  const context = useContext(AdminAuthContext);
  if (context === undefined) {
    throw new Error(
      "useAdminAuthContext must be used within an AdminAuthProvider"
    );
  }
  return context;
}
