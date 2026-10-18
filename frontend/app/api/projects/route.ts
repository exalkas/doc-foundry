import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

async function proxyRequest(request: NextRequest, method: string, body?: any) {
  const token = request.cookies.get("auth_token")?.value;
  const workspaceId = request.headers.get("X-Workspace-Id");

  const headers: HeadersInit = {
    "Content-Type": "application/json",
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  if (workspaceId) {
    headers["X-Workspace-Id"] = workspaceId;
  }

  const response = await fetch(`${BACKEND_URL}/api/projects`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    return NextResponse.json(
      { error: "Request failed" },
      { status: response.status }
    );
  }

  const data = await response.json();
  return NextResponse.json(data);
}

export async function GET(request: NextRequest) {
  return proxyRequest(request, "GET");
}

export async function POST(request: NextRequest) {
  const body = await request.json();
  return proxyRequest(request, "POST", body);
}
