import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

export const runtime = "nodejs";

/**
 * Proxy all /api/* requests to the FastAPI backend.
 * App Router often does not apply next.config rewrites reliably for client fetch();
 * this route makes same-origin /api/... calls work from the browser.
 */
const backendBase = () =>
  (
    process.env.BACKEND_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000"
  ).replace(/\/$/, "");

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
  "host",
]);

async function proxy(request: NextRequest, pathSegments: string[] | undefined) {
  const suffix = pathSegments?.length ? pathSegments.join("/") : "";
  const base = backendBase();
  const url = `${base}/api/${suffix}${request.nextUrl.search}`;

  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });

  const method = request.method;
  const hasBody = method !== "GET" && method !== "HEAD";

  const init: RequestInit & { duplex?: string } = {
    method,
    headers,
    redirect: "manual",
  };
  if (hasBody && request.body) {
    init.body = request.body;
    init.duplex = "half";
  }

  let upstream: Response;
  try {
    upstream = await fetch(url, init);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json(
      {
        detail:
          `Admin proxy could not reach the FastAPI backend at ${base}. ` +
          `Start it (e.g. uvicorn on that host/port) and confirm GET ${base}/health returns {"status":"ok"}. ` +
          `Underlying error: ${msg}`,
      },
      { status: 502, headers: { "X-Admin-Proxy-Error": "upstream-unreachable" } },
    );
  }

  const outHeaders = new Headers();
  upstream.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) {
      outHeaders.set(key, value);
    }
  });

  outHeaders.set("X-Proxied-From", base);

  return new NextResponse(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: outHeaders,
  });
}

type RouteCtx = { params: { path?: string[] } };

export async function GET(request: NextRequest, ctx: RouteCtx) {
  return proxy(request, ctx.params.path);
}

export async function POST(request: NextRequest, ctx: RouteCtx) {
  return proxy(request, ctx.params.path);
}

export async function PUT(request: NextRequest, ctx: RouteCtx) {
  return proxy(request, ctx.params.path);
}

export async function PATCH(request: NextRequest, ctx: RouteCtx) {
  return proxy(request, ctx.params.path);
}

export async function DELETE(request: NextRequest, ctx: RouteCtx) {
  return proxy(request, ctx.params.path);
}

export async function OPTIONS(request: NextRequest, ctx: RouteCtx) {
  return proxy(request, ctx.params.path);
}
