/**
 * Where the proxy route forwards to, server-side.
 *
 * Lifted out of the route module so it can be tested: a Next route file may only
 * export route handlers and a few known config keys, so an exported helper there
 * is not reachable from a test.
 *
 * The rule that matters here is that **an empty string is not a configured
 * value**. `.env.example` shipped `API_URL=` and the old code used `??`, which
 * falls through on `undefined` but not on `""` — so the empty string won a
 * comparison it should have lost, suppressed the localhost fallback below, and
 * every `/api/v1/*` call answered 503. Anyone who followed the file's own
 * instructions and copied it got a dead application.
 */

/** First value that is actually set — empty and whitespace-only count as unset. */
function firstConfigured(...values: (string | undefined)[]): string | undefined {
  for (const value of values) {
    const trimmed = value?.trim();
    if (trimmed) return trimmed;
  }
  return undefined;
}

export type ApiBaseUrlEnv = {
  API_URL?: string;
  NEXT_PUBLIC_API_URL?: string;
  NODE_ENV?: string;
};

/**
 * Resolve the upstream API base, or `null` when there is nothing to forward to.
 *
 * Takes the environment as an argument so a test can vary it without mutating
 * `process.env`; defaults to the real one for the route module.
 */
export function apiBaseUrl(env: ApiBaseUrlEnv = process.env): string | null {
  const publicUrl = env.NEXT_PUBLIC_API_URL?.trim();

  const configuredUrl = firstConfigured(
    env.API_URL,
    // A relative NEXT_PUBLIC_API_URL points at this proxy — following it would
    // make the proxy forward to itself.
    publicUrl?.startsWith("http") ? publicUrl : undefined,
    // No upstream is guessable in a deployment; on a developer machine it is.
    env.NODE_ENV === "production" ? undefined : "http://localhost:8000/api/v1",
  );

  if (!configuredUrl) return null;

  const trimmedUrl = configuredUrl.replace(/\/+$/, "");
  return trimmedUrl.endsWith("/api/v1") ? trimmedUrl : `${trimmedUrl}/api/v1`;
}
