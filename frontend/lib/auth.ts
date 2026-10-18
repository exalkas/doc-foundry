/**
 * Authentication utilities for JWT handling and cookies
 */

export interface User {
  id: string;
  email: string;
  full_name?: string;
  role: "admin" | "owner" | "member" | "readonly";
  workspace_id?: string;
  is_email_verified: boolean;
}

export interface Workspace {
  id: string;
  name: string;
  owner_user_id: string;
  status: "active" | "suspended" | "trial" | "canceled";
  primary_color?: string;
  logo_url?: string;
  custom_domain?: string;
}

export interface AuthResponse {
  token: string;
  user: User;
  workspace?: Workspace;
}

/**
 * Get auth token from cookies
 */
export function getAuthToken(): string | null {
  if (typeof document === "undefined") return null;

  const cookies = document.cookie.split(";");
  const tokenCookie = cookies.find((cookie) =>
    cookie.trim().startsWith("auth_token=")
  );

  return tokenCookie ? tokenCookie.split("=")[1] : null;
}

/**
 * Set auth token in cookies
 */
export function setAuthToken(token: string): void {
  if (typeof document === "undefined") return;

  // Set cookie with httpOnly-like security (client-side)
  document.cookie = `auth_token=${token}; path=/; max-age=86400; SameSite=Lax`;
}

/**
 * Remove auth token from cookies
 */
export function removeAuthToken(): void {
  if (typeof document === "undefined") return;

  document.cookie = "auth_token=; path=/; max-age=0";
}

/**
 * Decode JWT token (client-side, basic decode without verification)
 * Note: In production, token verification should be done server-side
 */
export function decodeToken(token: string): any {
  try {
    const base64Url = token.split(".")[1];
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join("")
    );
    return JSON.parse(jsonPayload);
  } catch (error) {
    return null;
  }
}

/**
 * Get current user from token
 */
export function getCurrentUser(): User | null {
  const token = getAuthToken();
  if (!token) return null;

  const decoded = decodeToken(token);
  if (!decoded || !decoded.user) return null;

  return decoded.user;
}

/**
 * Check if user is authenticated
 */
export function isAuthenticated(): boolean {
  return getAuthToken() !== null;
}

/**
 * Check if user has admin role
 */
export function isAdmin(): boolean {
  const user = getCurrentUser();
  return user?.role === "admin";
}

/**
 * Check if user has workspace role
 */
export function hasWorkspaceRole(
  role: "owner" | "member" | "readonly"
): boolean {
  const user = getCurrentUser();
  if (!user) return false;

  // Admin has all permissions
  if (user.role === "admin") return true;

  // Check workspace role
  return user.role === role;
}
