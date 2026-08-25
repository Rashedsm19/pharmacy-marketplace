/**
 * Telling the user what actually went wrong.
 *
 * "فشل تسجيل الدخول" for both a wrong password and a server that never answered
 * sends people looking for the wrong problem — it cost us an hour of doubting a
 * password that was correct the whole time. These cases need different words
 * because they need different actions: check what you typed, wait and retry, or
 * send us the request id.
 *
 * That first fix was not enough. On 2026-08-25 a sign-in showed "بيانات الدخول
 * غير صحيحة" next to HTTP 429, and the owner spent the next attempts doubting a
 * password that was correct. The server logs settled it: our own throttle never
 * fired once, and during that window not a single login request reached the API
 * at all. The 429 came from the edge in front of it while the service was waking
 * from a deploy, and an edge answers with HTML — not our `{"detail": …}`. With no
 * detail to read, the old code fell through to the caller's fallback, and the
 * caller on that screen had passed a message about credentials.
 *
 * So the rule now: **the caller's fallback is only ever shown for a genuine
 * authentication answer from our own API.** Anything the application did not
 * write is reported as what it is — infrastructure — and never as a judgement
 * about what the person typed.
 */
import { AxiosError, type AxiosResponse } from "axios";

export type FailureKind =
  | "offline"      // the browser has no network at all
  | "unreachable"  // the request never got an answer (server asleep, DNS, CORS)
  | "timeout"      // it answered too slowly
  | "throttled"    // too many requests, from our throttle or from the edge
  | "gateway"      // something answered, but it was not our application
  | "auth"         // the server answered, and said no
  | "server"       // the server answered, and broke
  | "client";      // the server answered, and it was our request

export type Failure = {
  kind: FailureKind;
  /** What to show the person. */
  message: string;
  /** The next thing for them to do, when there is one. */
  hint?: string;
  status?: number;
  /** Correlation id from the API, so a report can be traced to one request. */
  requestId?: string;
  /** Whether trying again in a moment is likely to work. */
  retryable: boolean;
  /**
   * False when the body did not come from our API. Kept on the object so a
   * screen can tell an application error from an infrastructure one without
   * re-parsing the response, and so this is visible while debugging.
   */
  fromApi: boolean;
};

/** Our API answers every error with `{"detail": "..."}`. Nothing else does. */
function apiDetail(response: AxiosResponse<{ detail?: unknown }>): string | undefined {
  const detail = response.data?.detail;
  if (typeof detail !== "string") return undefined;
  const trimmed = detail.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

/** "بعد 3 دقائق" — Arabic needs the dual and the small plural, not a bare number. */
function arabicMinutes(count: number): string {
  if (count <= 1) return "دقيقة";
  if (count === 2) return "دقيقتين";
  if (count <= 10) return `${count} دقائق`;
  return `${count} دقيقة`;
}

function retryAfterHint(response: AxiosResponse): string | undefined {
  const raw = response.headers?.["retry-after"];
  const seconds = Number(raw);
  if (!Number.isFinite(seconds) || seconds <= 0) return undefined;
  return `أعد المحاولة بعد ${arabicMinutes(Math.ceil(seconds / 60))}.`;
}

/** Said on every failure that is not about the password, so nobody doubts theirs. */
const CREDENTIALS_ARE_FINE = "بياناتك التي أدخلتها سليمة.";

export function describeError(error: unknown, fallback: string): Failure {
  const axiosError = error as AxiosError<{ detail?: unknown }>;
  const response = axiosError?.response;
  const requestId =
    (response?.headers?.["x-request-id"] as string | undefined) ?? undefined;

  // No response at all: the request never completed.
  if (!response) {
    if (typeof navigator !== "undefined" && navigator.onLine === false) {
      return {
        kind: "offline",
        message: "لا يوجد اتصال بالإنترنت",
        hint: "تحقق من اتصالك ثم أعد المحاولة.",
        retryable: true,
        fromApi: false,
      };
    }
    if (axiosError?.code === "ECONNABORTED" || axiosError?.code === "ETIMEDOUT") {
      return {
        kind: "timeout",
        message: "الخادم لم يستجب في الوقت المتوقع",
        hint:
          "الخدمة قد تكون في وضع الخمول وتحتاج لحظات لتستيقظ — أعد المحاولة بعد دقيقة. " +
          CREDENTIALS_ARE_FINE,
        retryable: true,
        fromApi: false,
      };
    }
    return {
      kind: "unreachable",
      message: "تعذر الوصول إلى الخادم",
      hint:
        "لم يصل رد من الخادم. قد يكون قيد التحديث أو في وضع الخمول — أعد المحاولة بعد لحظات. " +
        CREDENTIALS_ARE_FINE,
      retryable: true,
      fromApi: false,
    };
  }

  const status = response.status;
  const detail = apiDetail(response);
  const fromApi = detail !== undefined;

  // Checked before anything else: a 429 is a rate limit whether it came from our
  // throttle or from the edge, and it is never a statement about credentials.
  if (status === 429) {
    return {
      kind: "throttled",
      message: detail ?? "محاولات كثيرة خلال وقت قصير",
      hint:
        (retryAfterHint(response) ?? "انتظر قليلا ثم أعد المحاولة.") +
        ` ${CREDENTIALS_ARE_FINE}`,
      status,
      requestId,
      retryable: true,
      fromApi,
    };
  }

  // The body is not ours, so the application never saw this request. Report the
  // layer in front of it — never the caller's fallback, which is about the form.
  if (!fromApi) {
    const waking = status === 502 || status === 503 || status === 504;
    return {
      kind: "gateway",
      message: waking ? "الخدمة غير متاحة حاليا" : "رد غير متوقع من الخادم",
      hint:
        (waking
          ? "قد تكون قيد التحديث أو تستيقظ من الخمول — أعد المحاولة بعد لحظات. "
          : `الرد لم يأت من التطبيق نفسه (HTTP ${status}). أعد المحاولة، وإن تكرر أرسل لنا هذا الرمز. `) +
        CREDENTIALS_ARE_FINE,
      status,
      requestId,
      retryable: true,
      fromApi,
    };
  }

  if (status === 401 || status === 403) {
    return {
      kind: "auth",
      message: detail ?? fallback,
      status,
      requestId,
      retryable: false,
      fromApi,
    };
  }
  if (status >= 500) {
    return {
      kind: "server",
      message: "حدث خطأ في الخادم",
      hint: requestId
        ? `أعد المحاولة، وإن تكرر أرسل لنا رقم الطلب: ${requestId}`
        : "أعد المحاولة، وإن تكرر تواصل مع الدعم.",
      status,
      requestId,
      retryable: true,
      fromApi,
    };
  }
  return {
    kind: "client",
    message: detail,
    status,
    requestId,
    retryable: false,
    fromApi,
  };
}

/** A single line suitable for a toast. */
export function errorMessage(error: unknown, fallback: string): string {
  const failure = describeError(error, fallback);
  return failure.hint ? `${failure.message} — ${failure.hint}` : failure.message;
}
