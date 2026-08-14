/**
 * Telling the user what actually went wrong.
 *
 * "فشل تسجيل الدخول" for both a wrong password and a server that never answered
 * sends people looking for the wrong problem — it cost us an hour of doubting a
 * password that was correct the whole time. These four cases need different
 * words because they need different actions: check what you typed, wait and
 * retry, or send us the request id.
 */
import { AxiosError } from "axios";

export type FailureKind =
  | "offline"      // the browser has no network at all
  | "unreachable"  // the request never got an answer (server asleep, DNS, CORS)
  | "timeout"      // it answered too slowly
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
};

export function describeError(error: unknown, fallback: string): Failure {
  const axiosError = error as AxiosError<{ detail?: string }>;
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
      };
    }
    if (axiosError?.code === "ECONNABORTED") {
      return {
        kind: "timeout",
        message: "الخادم لم يستجب في الوقت المتوقع",
        hint:
          "الخدمة قد تكون في وضع الخمول وتحتاج لحظات لتستيقظ — أعد المحاولة بعد دقيقة.",
        retryable: true,
      };
    }
    return {
      kind: "unreachable",
      message: "تعذر الوصول إلى الخادم",
      hint:
        "لم يصل رد من الخادم. قد يكون قيد التحديث أو في وضع الخمول — أعد المحاولة بعد لحظات. " +
        "بياناتك التي أدخلتها سليمة.",
      retryable: true,
    };
  }

  const status = response.status;
  const detail = response.data?.detail;

  if (status === 401 || status === 403) {
    return {
      kind: "auth",
      message: detail ?? fallback,
      status,
      requestId,
      retryable: false,
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
    };
  }
  return {
    kind: "client",
    message: detail ?? fallback,
    status,
    requestId,
    retryable: false,
  };
}

/** A single line suitable for a toast. */
export function errorMessage(error: unknown, fallback: string): string {
  const failure = describeError(error, fallback);
  return failure.hint ? `${failure.message} — ${failure.hint}` : failure.message;
}
