import { describe, expect, it, vi } from "vitest";

import { describeError, diagnosticsLine, errorMessage, type Failure } from "./errors";

/**
 * These tests exist because the sign-in screen twice told someone their password
 * was wrong when it was not. Each case names the layer that answered and asserts
 * we describe that layer — not the form.
 */

const FALLBACK = "بيانات الدخول غير صحيحة";

/** An axios-shaped rejection. Axios lowercases response header keys. */
const res = (
  status: number,
  data: unknown,
  headers: Record<string, string> = {},
): unknown => ({ response: { status, data, headers } });

describe("proxy-generated responses (provenance by header)", () => {
  it("reports a backend outage as infrastructure and keeps the proxy's Arabic text", () => {
    const f = describeError(
      res(
        502,
        { detail: "تعذر الوصول إلى الخادم. حاول مرة أخرى بعد قليل." },
        { "x-api-proxy-error": "upstream-unreachable" },
      ),
      FALLBACK,
    );
    expect(f.kind).toBe("gateway");
    expect(f.message).toBe("تعذر الوصول إلى الخادم. حاول مرة أخرى بعد قليل.");
    expect(f.retryable).toBe(true);
    expect(f.fromApi).toBe(false);
  });

  it("does not offer retry for a missing configuration", () => {
    const f = describeError(
      res(503, { detail: "الخدمة غير مهيأة بشكل صحيح. تواصل مع الدعم الفني." }, {
        "x-api-proxy-error": "not-configured",
      }),
      FALLBACK,
    );
    expect(f.kind).toBe("gateway");
    expect(f.retryable).toBe(false);
  });

  it("prefers the proxy marker over the status-based guess", () => {
    // Without the header this 502 body would have been read as ours.
    const f = describeError(res(502, { detail: "x" }), FALLBACK);
    expect(f.kind).toBe("server");
  });
});

describe("rate limiting", () => {
  it("classifies an edge 429 with an HTML body and computes the wait", () => {
    const f = describeError(
      res(429, "<html>Too Many Requests</html>", { "retry-after": "120" }),
      FALLBACK,
    );
    expect(f.kind).toBe("throttled");
    expect(f.hint).toContain("دقيقتين");
    expect(f.fromApi).toBe(false);
  });

  it("shows exactly one duration when the message already carries it", () => {
    const f = describeError(
      res(429, { detail: "محاولات كثيرة خلال وقت قصير. حاول مرة اخرى بعد 6 دقائق." }, {
        "retry-after": "301",
      }),
      FALLBACK,
    );
    expect(f.kind).toBe("throttled");
    // The boundary that used to disagree: floor(301/60)=5 in the message,
    // ceil(301/60)=6 appended by the old hint.
    expect(f.hint).not.toMatch(/\d/);
    expect(f.message).toContain("6 دقائق");
  });

  it("uses the Arabic dual and small plural, never a bare singular", () => {
    const at = (seconds: string) =>
      describeError(res(429, "<html/>", { "retry-after": seconds }), FALLBACK).hint;
    expect(at("30")).toContain("دقيقة");
    expect(at("61")).toContain("دقيقتين");
    expect(at("301")).toContain("6 دقائق");
  });

  it("falls back to a wordless wait when Retry-After is absent or junk", () => {
    expect(describeError(res(429, "<html/>"), FALLBACK).hint).toContain("انتظر قليلا");
    expect(
      describeError(res(429, "<html/>", { "retry-after": "nonsense" }), FALLBACK).hint,
    ).toContain("انتظر قليلا");
  });
});

describe("application answers", () => {
  it("shows the API's own message for a real credential failure", () => {
    const f = describeError(
      res(401, { detail: "البريد الإلكتروني أو كلمة المرور غير صحيحة" }),
      FALLBACK,
    );
    expect(f.kind).toBe("auth");
    expect(f.message).toBe("البريد الإلكتروني أو كلمة المرور غير صحيحة");
    expect(f.retryable).toBe(false);
  });

  it("uses the caller's fallback only when our API sends a 401 with no detail", () => {
    const f = describeError(res(401, {}), FALLBACK);
    expect(f.kind).toBe("auth");
    expect(f.message).toBe(FALLBACK);
  });

  it("keeps a structured 422 an application error and surfaces its reasons", () => {
    const f = describeError(
      res(422, {
        detail: "تعذر نشر الدفعة: لم تجتز شروط الأهلية.",
        reasons: ["الدفعة مفتوحة", "المنتج مقيد"],
      }),
      FALLBACK,
    );
    expect(f.kind).toBe("client");
    expect(f.fromApi).toBe(true);
    expect(f.retryable).toBe(false);
    expect(f.reasons).toEqual(["الدفعة مفتوحة", "المنتج مقيد"]);
  });

  it("still reads a legacy object detail without rendering the object", () => {
    const f = describeError(
      res(422, { detail: { message: "فشل الفحص", reasons: ["سبب"] } }),
      FALLBACK,
    );
    expect(f.kind).toBe("client");
    expect(f.message).toBe("فشل الفحص");
    expect(f.reasons).toEqual(["سبب"]);
  });

  it("unwraps FastAPI's array detail", () => {
    const f = describeError(
      res(422, { detail: [{ loc: ["body", "email"], msg: "value is not a valid email address" }] }),
      FALLBACK,
    );
    expect(f.kind).toBe("client");
    expect(f.message).toBe("value is not a valid email address");
  });

  it("never renders an unrecognised object, and never calls it infrastructure", () => {
    const f = describeError(res(400, { detail: { unexpected: true } }), FALLBACK);
    expect(f.fromApi).toBe(true);
    expect(f.kind).toBe("client");
    expect(f.message).not.toContain("object");
    expect(f.message).not.toContain("[");
  });

  it("treats a blob body as ours but opaque, not as a gateway fault", () => {
    const f = describeError(res(400, new Blob(["{}"])), FALLBACK);
    expect(f.fromApi).toBe(true);
    expect(f.kind).toBe("client");
  });

  it("keeps the request id on a server error", () => {
    const f = describeError(res(500, { detail: "x" }, { "x-request-id": "abc123" }), FALLBACK);
    expect(f.kind).toBe("server");
    expect(f.requestId).toBe("abc123");
    expect(f.hint).toContain("abc123");
  });
});

describe("foreign answers", () => {
  it("reports a WAF 403 as infrastructure rather than a rejected login", () => {
    const f = describeError(res(403, "<html>Forbidden</html>"), FALLBACK);
    expect(f.kind).toBe("gateway");
    expect(f.fromApi).toBe(false);
  });

  it("reports an edge 503 as a service that may be waking", () => {
    const f = describeError(res(503, "<html/>"), FALLBACK);
    expect(f.kind).toBe("gateway");
    expect(f.message).toBe("الخدمة غير متاحة حاليا");
  });
});

describe("no response at all", () => {
  it("distinguishes timeout from unreachable", () => {
    expect(describeError({ code: "ECONNABORTED" }, FALLBACK).kind).toBe("timeout");
    expect(describeError({ code: "ERR_NETWORK" }, FALLBACK).kind).toBe("unreachable");
  });

  it("reports a browser with no connection as offline", () => {
    vi.stubGlobal("navigator", { onLine: false });
    try {
      expect(describeError({ code: "ERR_NETWORK" }, FALLBACK).kind).toBe("offline");
    } finally {
      vi.unstubAllGlobals();
    }
  });
});

describe("the invariant", () => {
  const everyNonAuthCase: unknown[] = [
    res(502, { detail: "x" }, { "x-api-proxy-error": "upstream-unreachable" }),
    res(503, { detail: "x" }, { "x-api-proxy-error": "not-configured" }),
    res(429, "<html/>", { "retry-after": "120" }),
    res(429, { detail: "محاولات كثيرة" }),
    res(403, "<html/>"),
    res(503, "<html/>"),
    res(500, { detail: "x" }),
    res(422, { detail: "x", reasons: ["y"] }),
    res(400, new Blob(["{}"])),
    { code: "ERR_NETWORK" },
    { code: "ECONNABORTED" },
  ];

  it("never shows the credentials message outside a genuine auth answer", () => {
    for (const error of everyNonAuthCase) {
      const f = describeError(error, FALLBACK);
      expect(f.kind).not.toBe("auth");
      expect(f.message).not.toContain(FALLBACK);
      expect(f.hint ?? "").not.toContain(FALLBACK);
    }
  });

  it("reassures about the input whenever the input cannot be the cause", () => {
    // Deliberately not every kind. `client` is the application rejecting what was
    // submitted — telling that person their input was fine would be a lie — and
    // `server` points at the request id, which is the actionable thing there.
    const cannotBeTheInput = new Set(["offline", "unreachable", "timeout", "throttled", "gateway"]);
    const seen = new Set<string>();

    vi.stubGlobal("navigator", { onLine: false });
    const offline = describeError({ code: "ERR_NETWORK" }, FALLBACK);
    vi.unstubAllGlobals();

    for (const f of [...everyNonAuthCase.map((e) => describeError(e, FALLBACK)), offline]) {
      seen.add(f.kind);
      if (!cannotBeTheInput.has(f.kind)) continue;
      expect(f.hint ?? "").toContain("بياناتك التي أدخلتها سليمة.");
    }

    // Guards the guard: if a refactor stopped producing these kinds, the loop
    // above would pass by covering nothing.
    for (const kind of cannotBeTheInput) expect(seen).toContain(kind);
  });
});

describe("diagnosticsLine", () => {
  const base: Failure = {
    kind: "offline",
    message: "x",
    retryable: true,
    fromApi: false,
  };

  it("shows nothing when there is no status and no request id", () => {
    expect(diagnosticsLine(base)).toBeNull();
    expect(diagnosticsLine({ ...base, kind: "unreachable" })).toBeNull();
  });

  it("shows the layer and status when there is a status", () => {
    expect(diagnosticsLine({ ...base, kind: "gateway", status: 502 })).toBe(
      "gateway · HTTP 502 · not-from-api",
    );
  });

  it("omits not-from-api when the answer was ours", () => {
    expect(diagnosticsLine({ ...base, kind: "auth", status: 401, fromApi: true })).toBe(
      "auth · HTTP 401",
    );
  });

  it("shows a request id even without a status", () => {
    expect(diagnosticsLine({ ...base, requestId: "abc123" })).toBe("offline · abc123");
  });

  it("shows both when both are present", () => {
    expect(
      diagnosticsLine({ ...base, kind: "server", status: 500, requestId: "abc", fromApi: true }),
    ).toBe("server · HTTP 500 · abc");
  });
});

describe("errorMessage", () => {
  it("folds reasons into the single toast line", () => {
    const line = errorMessage(
      res(422, { detail: "تعذر نشر الدفعة", reasons: ["الدفعة مفتوحة", "المنتج مقيد"] }),
      FALLBACK,
    );
    expect(line).toContain("تعذر نشر الدفعة");
    expect(line).toContain("الدفعة مفتوحة");
    expect(line).toContain("المنتج مقيد");
  });
});
