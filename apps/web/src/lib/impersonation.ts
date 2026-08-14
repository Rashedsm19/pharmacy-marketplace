/**
 * Entering and leaving a customer's account.
 *
 * The support session lives in the same cookies the app already reads, so every
 * screen works unchanged. What matters is the way back: the administrator's own
 * tokens are put aside first, and leaving restores them. That has to work even
 * when the support token has already expired — otherwise a session that times
 * out would strand the administrator at the login page.
 *
 * The refresh token is deliberately removed while a session is open. The axios
 * client retries any 401 by refreshing, and mid-session that would mint an
 * administrator token and replay the customer's request as the platform.
 */
import Cookies from "js-cookie";

const SAVED_ACCESS = "support.saved_access";
const SAVED_REFRESH = "support.saved_refresh";
const SESSION = "support.session";

export type ImpersonationState = {
  sessionId: string;
  organizationName: string;
  userEmail: string;
  expiresAt: string;
};

export function beginImpersonation(
  token: string,
  state: ImpersonationState
): void {
  if (typeof window === "undefined") return;
  const access = Cookies.get("access_token");
  const refresh = Cookies.get("refresh_token");
  if (access) sessionStorage.setItem(SAVED_ACCESS, access);
  if (refresh) sessionStorage.setItem(SAVED_REFRESH, refresh);
  sessionStorage.setItem(SESSION, JSON.stringify(state));

  Cookies.set("access_token", token, { expires: 1 / 24, sameSite: "strict" });
  // No refresh while impersonating: a silent refresh would swap the customer's
  // session for the administrator's and replay the request as the platform.
  Cookies.remove("refresh_token");
}

export function currentImpersonation(): ImpersonationState | null {
  if (typeof window === "undefined") return null;
  const raw = sessionStorage.getItem(SESSION);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as ImpersonationState;
  } catch {
    return null;
  }
}

export function endImpersonation(): void {
  if (typeof window === "undefined") return;
  const access = sessionStorage.getItem(SAVED_ACCESS);
  const refresh = sessionStorage.getItem(SAVED_REFRESH);

  sessionStorage.removeItem(SESSION);
  sessionStorage.removeItem(SAVED_ACCESS);
  sessionStorage.removeItem(SAVED_REFRESH);

  if (access) Cookies.set("access_token", access, { expires: 1 / 48, sameSite: "strict" });
  else Cookies.remove("access_token");
  if (refresh) Cookies.set("refresh_token", refresh, { expires: 7, sameSite: "strict" });
}
