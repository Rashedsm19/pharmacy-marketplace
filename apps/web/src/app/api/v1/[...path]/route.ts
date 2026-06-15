import { NextRequest, NextResponse } from "next/server";

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
  "host",
  "content-length",
  "content-encoding",
  "accept-encoding",
]);

function apiBaseUrl() {
  const configuredUrl =
    process.env.API_URL ??
    (process.env.NEXT_PUBLIC_API_URL?.startsWith("http")
      ? process.env.NEXT_PUBLIC_API_URL
      : undefined) ??
    (process.env.NODE_ENV === "production" ? undefined : "http://localhost:8000/api/v1");

  if (!configuredUrl) {
    return null;
  }

  const trimmedUrl = configuredUrl.replace(/\/+$/, "");
  return trimmedUrl.endsWith("/api/v1") ? trimmedUrl : `${trimmedUrl}/api/v1`;
}

function filteredHeaders(headers: Headers) {
  const nextHeaders = new Headers(headers);
  HOP_BY_HOP_HEADERS.forEach((header) => nextHeaders.delete(header));
  return nextHeaders;
}

async function proxy(request: NextRequest, context: RouteContext) {
  const baseUrl = apiBaseUrl();

  if (!baseUrl) {
    return NextResponse.json(
      { detail: "API_URL is not configured" },
      { status: 503 }
    );
  }

  const { path } = await context.params;
  const targetUrl = new URL(`${baseUrl}/${path.map(encodeURIComponent).join("/")}`);
  targetUrl.search = request.nextUrl.search;

  const init: RequestInit = {
    method: request.method,
    headers: filteredHeaders(request.headers),
    redirect: "manual",
    cache: "no-store",
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.arrayBuffer();
  }

  const response = await fetch(targetUrl, init);
  const responseHeaders = filteredHeaders(response.headers);

  return new NextResponse(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: responseHeaders,
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const HEAD = proxy;
export const OPTIONS = proxy;
