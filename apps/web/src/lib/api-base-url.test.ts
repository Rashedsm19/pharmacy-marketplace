import { describe, expect, it } from "vitest";

import { apiBaseUrl } from "./api-base-url";

/**
 * The regression these guard: `.env.example` shipped `API_URL=`, and `??` does
 * not fall through on an empty string. Copying the example file exactly as its
 * own instructions said produced a 503 on every API call.
 */

describe("apiBaseUrl", () => {
  it("falls back to localhost in development when nothing is set", () => {
    expect(apiBaseUrl({ NODE_ENV: "development" })).toBe("http://localhost:8000/api/v1");
  });

  it("treats an empty API_URL as unset, not as a configured value", () => {
    expect(apiBaseUrl({ API_URL: "", NODE_ENV: "development" })).toBe(
      "http://localhost:8000/api/v1",
    );
  });

  it("treats a whitespace-only API_URL as unset", () => {
    expect(apiBaseUrl({ API_URL: "   ", NODE_ENV: "development" })).toBe(
      "http://localhost:8000/api/v1",
    );
  });

  it("uses API_URL when it is actually set", () => {
    expect(apiBaseUrl({ API_URL: "https://api.example.com/api/v1" })).toBe(
      "https://api.example.com/api/v1",
    );
  });

  it("appends /api/v1 when the configured host omits it", () => {
    expect(apiBaseUrl({ API_URL: "https://api.example.com" })).toBe(
      "https://api.example.com/api/v1",
    );
  });

  it("is idempotent about trailing slashes", () => {
    expect(apiBaseUrl({ API_URL: "https://api.example.com/api/v1///" })).toBe(
      "https://api.example.com/api/v1",
    );
  });

  it("accepts an absolute NEXT_PUBLIC_API_URL as the upstream", () => {
    expect(
      apiBaseUrl({ NEXT_PUBLIC_API_URL: "http://localhost:8000/api/v1", NODE_ENV: "production" }),
    ).toBe("http://localhost:8000/api/v1");
  });

  it("ignores a relative NEXT_PUBLIC_API_URL, which points back at this proxy", () => {
    expect(apiBaseUrl({ NEXT_PUBLIC_API_URL: "/api/v1", NODE_ENV: "production" })).toBeNull();
  });

  it("returns null in production when there is nothing to forward to", () => {
    expect(apiBaseUrl({ NODE_ENV: "production" })).toBeNull();
    expect(apiBaseUrl({ API_URL: "", NODE_ENV: "production" })).toBeNull();
  });

  it("prefers API_URL over an absolute NEXT_PUBLIC_API_URL", () => {
    expect(
      apiBaseUrl({
        API_URL: "https://internal.example.com/api/v1",
        NEXT_PUBLIC_API_URL: "https://public.example.com/api/v1",
      }),
    ).toBe("https://internal.example.com/api/v1");
  });
});
