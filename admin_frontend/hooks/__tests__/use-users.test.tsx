import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useUsers } from "../use-users";
import * as apiClient from "@/lib/api-client";
import type { User } from "@/lib/types";
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

describe("useUsers", () => {
  beforeEach(() => {
    mockGet.mockClear();
  });

  it("should fetch users with default parameters", async () => {
    const mockUsers: User[] = [
      {
        id: "1",
        email: "user1@example.com",
        role: "admin",
        is_email_verified: true,
      },
      {
        id: "2",
        email: "user2@example.com",
        role: "owner",
        is_email_verified: false,
      },
    ];

    mockGet.mockResolvedValue(mockUsers);

    const { result } = renderHook(() => useUsers(), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(true);
    expect(mockGet).toHaveBeenCalledWith(
      "/api/admin/users?page=1&page_size=50"
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual(mockUsers);
  });

  it("should fetch users with role filter", async () => {
    const mockUsers: User[] = [
      {
        id: "1",
        email: "admin@example.com",
        role: "admin",
        is_email_verified: true,
      },
    ];

    mockGet.mockResolvedValue(mockUsers);

    const { result } = renderHook(
      () =>
        useUsers({
          role: "admin",
          page: 1,
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
      "/api/admin/users?role=admin&page=1&page_size=25"
    );
    expect(result.current.data).toEqual(mockUsers);
  });

  it("should handle errors correctly", async () => {
    const error = new Error("Failed to fetch users");
    mockGet.mockRejectedValue(error);

    const { result } = renderHook(() => useUsers(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBe(error);
  });
});
