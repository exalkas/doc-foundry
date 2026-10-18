import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export async function GET(request: NextRequest) {
  try {
    const token = request.cookies.get("auth_token")?.value;
    const workspaceId = request.headers.get("X-Workspace-Id");

    if (!token) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const headers: HeadersInit = {
      Authorization: `Bearer ${token}`,
    };

    if (workspaceId) {
      headers["X-Workspace-Id"] = workspaceId;
    }

    const response = await fetch(`${BACKEND_URL}/api/usage/summary`, {
      headers,
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: "Failed to fetch usage" },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Usage summary error:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
