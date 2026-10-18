"use client";

import React, { createContext, useContext, ReactNode } from "react";
import { useWorkspace } from "@/hooks/use-workspace";
import type { Workspace } from "@/lib/auth";

interface WorkspaceContextType {
  workspace: Workspace | null;
  workspaces: Workspace[];
  loading: boolean;
  switchWorkspace: (workspaceId: string) => Promise<void>;
  createWorkspace: (name: string, primaryColor?: string) => Promise<Workspace>;
  deleteWorkspace: (workspaceId: string) => Promise<void>;
  refresh: () => void;
}

const WorkspaceContext = createContext<WorkspaceContextType | undefined>(
  undefined
);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const workspace = useWorkspace();

  return (
    <WorkspaceContext.Provider value={workspace}>
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspaceContext() {
  const context = useContext(WorkspaceContext);
  if (context === undefined) {
    throw new Error(
      "useWorkspaceContext must be used within a WorkspaceProvider"
    );
  }
  return context;
}
