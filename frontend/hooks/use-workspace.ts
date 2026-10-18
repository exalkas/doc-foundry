"use client";

import { useState, useEffect, useCallback } from "react";
import { get, post, del } from "@/lib/api-client";
import type { Workspace } from "@/lib/auth";

interface WorkspaceState {
  workspace: Workspace | null;
  workspaces: Workspace[];
  loading: boolean;
}

export function useWorkspace() {
  const [state, setState] = useState<WorkspaceState>({
    workspace: null,
    workspaces: [],
    loading: true,
  });

  const loadWorkspaces = useCallback(async () => {
    try {
      const data = await get<{
        workspaces: Workspace[];
        current_workspace: Workspace;
      }>("/api/auth/me");

      setState({
        workspace: data.current_workspace || data.workspaces[0] || null,
        workspaces: data.workspaces || [],
        loading: false,
      });

      // Store current workspace ID in localStorage
      if (data.current_workspace) {
        localStorage.setItem("current_workspace_id", data.current_workspace.id);
      }
    } catch (error) {
      setState({
        workspace: null,
        workspaces: [],
        loading: false,
      });
    }
  }, []);

  useEffect(() => {
    loadWorkspaces();
  }, [loadWorkspaces]);

  const switchWorkspace = useCallback(
    async (workspaceId: string) => {
      try {
        // Update workspace context on backend
        await post("/api/auth/switch-workspace", { workspace_id: workspaceId });

        // Reload workspaces
        await loadWorkspaces();

        // Update localStorage
        localStorage.setItem("current_workspace_id", workspaceId);
      } catch (error) {
        console.error("Failed to switch workspace:", error);
        throw error;
      }
    },
    [loadWorkspaces]
  );

  const createWorkspace = useCallback(
    async (name: string, primaryColor?: string) => {
      try {
        const newWorkspace = await post<Workspace>("/api/workspaces", {
          name,
          primary_color: primaryColor,
        });

        // Reload workspaces to get updated list
        await loadWorkspaces();

        // Automatically switch to the new workspace
        if (newWorkspace.id) {
          await switchWorkspace(newWorkspace.id);
        }

        return newWorkspace;
      } catch (error) {
        console.error("Failed to create workspace:", error);
        throw error;
      }
    },
    [loadWorkspaces, switchWorkspace]
  );

  const deleteWorkspace = useCallback(
    async (workspaceId: string) => {
      try {
        await del(`/api/workspaces/${workspaceId}`);

        // Reload workspaces
        await loadWorkspaces();

        // If deleted workspace was current, switch to first available
        if (state.workspace?.id === workspaceId) {
          const remainingWorkspaces = state.workspaces.filter(
            (ws) => ws.id !== workspaceId
          );
          if (remainingWorkspaces.length > 0) {
            await switchWorkspace(remainingWorkspaces[0].id);
          }
        }
      } catch (error) {
        console.error("Failed to delete workspace:", error);
        throw error;
      }
    },
    [loadWorkspaces, switchWorkspace, state.workspace, state.workspaces]
  );

  const refresh = useCallback(() => {
    loadWorkspaces();
  }, [loadWorkspaces]);

  return {
    ...state,
    switchWorkspace,
    createWorkspace,
    deleteWorkspace,
    refresh,
  };
}
