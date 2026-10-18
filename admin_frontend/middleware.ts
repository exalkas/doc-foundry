/**
 * Middleware for route protection and authentication
 *
 * SECURITY NOTE:
 * This middleware performs client-side JWT decoding for UX purposes only (route protection).
 * It does NOT verify the JWT signature - this is intentional for performance reasons.
 *
 * IMPORTANT: The backend MUST verify the JWT signature on every API request.
 * This middleware is only used to:
 * - Redirect unauthenticated users to login
 * - Provide better UX by checking role client-side
 * - Prevent unnecessary API calls for unauthorized routes
 *
 * Security is enforced by the backend API, not this middleware.
 */

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const token = request.cookies.get("auth_token")?.value;

  // Allow login page
  if (request.nextUrl.pathname === "/login") {
    // If already authenticated and is admin, redirect to dashboard
    if (token) {
      try {
        // Basic JWT decode to check role (backend will verify)
        // JWT payload structure: { sub, workspace_id, global_role }
        const base64Url = token.split(".")[1];
        const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
        const payload = JSON.parse(Buffer.from(base64, "base64").toString());
        // Check global_role at top level (not nested under user)
        if (payload?.global_role === "admin") {
          return NextResponse.redirect(new URL("/", request.url));
        }
      } catch {
        // Invalid token, allow login page
      }
    }
    return NextResponse.next();
  }

  // Protect all other routes
  if (!token) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", request.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Check if user is admin (basic check, backend will verify)
  try {
    // JWT payload structure: { sub, workspace_id, global_role }
    const base64Url = token.split(".")[1];
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
    const payload = JSON.parse(Buffer.from(base64, "base64").toString());
    // Check global_role at top level (not nested under user)
    if (payload?.global_role !== "admin") {
      const loginUrl = new URL("/login", request.url);
      return NextResponse.redirect(loginUrl);
    }
  } catch {
    // Invalid token, redirect to login
    const loginUrl = new URL("/login", request.url);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
