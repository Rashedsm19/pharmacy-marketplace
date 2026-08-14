"use client";

/**
 * API keys for the pharmacy's own system.
 *
 * The whole screen is arranged around one fact: the key is shown once. So the
 * creation result is a deliberate, dismissible panel with a copy button rather
 * than a toast that disappears, and the list shows only the prefix afterwards.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useLocale } from "next-intl";
import {
  AlertTriangle,
  BookOpen,
  Check,
  Copy,
  KeyRound,
  Loader2,
  Plus,
  ShieldOff,
} from "lucide-react";

import Shell from "@/components/layout/shell";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { EmptyState } from "@/components/ui/empty-state";
import { apiKeysApi } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { formatDate } from "@/lib/utils";

type ApiKey = {
  id: string;
  name: string;
  prefix: string;
  scopes: string[];
  is_active: boolean;
  revoked_at?: string | null;
  last_used_at?: string | null;
  last_used_ip?: string | null;
  request_count: number;
  created_at: string;
};

type Scope = { value: string; label_ar: string; description_ar: string };

export default function ApiKeysPage() {
  const locale = useLocale();
  const queryClient = useQueryClient();

  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [selected, setSelected] = useState<string[]>(["inventory:read", "inventory:write"]);
  const [issued, setIssued] = useState<{ key: string; name: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmRevoke, setConfirmRevoke] = useState<string | null>(null);

  const { data: scopes = [] } = useQuery<Scope[]>({
    queryKey: ["api-key-scopes"],
    queryFn: () => apiKeysApi.scopes().then((r) => r.data),
  });

  const { data: keys = [], isLoading } = useQuery<ApiKey[]>({
    queryKey: ["api-keys"],
    queryFn: () => apiKeysApi.list().then((r) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: () => apiKeysApi.create({ name, scopes: selected }).then((r) => r.data),
    onSuccess: (data: ApiKey & { key: string }) => {
      setIssued({ key: data.key, name: data.name });
      setCreating(false);
      setName("");
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
    },
    onError: (err: unknown) => {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "تعذر إنشاء المفتاح."
      );
    },
  });

  const revokeMutation = useMutation({
    mutationFn: (id: string) => apiKeysApi.revoke(id),
    onSuccess: () => {
      setConfirmRevoke(null);
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
    },
    // Silence here was the worst kind: the spinner stopped, the key still read
    // "نشط", and the person believed a leaked key had been revoked when it had
    // not.
    onError: (err: unknown) => {
      setConfirmRevoke(null);
      setError(errorMessage(err, "تعذر إلغاء المفتاح — المفتاح ما زال فعالا"));
    },
  });

  const copyKey = async () => {
    if (!issued) return;
    try {
      await navigator.clipboard.writeText(issued.key);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      setError("تعذر النسخ — حدد المفتاح وانسخه يدويا.");
    }
  };

  const toggleScope = (value: string) =>
    setSelected((current) =>
      current.includes(value)
        ? current.filter((scope) => scope !== value)
        : [...current, value]
    );

  const scopeLabel = (value: string) =>
    scopes.find((scope) => scope.value === value)?.label_ar ?? value;

  return (
    <Shell>
      <div className="space-y-6">
        <PageHeader
          title="مفاتيح الربط البرمجي"
          subtitle="اربط نظامك — أودو أو غيره — بمخزونك في المنصة"
          actions={
            <div className="flex items-center gap-2">
              <Link
                href={`/${locale}/docs/integration`}
                className="inline-flex items-center gap-2 h-9 px-4 rounded-full text-sm font-medium ring-1 ring-inset ring-[#e1d3c0] text-[#5f665f] hover:bg-[#fbf7f0]"
              >
                <BookOpen className="h-4 w-4" />
                دليل الربط
              </Link>
              <button
                type="button"
                onClick={() => {
                  setCreating(true);
                  setIssued(null);
                  setError(null);
                }}
                className="inline-flex items-center gap-2 h-9 px-4 rounded-full bg-brand-600 text-white text-sm font-medium hover:bg-brand-700"
              >
                <Plus className="h-4 w-4" />
                مفتاح جديد
              </button>
            </div>
          }
        />

        {error && (
          <div className="rounded-2xl px-4 py-3 text-sm bg-red-50 text-red-800 ring-1 ring-inset ring-red-200">
            {error}
          </div>
        )}

        {/* ── The one time the key is visible ─────────────────────────── */}
        {issued && (
          <SectionCard
            className="ring-2 ring-brand-500"
            title="مفتاحك جاهز — انسخه الآن"
            subtitle="لن يعرض هذا المفتاح مرة أخرى بعد مغادرة الصفحة"
          >
            <div className="flex items-start gap-3 rounded-xl bg-amber-50 ring-1 ring-inset ring-amber-200 px-4 py-3 mb-4">
              <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
              <p className="text-sm text-amber-900 leading-relaxed">
                نحن نحفظ بصمة مشفرة للمفتاح فقط، ولا نحتفظ بنصه — فلا يمكننا
                إظهاره لك لاحقا. إن فقدته، ألغ هذا المفتاح وأنشئ غيره.
              </p>
            </div>

            <div className="flex flex-col sm:flex-row gap-2">
              <code
                dir="ltr"
                className="flex-1 px-4 py-3 rounded-xl bg-[#1f2a24] text-[#e8f0ea] text-sm font-mono break-all select-all"
              >
                {issued.key}
              </code>
              <button
                type="button"
                onClick={copyKey}
                className="inline-flex items-center justify-center gap-2 h-12 sm:h-auto px-5 rounded-xl bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 shrink-0"
              >
                {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                {copied ? "تم النسخ" : "نسخ"}
              </button>
            </div>

            <button
              type="button"
              onClick={() => setIssued(null)}
              className="mt-4 text-sm text-[#8a9089] hover:text-[#5f665f]"
            >
              حفظته — أغلق
            </button>
          </SectionCard>
        )}

        {/* ── Creation form ───────────────────────────────────────────── */}
        {creating && (
          <SectionCard
            title="إنشاء مفتاح"
            subtitle="اختر للمفتاح اسم النظام الذي سيستخدمه، وامنحه أقل الصلاحيات اللازمة"
          >
            <form
              onSubmit={(event) => {
                event.preventDefault();
                if (!name.trim()) {
                  setError("اسم المفتاح مطلوب.");
                  return;
                }
                if (selected.length === 0) {
                  setError("اختر صلاحية واحدة على الأقل.");
                  return;
                }
                createMutation.mutate();
              }}
              className="space-y-5"
            >
              <div>
                <label
                  htmlFor="key-name"
                  className="block text-sm font-medium text-[#1f2a24] mb-1.5"
                >
                  اسم المفتاح
                </label>
                <input
                  id="key-name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="مثال: نظام أودو — الفرع الرئيسي"
                  className="w-full h-11 px-4 rounded-xl bg-white ring-1 ring-inset ring-[#e1d3c0] text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>

              <fieldset>
                <legend className="text-sm font-medium text-[#1f2a24] mb-2">
                  الصلاحيات
                </legend>
                <div className="grid gap-2 sm:grid-cols-3">
                  {scopes.map((scope) => {
                    const active = selected.includes(scope.value);
                    return (
                      <label
                        key={scope.value}
                        className={`cursor-pointer rounded-xl px-4 py-3 ring-1 ring-inset transition-colors ${
                          active
                            ? "bg-brand-50 ring-brand-400"
                            : "bg-[#fdfbf7] ring-[#e1d3c0] hover:bg-[#f9f4ec]"
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={active}
                            onChange={() => toggleScope(scope.value)}
                            className="h-4 w-4 accent-brand-600"
                          />
                          <span className="text-sm font-medium text-[#1f2a24]">
                            {scope.label_ar}
                          </span>
                        </div>
                        <p className="text-xs text-[#8a9089] mt-1 leading-relaxed">
                          {scope.description_ar}
                        </p>
                        <code
                          dir="ltr"
                          className="block text-[11px] text-[#a8927a] mt-1 font-mono"
                        >
                          {scope.value}
                        </code>
                      </label>
                    );
                  })}
                </div>
              </fieldset>

              <div className="flex items-center gap-2">
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="inline-flex items-center gap-2 h-10 px-5 rounded-full bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 disabled:opacity-60"
                >
                  {createMutation.isPending && (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  )}
                  إنشاء المفتاح
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setCreating(false);
                    setError(null);
                  }}
                  className="h-10 px-5 rounded-full text-sm font-medium text-[#5f665f] hover:bg-[#fbf7f0]"
                >
                  إلغاء
                </button>
              </div>
            </form>
          </SectionCard>
        )}

        {/* ── The keys ────────────────────────────────────────────────── */}
        <SectionCard title="المفاتيح" subtitle="ألغ أي مفتاح فور الاشتباه في تسريبه" noPadding>
          {isLoading ? (
            <p className="px-6 py-8 text-sm text-[#8a9089]">جاري التحميل…</p>
          ) : keys.length === 0 ? (
            <EmptyState
              icon={KeyRound}
              title="لا توجد مفاتيح بعد"
              description="أنشئ مفتاحا ليتمكن نظامك من إرسال المخزون وقراءة ما يقترب انتهاؤه."
              action={
                <button
                  type="button"
                  onClick={() => setCreating(true)}
                  className="inline-flex items-center gap-2 h-10 px-5 rounded-full bg-brand-600 text-white text-sm font-medium hover:bg-brand-700"
                >
                  <Plus className="h-4 w-4" />
                  مفتاح جديد
                </button>
              }
            />
          ) : (
            <ul className="divide-y divide-[#eadfcc]">
              {keys.map((key) => (
                <li key={key.id} className="px-5 sm:px-6 py-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-medium text-[#1f2a24]">{key.name}</span>
                        {key.is_active ? (
                          <span className="px-2 py-0.5 rounded-full text-xs bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-200">
                            نشط
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded-full text-xs bg-slate-100 text-slate-600 ring-1 ring-inset ring-slate-200">
                            ملغى
                          </span>
                        )}
                      </div>
                      <code
                        dir="ltr"
                        className="block text-sm font-mono text-[#5f665f] mt-1"
                      >
                        {key.prefix}••••••••••••
                      </code>
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        {key.scopes.map((scope) => (
                          <span
                            key={scope}
                            className="px-2 py-0.5 rounded-md text-xs bg-[#f4eadf] text-[#7b5411]"
                          >
                            {scopeLabel(scope)}
                          </span>
                        ))}
                      </div>
                    </div>

                    <div className="text-left shrink-0">
                      <p className="text-xs text-[#8a9089]">
                        أنشئ {formatDate(key.created_at, locale)}
                      </p>
                      <p className="text-xs text-[#8a9089] mt-0.5">
                        {key.last_used_at
                          ? `آخر استخدام ${formatDate(key.last_used_at, locale)} · ${key.request_count.toLocaleString("ar-SA")} طلب`
                          : "لم يستخدم بعد"}
                      </p>
                      {key.is_active &&
                        (confirmRevoke === key.id ? (
                          <div className="flex items-center gap-2 mt-2 justify-end">
                            <button
                              type="button"
                              onClick={() => revokeMutation.mutate(key.id)}
                              disabled={revokeMutation.isPending}
                              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-red-600 text-white text-xs font-medium hover:bg-red-700 disabled:opacity-60"
                            >
                              {revokeMutation.isPending && (
                                <Loader2 className="h-3 w-3 animate-spin" />
                              )}
                              تأكيد الإلغاء
                            </button>
                            <button
                              type="button"
                              onClick={() => setConfirmRevoke(null)}
                              className="px-3 py-1 rounded-full text-xs text-[#5f665f] hover:bg-[#fbf7f0]"
                            >
                              تراجع
                            </button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() => setConfirmRevoke(key.id)}
                            className="inline-flex items-center gap-1.5 mt-2 text-xs font-medium text-red-700 hover:text-red-800"
                          >
                            <ShieldOff className="h-3.5 w-3.5" />
                            إلغاء المفتاح
                          </button>
                        ))}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </SectionCard>
      </div>
    </Shell>
  );
}
