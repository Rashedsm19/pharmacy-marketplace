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

  // The API sleeps on the free plan, so the first request after an idle period can
  // be refused or dropped while it wakes. Without a retry the fetch throws and
  // Next answers with a bare "Internal Server Error" that tells the user nothing.
  //
  // But only a read may be retried. A write that timed out may well have been
  // received and committed — the timeout says nothing about whether the server
  // acted — and replaying it turned one submitted offer into three, one
  // inventory import into three (tripling a pharmacy's stock), and one completed
  // transaction into duplicate tax invoices. Nothing in the API is idempotent,
  // so the retry has to stop at the methods that are idempotent by definition.
  const isRead = request.method === "GET" || request.method === "HEAD";
  const MAX_ATTEMPTS = isRead ? 3 : 1;
  let lastError: unknown;

  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    try {
      const response = await fetch(targetUrl, {
        ...init,
        signal: AbortSignal.timeout(60_000),
      });
      return new NextResponse(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers: filteredHeaders(response.headers),
      });
    } catch (error) {
      lastError = error;
      if (attempt < MAX_ATTEMPTS) {
        await new Promise((resolve) => setTimeout(resolve, attempt * 1500));
      }
    }
  }

  console.error(`[api-proxy] ${request.method} ${targetUrl.pathname} failed`, lastError);
  return NextResponse.json(
    { detail: "تعذر الوصول إلى الخادم. حاول مرة أخرى بعد قليل." },
    { status: 502 }
  );
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const HEAD = proxy;
export const OPTIONS = proxy;
