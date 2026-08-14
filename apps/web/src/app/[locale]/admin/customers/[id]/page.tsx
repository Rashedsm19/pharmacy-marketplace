"use client";

/**
 * One customer, and everything support can do for them.
 *
 * The layout follows a support call: who they are and whether the account
 * works, then their people with the actions that unblock a person, then their
 * stock and history. The destructive actions sit at the bottom behind typed
 * confirmation, because nothing here should be one stray click away.
 */

import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useLocale } from "next-intl";
import { toast } from "sonner";
import {
  ArrowRight,
  Check,
  Copy,
  Eye,
  KeyRound,
  Loader2,
  Power,
  Trash2,
  Upload,
} from "lucide-react";

import Shell from "@/components/layout/shell";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { KpiCard } from "@/components/ui/kpi-card";
import { adminApi, authApi } from "@/lib/api";
import { useAuthStore } from "@/lib/auth";
import { errorMessage } from "@/lib/errors";
import { beginImpersonation } from "@/lib/impersonation";
import { formatCurrency, formatDate } from "@/lib/utils";

type User = {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  membership_role?: string | null;
  last_login_at?: string | null;
};

const ZONE_LABEL: Record<string, string> = {
  expired: "منتهية",
  red: "أقل من ٣٠ يوما",
  orange: "٣٠ – ٩٠ يوما",
  yellow: "٩٠ – ١٨٠ يوما",
  green: "أكثر من ١٨٠ يوما",
};

const ZONE_STYLE: Record<string, string> = {
  expired: "bg-slate-800 text-white",
  red: "bg-red-50 text-red-700 ring-1 ring-inset ring-red-200",
  orange: "bg-orange-50 text-orange-700 ring-1 ring-inset ring-orange-200",
  yellow: "bg-amber-50 text-amber-800 ring-1 ring-inset ring-amber-200",
  green: "bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-200",
};

type Pending = {
  kind: "reset" | "impersonate" | "toggle" | "upload" | "reactivate" | "purge";
  userId?: string;
  active?: boolean;
  file?: File;
  title: string;
  hint: string;
  minimum: number;
};

export default function CustomerFilePage() {
  const params = useParams<{ id: string }>();
  const orgId = params.id;
  const locale = useLocale();
  const router = useRouter();
  const queryClient = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);

  const [issuedLink, setIssuedLink] = useState<{ url: string; email: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const [purgeName, setPurgeName] = useState("");
  // Every action asks why before it runs. Inline rather than a browser
  // dialog: the reason is stored in the audit trail, so it deserves a real
  // field the person can see and correct.
  const [pending, setPending] = useState<Pending | null>(null);
  const [reason, setReason] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["admin-customer", orgId],
    queryFn: () => adminApi.customer(orgId).then((r) => r.data),
  });

  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: ["admin-customer", orgId] });

  // One classifier for every action here, so "the server is asleep" never
  // reads as "the platform refused you".
  const fail = (fallback: string) => (error: unknown) =>
    toast.error(errorMessage(error, fallback));

  const resetLink = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      adminApi.resetLink(id, reason).then((r) => r.data),
    onSuccess: (result, variables) => {
      const user = data?.users?.find((u: User) => u.id === variables.id);
      setIssuedLink({ url: result.reset_url, email: user?.email ?? "" });
      toast.success(result.notice);
    },
    onError: fail("تعذر إصدار الرابط"),
  });

  const toggleUser = useMutation({
    mutationFn: ({ id, active, reason }: { id: string; active: boolean; reason: string }) =>
      active ? adminApi.deactivateUser(id, reason) : adminApi.activateUser(id, reason),
    onSuccess: () => {
      toast.success("تم تحديث الحساب");
      refresh();
    },
    onError: fail("تعذر تحديث الحساب"),
  });

  const impersonate = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      adminApi.impersonate(id, reason).then((r) => r.data),
    onSuccess: async (session) => {
      beginImpersonation(session.access_token, {
        sessionId: session.session_id,
        organizationName: session.organization_name,
        userEmail: session.user_email,
        expiresAt: session.expires_at,
      });
      // Swap the stored identity too, or the sidebar keeps offering platform
      // links that the customer's session cannot open.
      try {
        const me = await authApi.me();
        useAuthStore.getState().setUser({
          ...me.data,
          org_id: session.organization_id,
        });
      } catch {
        /* the banner and the token are what matter */
      }
      window.location.href = `/${locale}/dashboard`;
    },
    onError: fail("تعذر فتح جلسة التصفح"),
  });

  const uploadFor = useMutation({
    mutationFn: ({ file, reason }: { file: File; reason: string }) =>
      adminApi.importForCustomer(orgId, file, reason).then((r) => r.data),
    onSuccess: () => {
      toast.success("أدرج الملف في طابور المعالجة وأبلغ العميل");
      refresh();
    },
    onError: fail("تعذر رفع الملف"),
  });

  const reactivate = useMutation({
    mutationFn: (reason: string) => adminApi.reactivateOrg(orgId, reason),
    onSuccess: () => {
      toast.success("أعيد تفعيل المنشأة");
      refresh();
    },
    onError: fail("تعذر إعادة التفعيل"),
  });

  const purge = useMutation({
    mutationFn: ({ name, reason }: { name: string; reason: string }) =>
      adminApi.purgeOrg(orgId, name, reason).then((r) => r.data),
    onSuccess: (result) => {
      toast.success(result.message);
      router.push(`/${locale}/admin/customers`);
    },
    onError: fail("تعذر الحذف"),
  });

  const runPending = () => {
    if (!pending) return;
    const text = reason.trim();
    if (text.length < pending.minimum) {
      toast.error(`اكتب سببا لا يقل عن ${pending.minimum} أحرف — يحفظ في سجل التدقيق`);
      return;
    }
    switch (pending.kind) {
      case "reset":
        resetLink.mutate({ id: pending.userId!, reason: text });
        break;
      case "impersonate":
        impersonate.mutate({ id: pending.userId!, reason: text });
        break;
      case "toggle":
        toggleUser.mutate({
          id: pending.userId!,
          active: Boolean(pending.active),
          reason: text,
        });
        break;
      case "upload":
        uploadFor.mutate({ file: pending.file!, reason: text });
        break;
      case "reactivate":
        reactivate.mutate(text);
        break;
      case "purge":
        purge.mutate({ name: purgeName.trim(), reason: text });
        break;
    }
    setPending(null);
    setReason("");
  };

  if (isLoading) {
    return (
      <Shell>
        <p className="text-sm text-[#8a9089]">جار التحميل…</p>
      </Shell>
    );
  }
  if (!data) {
    return (
      <Shell>
        <p className="text-sm text-[#8a9089]">لم يعثر على المنشأة.</p>
      </Shell>
    );
  }

  const org = data.organization;
  const summary = data.summary;
  const zones = data.inventory_by_zone ?? {};

  return (
    <Shell>
      <div className="space-y-6">
        <PageHeader
          title={org.name_ar || org.name}
          subtitle={`${org.commercial_registration_number ?? "بلا سجل"} · ${org.city ?? "—"} · ${
            { approved: "معتمدة", pending: "قيد المراجعة", suspended: "موقوفة", rejected: "مرفوضة" }[
              org.status as string
            ] ?? org.status
          }`}
          actions={
            <Link
              href={`/${locale}/admin/customers`}
              className="inline-flex items-center gap-2 h-9 px-4 rounded-full text-sm ring-1 ring-inset ring-[#e1d3c0] text-[#5f665f] hover:bg-[#fbf7f0]"
            >
              <ArrowRight className="h-4 w-4" />
              كل العملاء
            </Link>
          }
        />

        {/* One place to state why, for whichever action was chosen. */}
        {pending && (
          <SectionCard className="ring-2 ring-brand-500" title={pending.title}>
            <label className="block text-sm text-[#5f665f] mb-2">{pending.hint}</label>
            <div className="flex flex-col sm:flex-row gap-2">
              <input
                autoFocus
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") runPending();
                  if (event.key === "Escape") {
                    setPending(null);
                    setReason("");
                  }
                }}
                placeholder="مثال: العميل اتصل بالدعم وطلب المساعدة"
                className="flex-1 h-11 px-4 rounded-xl bg-white ring-1 ring-inset ring-[#e1d3c0] text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              <button
                type="button"
                onClick={runPending}
                className="h-11 px-6 rounded-xl bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 shrink-0"
              >
                تأكيد
              </button>
              <button
                type="button"
                onClick={() => {
                  setPending(null);
                  setReason("");
                }}
                className="h-11 px-5 rounded-xl text-sm text-[#5f665f] hover:bg-[#fbf7f0] shrink-0"
              >
                إلغاء
              </button>
            </div>
          </SectionCard>
        )}

        {org.suspension_reason && (
          <div className="rounded-2xl bg-red-50 ring-1 ring-inset ring-red-200 px-5 py-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-red-800">
              <strong>المنشأة موقوفة:</strong> {org.suspension_reason} — مستخدموها لا
              يستطيعون الدخول.
            </p>
            <button
              type="button"
              onClick={() =>
                setPending({
                  kind: "reactivate",
                  title: "إعادة تفعيل المنشأة",
                  hint: "سبب إعادة التفعيل",
                  minimum: 5,
                })
              }
              className="h-9 px-4 rounded-full bg-brand-600 text-white text-sm font-medium hover:bg-brand-700"
            >
              إعادة التفعيل
            </button>
          </div>
        )}

        {/* The link is shown once, so it gets a panel rather than a toast. */}
        {issuedLink && (
          <SectionCard
            className="ring-2 ring-brand-500"
            title="رابط استعادة كلمة المرور"
            subtitle={`للحساب ${issuedLink.email} — صالح ٣٠ دقيقة`}
          >
            <p className="text-sm text-[#5f665f] mb-3">
              خدمة البريد غير مفعلة على هذا التثبيت، فانسخ الرابط وأرسله للعميل
              بنفسك. لن يعرض مرة أخرى.
            </p>
            <div className="flex flex-col sm:flex-row gap-2">
              <code
                dir="ltr"
                className="flex-1 px-4 py-3 rounded-xl bg-[#1f2a24] text-[#e8f0ea] text-xs font-mono break-all select-all"
              >
                {issuedLink.url}
              </code>
              <button
                type="button"
                onClick={async () => {
                  await navigator.clipboard.writeText(issuedLink.url);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 2500);
                }}
                className="inline-flex items-center justify-center gap-2 h-11 px-5 rounded-xl bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 shrink-0"
              >
                {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                {copied ? "تم النسخ" : "نسخ"}
              </button>
            </div>
            <button
              type="button"
              onClick={() => setIssuedLink(null)}
              className="mt-3 text-sm text-[#8a9089] hover:text-[#5f665f]"
            >
              أرسلته — أغلق
            </button>
          </SectionCard>
        )}

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard
            label="المستخدمون"
            value={`${summary.active_users} / ${summary.users}`}
            hint={`${summary.branches} فرع`}
            tone="brand"
          />
          <KpiCard
            label="التشغيلات"
            value={summary.batches.toLocaleString("ar-SA")}
            hint={formatCurrency(summary.stock_value)}
            tone="gold"
          />
          <KpiCard
            label="قرب الانتهاء"
            value={summary.near_expiry.toLocaleString("ar-SA")}
            hint={`${summary.expired} منتهية`}
            tone="warning"
          />
          <KpiCard
            label="النشاط"
            value={`${summary.sales} بيع`}
            hint={`${summary.imports} استيراد · ${summary.api_keys} مفتاح`}
            tone="safe"
          />
        </div>

        {/* ── People ──────────────────────────────────────────────────── */}
        <SectionCard
          noPadding
          title="المستخدمون"
          subtitle="من هنا تحل أكثر حالات الدعم شيوعا"
        >
          <ul className="divide-y divide-[#eadfcc]">
            {(data.users ?? []).map((user: User) => (
              <li
                key={user.id}
                className="px-5 sm:px-6 py-4 flex flex-wrap items-start justify-between gap-3"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-medium text-[#1f2a24]">{user.full_name}</span>
                    {!user.is_active && (
                      <span className="px-2 py-0.5 rounded-full text-xs bg-slate-100 text-slate-600">
                        معطل
                      </span>
                    )}
                    {user.membership_role === "owner" && (
                      <span className="px-2 py-0.5 rounded-full text-xs bg-[#f4eadf] text-[#7b5411]">
                        المالك
                      </span>
                    )}
                  </div>
                  <div dir="ltr" className="text-sm text-[#5f665f] text-right">
                    {user.email}
                  </div>
                  <div className="text-xs text-[#8a9089] mt-0.5">
                    {user.last_login_at
                      ? `آخر دخول ${formatDate(user.last_login_at, locale)}`
                      : "لم يدخل بعد"}
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2 shrink-0">
                  <button
                    type="button"
                    onClick={() =>
                      setPending({
                        kind: "reset",
                        userId: user.id,
                        title: `إصدار رابط استعادة ل ${user.full_name}`,
                        hint: "سبب الإصدار",
                        minimum: 5,
                      })
                    }
                    disabled={resetLink.isPending}
                    className="inline-flex items-center gap-1.5 h-8 px-3 rounded-full text-xs ring-1 ring-inset ring-[#e1d3c0] text-[#5f665f] hover:bg-[#fbf7f0]"
                  >
                    <KeyRound className="h-3.5 w-3.5" />
                    رابط استعادة
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setPending({
                        kind: "impersonate",
                        userId: user.id,
                        title: `تصفح حساب ${user.full_name}`,
                        hint: "سبب الدخول — يظهر في سجل التدقيق (١٠ أحرف فأكثر)",
                        minimum: 10,
                      })
                    }
                    disabled={impersonate.isPending || !user.is_active}
                    className="inline-flex items-center gap-1.5 h-8 px-3 rounded-full text-xs bg-[#1f2a24] text-white hover:bg-[#2c3a32] disabled:opacity-40"
                  >
                    {impersonate.isPending ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Eye className="h-3.5 w-3.5" />
                    )}
                    تصفح كالعميل
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setPending({
                        kind: "toggle",
                        userId: user.id,
                        active: user.is_active,
                        title: `${user.is_active ? "تعطيل" : "تفعيل"} ${user.full_name}`,
                        hint: user.is_active ? "سبب التعطيل" : "سبب التفعيل",
                        minimum: 5,
                      })
                    }
                    className="inline-flex items-center gap-1.5 h-8 px-3 rounded-full text-xs ring-1 ring-inset ring-[#e1d3c0] text-[#5f665f] hover:bg-[#fbf7f0]"
                  >
                    <Power className="h-3.5 w-3.5" />
                    {user.is_active ? "تعطيل" : "تفعيل"}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </SectionCard>

        {/* ── Stock and history ───────────────────────────────────────── */}
        <div className="grid gap-4 lg:grid-cols-3">
          <SectionCard title="المخزون حسب المدة" className="lg:col-span-1">
            <ul className="space-y-2">
              {["expired", "red", "orange", "yellow", "green"].map((zone) => (
                <li key={zone} className="flex items-center justify-between gap-3">
                  <span className="text-sm text-[#5f665f]">{ZONE_LABEL[zone]}</span>
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-xs font-medium tabular-nums ${ZONE_STYLE[zone]}`}
                  >
                    {(zones[zone] ?? 0).toLocaleString("ar-SA")}
                  </span>
                </li>
              ))}
            </ul>
          </SectionCard>

          <SectionCard
            className="lg:col-span-2"
            title="رفع ملف نيابة عن العميل"
            subtitle="يدخل مخزون العميل مباشرة، ويبلغ به"
          >
            <input
              ref={fileRef}
              type="file"
              accept=".xlsx,.xlsm,.csv"
              className="hidden"
              onChange={(event) => {
                const file = event.target.files?.[0];
                event.target.value = "";
                if (!file) return;
                setPending({
                  kind: "upload",
                  file,
                  title: `رفع ${file.name} إلى مخزون العميل`,
                  hint: "سبب الرفع نيابة عن العميل",
                  minimum: 5,
                });
              }}
            />
            <p className="text-sm text-[#5f665f] leading-relaxed mb-4">
              استخدمه حين يرسل العميل ملفه على الواتساب أو يعجز عن الرفع بنفسه.
              يسجل باسمك في سجل الاستيراد، ويصل العميل إشعار بأن الدعم عدل مخزونه.
            </p>
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              disabled={uploadFor.isPending}
              className="inline-flex items-center gap-2 h-10 px-5 rounded-full bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 disabled:opacity-60"
            >
              {uploadFor.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Upload className="h-4 w-4" />
              )}
              اختيار ملف ورفعه
            </button>

            {(data.recent_imports ?? []).length > 0 && (
              <ul className="mt-5 divide-y divide-[#eadfcc] rounded-xl ring-1 ring-[#eadfcc] overflow-hidden">
                {data.recent_imports.slice(0, 5).map((job: Record<string, string | number>) => (
                  <li
                    key={String(job.id)}
                    className="flex items-center justify-between gap-3 px-4 py-2.5 bg-white text-sm"
                  >
                    <span className="truncate text-[#1f2a24]">{job.filename}</span>
                    <span className="text-xs text-[#8a9089] whitespace-nowrap">
                      +{job.created_batches} · ✕{job.failed_rows} ·{" "}
                      {formatDate(String(job.created_at), locale)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </SectionCard>
        </div>

        {/* ── Irreversible ────────────────────────────────────────────── */}
        <SectionCard
          className="ring-1 ring-red-200"
          title="الحذف النهائي"
          subtitle="لا رجعة فيه — تمحى المنشأة وكل بياناتها"
        >
          <p className="text-sm text-[#5f665f] leading-relaxed mb-4">
            يرفض إذا كان للمنشأة صفقات أو فواتير ضريبية، لأن فواتيرها مرتبطة بسلسلة
            فواتير الطرف الآخر. أوقف المنشأة أولا، ثم اكتب اسمها حرفيا للتأكيد.
          </p>
          <div className="flex flex-col sm:flex-row gap-2">
            <input
              value={purgeName}
              onChange={(event) => setPurgeName(event.target.value)}
              placeholder={`اكتب: ${org.name_ar || org.name}`}
              className="flex-1 h-10 px-4 rounded-xl bg-white ring-1 ring-inset ring-red-200 text-sm focus:outline-none focus:ring-2 focus:ring-red-400"
            />
            <button
              type="button"
              disabled={
                purge.isPending ||
                purgeName.trim() !== (org.name_ar || org.name).trim()
              }
              onClick={() =>
                setPending({
                  kind: "purge" as Pending["kind"],
                  title: `حذف «${org.name_ar || org.name}» نهائيا`,
                  hint: "سبب الحذف النهائي (١٠ أحرف فأكثر)",
                  minimum: 10,
                })
              }
              className="inline-flex items-center justify-center gap-2 h-10 px-5 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-40 shrink-0"
            >
              {purge.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="h-4 w-4" />
              )}
              حذف نهائي
            </button>
          </div>
        </SectionCard>
      </div>
    </Shell>
  );
}
