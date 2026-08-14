"use client";

/**
 * The reminder that you are inside someone else's account.
 *
 * It sits above everything, in a colour used nowhere else in the product, and
 * it does not scroll away. Support forgetting which account they are in is how
 * a customer's data gets changed by accident.
 */

import { useEffect, useState } from "react";
import { useLocale } from "next-intl";
import { Eye, LogOut } from "lucide-react";

import { adminApi } from "@/lib/api";
import {
  currentImpersonation,
  endImpersonation,
  type ImpersonationState,
} from "@/lib/impersonation";

export default function ImpersonationBanner() {
  const locale = useLocale();
  const [session, setSession] = useState<ImpersonationState | null>(null);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    setSession(currentImpersonation());
  }, []);

  if (!session) return null;

  const leave = async () => {
    setLeaving(true);
    try {
      // Close it server-side so the token dies rather than merely being
      // forgotten by this browser. A failure here must not trap the
      // administrator, so the local restore happens either way.
      await adminApi.endImpersonation(session.sessionId);
    } catch {
      /* the session may have expired already */
    }
    endImpersonation();
    // A full reload rather than a route change: the stored identity has to be
    // rebuilt from the restored token, not carried over from the customer.
    window.location.href = `/${locale}/admin/customers`;
  };

  return (
    <div className="sticky top-0 z-50 bg-[#7b2d26] text-white" dir="rtl">
      <div className="mx-auto max-w-[1400px] flex flex-wrap items-center justify-between gap-2 px-4 sm:px-6 py-2">
        <div className="flex items-center gap-2 min-w-0">
          <Eye className="h-4 w-4 shrink-0" />
          <span className="text-sm truncate">
            أنت تتصفّح حساب <strong>{session.organizationName}</strong> ({session.userEmail})
            — كل إجراء يُسجَّل باسمك
          </span>
        </div>
        <button
          type="button"
          onClick={leave}
          disabled={leaving}
          className="inline-flex items-center gap-1.5 h-8 px-4 rounded-full bg-white/15 hover:bg-white/25 text-sm font-medium disabled:opacity-60 shrink-0"
        >
          <LogOut className="h-3.5 w-3.5" />
          {leaving ? "جارٍ الخروج…" : "خروج من الحساب"}
        </button>
      </div>
    </div>
  );
}

export { ImpersonationBanner };
