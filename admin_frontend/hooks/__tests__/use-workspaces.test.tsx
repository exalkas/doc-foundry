import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useWorkspaces } from "../use-workspaces";
import * as apiClient from "@/lib/api-client";
import type { Workspace } from "@/lib/types";
import { ReactNode } from "react";

// Mock the API client
jest.mock("@/lib/api-client", () => ({
  get: jest.fn(),
}));

const mockGet = apiClient.get as jest.MockedFunction<typeof apiClient.get>;

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  Wrapper.displayName = "TestQueryClientProvider";
  return Wrapper;
}

describe("useWorkspaces", () => {
  beforeEach(() => {
    mockGet.mockClear();
  });

  it("should fetch workspaces with default parameters", async () => {
    const mockWorkspaces: Workspace[] = [
      {
        id: "1",
        name: "Workspace 1",
        status: "active",
        created_at: "2024-01-01T00:00:00Z",
      },
      {
        id: "2",
        name: "Workspace 2",
        status: "suspended",
        created_at: "2024-01-02T00:00:00Z",
      },
    ];

    mockGet.mockResolvedValue(mockWorkspaces);

    const { result } = renderHook(() => useWorkspaces(), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(true);
    expect(mockGet).toHaveBeenCalledWith(
      "/api/admin/workspaces?page=1&page_size=50"
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual(mockWorkspaces);
  });

  it("should fetch workspaces with custom parameters", async () => {
    const mockWorkspaces: Workspace[] = [
      {
        id: "1",
        name: "Workspace 1",
        status: "active",
        created_at: "2024-01-01T00:00:00Z",
      },
    ];

    mockGet.mockResolvedValue(mockWorkspaces);

    const { result } = renderHook(
      () =>
        useWorkspaces({
          status: "active",
          page: 2,
          page_size: 25,
        }),
      {
        wrapper: createWrapper(),
      }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockGet).toHaveBeenCalledWith(
      "/api/admin/workspaces?status=active&page=2&page_size=25"
    );
    expect(result.current.data).toEqual(mockWorkspaces);
  });

  it("should handle errors correctly", async () => {
    const error = new Error("Failed to fetch workspaces");
    mockGet.mockRejectedValue(error);

    const { result } = renderHook(() => useWorkspaces(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBe(error);
  });
});
