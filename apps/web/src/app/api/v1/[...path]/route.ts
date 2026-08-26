import { NextRequest, NextResponse } from "next/server";

import { apiBaseUrl } from "@/lib/api-base-url";

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

/**
 * Marks a response this route generated ITSELF, rather than one it forwarded.
 *
 * Without it the two are indistinguishable to the client: both arrive as JSON
 * with a `detail` string, because that is the shape this application uses. So a
 * backend outage — the proxy's own 502 — was read as an answer from the API and
 * reported as a generic server error, with the Arabic text explaining the outage
 * thrown away. Provenance has to be carried; it cannot be inferred from a body
 * that was deliberately made to look the same.
 *
 * Only ever set on the two responses below. A forwarded response is untouched.
 */
const PROXY_ERROR_HEADER = "X-Api-Proxy-Error";

function filteredHeaders(headers: Headers) {
  const nextHeaders = new Headers(headers);
  HOP_BY_HOP_HEADERS.forEach((header) => nextHeaders.delete(header));
  return nextHeaders;
}

async function proxy(request: NextRequest, context: RouteContext) {
  const baseUrl = apiBaseUrl();

  if (!baseUrl) {
    // Arabic, because this reaches a person on the sign-in screen. The English
    // cause goes in the header and the server log, where the person who can act
    // on it will look — it is a deployment fault, not something a user can fix,
    // which is why this one is not retryable.
    console.error("[api-proxy] API_URL is not configured — no upstream to forward to");
    return NextResponse.json(
      { detail: "الخدمة غير مهيأة بشكل صحيح. تواصل مع الدعم الفني." },
      { status: 503, headers: { [PROXY_ERROR_HEADER]: "not-configured" } }
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
    { status: 502, headers: { [PROXY_ERROR_HEADER]: "upstream-unreachable" } }
  );
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const HEAD = proxy;
export const OPTIONS = proxy;
