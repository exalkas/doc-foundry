/**
 * Authentication utilities for marketing site
 */

import { apiClient } from "./api-client";

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterData {
  full_name: string;
  email: string;
  password: string;
  workspace_name: string;
}

export interface AuthResponse {
  token: string;
  user: {
    id: string;
    email: string;
    full_name?: string;
  };
  workspace?: {
    id: string;
    name: string;
  };
}

/**
 * Login with email and password
 */
export async function login(
  credentials: LoginCredentials
): Promise<AuthResponse> {
  return apiClient.post<AuthResponse>("/auth/login", credentials);
}

/**
 * Register new user and workspace
 */
export async function register(data: RegisterData): Promise<AuthResponse> {
  return apiClient.post<AuthResponse>("/auth/register", data);
}

/**
 * Get current user info
 */
export async function getCurrentUser(): Promise<AuthResponse> {
  return apiClient.get<AuthResponse>("/auth/me");
}

/**
 * Logout (clears cookies on backend)
 */
export async function logout(): Promise<void> {
  await apiClient.post("/auth/logout");
  // Redirect to home
  if (typeof window !== "undefined") {
    window.location.href = "/";
  }
}

/**
 * Check if user is authenticated
 */
export async function isAuthenticated(): Promise<boolean> {
  try {
    await getCurrentUser();
    return true;
  } catch {
    return false;
  }
}
