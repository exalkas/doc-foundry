import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Decode JWT token payload without verification (for client-side role check only).
 * Backend will verify the token on API calls.
 */
function decodeJWT(
  token: string
): { role?: string; [key: string]: any } | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) {
      return null;
    }

    // Decode payload (second part)
    const payload = parts[1];
    // Add padding if needed for base64url decoding
    const paddedPayload = payload + "=".repeat((4 - (payload.length % 4)) % 4);
    const decoded = Buffer.from(
      paddedPayload.replace(/-/g, "+").replace(/_/g, "/"),
      "base64"
    ).toString("utf-8");
    return JSON.parse(decoded);
  } catch (error) {
    return null;
  }
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Check for auth token in cookies
  const token = request.cookies.get("auth_token")?.value;

  // Protect /app/* routes
  if (pathname.startsWith("/app")) {
    if (!token) {
      const loginUrl = new URL("/login", request.url);
      loginUrl.searchParams.set("redirect", pathname);
      return NextResponse.redirect(loginUrl);
    }
  }

  // Protect /admin routes (require admin role)
  if (pathname.startsWith("/admin")) {
    if (!token) {
      const loginUrl = new URL("/login", request.url);
      loginUrl.searchParams.set("redirect", pathname);
      return NextResponse.redirect(loginUrl);
    }

    // Decode token to check role
    const payload = decodeJWT(token);
    const userRole = payload?.role;

    // Only allow admin role to access admin routes
    if (userRole !== "admin") {
      // Redirect to app dashboard with error message
      const appUrl = new URL("/app", request.url);
      appUrl.searchParams.set("error", "unauthorized");
      return NextResponse.redirect(appUrl);
    }
  }

  // Allow public routes
  return NextResponse.next();
}

export const config = {
  matcher: ["/app/:path*", "/admin/:path*"],
};
