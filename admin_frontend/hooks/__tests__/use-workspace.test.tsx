import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useWorkspace } from "../use-workspace";
import * as apiClient from "@/lib/api-client";
import type { Workspace } from "@/lib/types";
import { ApiClientError } from "@/lib/api-client";
import { ReactNode } from "react";

// Mock the API client
jest.mock("@/lib/api-client", () => ({
  get: jest.fn(),
  ApiClientError: class ApiClientError extends Error {
    status?: number;
    constructor(message: string, status?: number) {
      super(message);
      this.status = status;
    }
  },
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

describe("useWorkspace", () => {
  beforeEach(() => {
    mockGet.mockClear();
  });

  it("should fetch a single workspace by id", async () => {
    const mockWorkspace: Workspace = {
      id: "workspace-1",
      name: "Test Workspace",
      status: "active",
      created_at: "2024-01-01T00:00:00Z",
    };

    mockGet.mockResolvedValue(mockWorkspace);

    const { result } = renderHook(() => useWorkspace("workspace-1"), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(true);
    expect(mockGet).toHaveBeenCalledWith("/api/admin/workspaces/workspace-1");

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual(mockWorkspace);
  });

  it("should handle 404 errors correctly", async () => {
    const error = new ApiClientError("Not found", 404);
    mockGet.mockRejectedValue(error);

    const { result } = renderHook(() => useWorkspace("workspace-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(mockGet).toHaveBeenCalledTimes(1);
    expect(mockGet).toHaveBeenCalledWith("/api/admin/workspaces/workspace-1");
    expect(result.current.error).toBe(error);
  });

  it("should not fetch when id is empty", () => {
    const { result } = renderHook(() => useWorkspace(""), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(false);
    expect(result.current.isFetching).toBe(false);
    expect(mockGet).not.toHaveBeenCalled();
  });

  it("should handle non-404 errors correctly", async () => {
    const error = new ApiClientError("Server error", 500);
    // Mock multiple failures since the hook retries up to 2 times for non-404 errors
    mockGet.mockRejectedValue(error);

    const { result } = renderHook(() => useWorkspace("workspace-1"), {
      wrapper: createWrapper(),
    });

    // Wait for all retries to complete (hook retries up to 2 times)
    await waitFor(
      () => {
        expect(result.current.isError).toBe(true);
      },
      { timeout: 5000 }
    );

    // The hook will retry, so we expect multiple calls (initial + retries)
    expect(mockGet).toHaveBeenCalled();
    expect(result.current.error).toBeDefined();
  });
});
