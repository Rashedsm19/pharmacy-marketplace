"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import Shell from "@/components/layout/shell";
import { PageHeader } from "@/components/ui/page-header";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { subscriptionsApi } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import { Layers, Plus, Pencil, Ban, Building2 } from "lucide-react";

type Plan = {
  id: string;
  code: string;
  version: number;
  name_ar: string;
  name_en: string;
  monthly_price: string;
  annual_price: string;
  currency: string;
  trial_days: number;
  limits: Record<string, unknown>;
  is_active: boolean;
  is_public: boolean;
  sort_order: number;
};

type AdminRow = {
  organization_id: string;
  organization_name: string;
  organization_status: string;
  subscription: { id: string; status: string; billing_cycle: string; current_period_end: string | null } | null;
  plan: Plan | null;
};

type FormState = {
  id: string | null;
  code: string;
  name_ar: string;
  name_en: string;
  monthly_price: string;
  annual_price: string;
  trial_days: string;
  sort_order: string;
  is_public: boolean;
  is_active: boolean;
  limits: string;
};

const emptyForm: FormState = {
  id: null,
  code: "",
  name_ar: "",
  name_en: "",
  monthly_price: "0",
  annual_price: "0",
  trial_days: "0",
  sort_order: "0",
  is_public: true,
  is_active: true,
  limits: '{\n  "max_active_listings": 20,\n  "max_branches": 2,\n  "max_team_members": 5,\n  "max_listings_per_period": 30,\n  "advanced_reports": false,\n  "restock_intelligence": false,\n  "api_access": false\n}',
};

export default function AdminPlansPage() {
  const t = useTranslations("subscription");
  const tc = useTranslations("common");
  const locale = useLocale();
  const queryClient = useQueryClient();

  const [form, setForm] = useState<FormState | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const plansQuery = useQuery({
    queryKey: ["admin", "plans"],
    queryFn: () => subscriptionsApi.plans().then((r) => r.data as Plan[]),
  });
  const subsQuery = useQuery({
    queryKey: ["admin", "org-subscriptions"],
    queryFn: () => subscriptionsApi.adminSubscriptions().then((r) => r.data as AdminRow[]),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["admin", "plans"] });
    queryClient.invalidateQueries({ queryKey: ["subscriptions", "plans"] });
    queryClient.invalidateQueries({ queryKey: ["admin", "org-subscriptions"] });
  };

  const saveMutation = useMutation({
    mutationFn: (payload: { id: string | null; body: Record<string, unknown> }) =>
      payload.id
        ? subscriptionsApi.adminUpdatePlan(payload.id, payload.body)
        : subscriptionsApi.adminCreatePlan(payload.body),
    onSuccess: () => {
      setForm(null);
      setNotice(t("planSaved"));
      invalidate();
    },
    onError: (err) =>
      setFormError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          t("actionError")
      ),
  });
  const deactivateMutation = useMutation({
    mutationFn: (id: string) => subscriptionsApi.adminDeactivatePlan(id),
    onSuccess: () => {
      setNotice(t("deactivated"));
      invalidate();
    },
  });

  const openEdit = (p: Plan) => {
    setFormError(null);
    setForm({
      id: p.id,
      code: p.code,
      name_ar: p.name_ar,
      name_en: p.name_en,
      monthly_price: String(p.monthly_price),
      annual_price: String(p.annual_price),
      trial_days: String(p.trial_days),
      sort_order: String(p.sort_order),
      is_public: p.is_public,
      is_active: p.is_active,
      limits: JSON.stringify(p.limits ?? {}, null, 2),
    });
  };

  const submit = () => {
    if (!form) return;
    setFormError(null);
    let limits: Record<string, unknown>;
    try {
      limits = JSON.parse(form.limits || "{}");
    } catch {
      setFormError(t("invalidLimits"));
      return;
    }
    const body: Record<string, unknown> = {
      name_ar: form.name_ar,
      name_en: form.name_en,
      monthly_price: Number(form.monthly_price),
      annual_price: Number(form.annual_price),
      trial_days: Number(form.trial_days),
      sort_order: Number(form.sort_order),
      is_public: form.is_public,
      is_active: form.is_active,
      limits,
    };
    if (!form.id) body.code = form.code;
    saveMutation.mutate({ id: form.id, body });
  };

  const plans = plansQuery.data ?? [];
  const subs = subsQuery.data ?? [];

  const field = (
    label: string,
    key: keyof FormState,
    opts?: { type?: string; textarea?: boolean }
  ) => (
    <div>
      <label className="mb-1 block text-sm font-medium text-slate-700">{label}</label>
      {opts?.textarea ? (
        <textarea
          rows={7}
          dir="ltr"
          value={String(form?.[key] ?? "")}
          onChange={(e) => setForm((f) => (f ? { ...f, [key]: e.target.value } : f))}
          className="w-full rounded-lg px-3 py-2 font-mono text-xs ring-1 ring-inset ring-slate-200 focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
      ) : (
        <input
          type={opts?.type ?? "text"}
          value={String(form?.[key] ?? "")}
          onChange={(e) => setForm((f) => (f ? { ...f, [key]: e.target.value } : f))}
          className="h-10 w-full rounded-lg px-3 ring-1 ring-inset ring-slate-200 focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
      )}
    </div>
  );

  return (
    <Shell>
      <div className="space-y-6">
        <PageHeader
          title={t("adminPlansTitle")}
          subtitle={t("adminPlansSubtitle")}
          actions={
            <button
              onClick={() => {
                setFormError(null);
                setForm({ ...emptyForm });
              }}
              className="inline-flex h-10 items-center gap-2 rounded-lg bg-brand-600 px-4 text-sm font-medium text-white hover:bg-brand-700"
            >
              <Plus className="h-4 w-4" />
              {t("newPlan")}
            </button>
          }
        />

        {notice && (
          <div className="rounded-lg bg-safe-50 px-4 py-2.5 text-sm text-safe-700 ring-1 ring-safe-200">
            {notice}
          </div>
        )}

        {plansQuery.isLoading ? (
          <div className="h-48 animate-pulse rounded-2xl bg-slate-100" />
        ) : plans.length === 0 ? (
          <EmptyState icon={Layers} title={tc("noData")} />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {plans.map((p) => (
              <div key={p.id} className="rounded-2xl bg-white p-5 ring-1 ring-slate-200 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="font-bold text-slate-900">
                    {locale === "ar" ? p.name_ar : p.name_en}
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Badge variant={p.is_active ? "success" : "default"}>
                      {p.is_active ? t("isActive") : "—"}
                    </Badge>
                    {p.is_public && <Badge variant="info">public</Badge>}
                  </div>
                </div>
                <div className="text-xs text-slate-500 tabular-nums">
                  {p.code} · {t("version")} {p.version}
                </div>
                <div className="flex gap-4 text-sm tabular-nums">
                  <span>{formatCurrency(Number(p.monthly_price))} {t("perMonth")}</span>
                  <span>{formatCurrency(Number(p.annual_price))} {t("perYear")}</span>
                </div>
                <div className="flex items-center gap-2 pt-1">
                  <button
                    onClick={() => openEdit(p)}
                    className="inline-flex h-9 items-center gap-1.5 rounded-lg px-3 text-sm font-medium text-slate-700 ring-1 ring-inset ring-slate-200 hover:bg-slate-50"
                  >
                    <Pencil className="h-4 w-4" />
                    {tc("edit")}
                  </button>
                  {p.is_active && (
                    <button
                      onClick={() => deactivateMutation.mutate(p.id)}
                      disabled={deactivateMutation.isPending}
                      className="inline-flex h-9 items-center gap-1.5 rounded-lg px-3 text-sm font-medium text-red-600 ring-1 ring-inset ring-red-200 hover:bg-red-50 disabled:opacity-50"
                    >
                      <Ban className="h-4 w-4" />
                      {t("deactivate")}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Organization subscriptions */}
        <div className="rounded-2xl bg-white p-6 ring-1 ring-slate-200 space-y-4">
          <h2 className="flex items-center gap-2 text-lg font-bold text-slate-900">
            <Building2 className="h-5 w-5 text-slate-400" />
            {t("orgSubscriptions")}
          </h2>
          {subsQuery.isLoading ? (
            <div className="h-32 animate-pulse rounded-xl bg-slate-100" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-slate-500">
                    <th className="py-2 text-start font-medium">{t("organization")}</th>
                    <th className="py-2 text-start font-medium">{t("plan")}</th>
                    <th className="py-2 text-start font-medium">{t("status")}</th>
                    <th className="py-2 text-start font-medium">{t("billingCycle")}</th>
                    <th className="py-2 text-start font-medium">{t("currentPeriodEnd")}</th>
                  </tr>
                </thead>
                <tbody>
                  {subs.map((row) => (
                    <tr key={row.organization_id} className="border-b border-slate-50">
                      <td className="py-2.5 font-medium text-slate-800">
                        {row.organization_name}
                      </td>
                      <td className="py-2.5">
                        {row.plan ? (locale === "ar" ? row.plan.name_ar : row.plan.name_en) : "—"}
                      </td>
                      <td className="py-2.5">
                        {row.subscription ? (
                          <Badge
                            variant={
                              row.subscription.status === "active"
                                ? "success"
                                : row.subscription.status === "trialing"
                                  ? "info"
                                  : row.subscription.status === "past_due"
                                    ? "warning"
                                    : "default"
                            }
                          >
                            {row.subscription.status}
                          </Badge>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="py-2.5">
                        {row.subscription
                          ? row.subscription.billing_cycle === "annual"
                            ? t("annual")
                            : t("monthly")
                          : "—"}
                      </td>
                      <td className="py-2.5 tabular-nums">
                        {row.subscription?.current_period_end
                          ? formatDate(
                              row.subscription.current_period_end,
                              locale === "ar" ? "ar-SA" : "en-US"
                            )
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Create / edit dialog */}
        <Dialog open={form !== null} onOpenChange={(open) => !open && setForm(null)}>
          {form && (
            <DialogContent title={form.id ? t("editPlan") : t("newPlan")} size="lg">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {!form.id && field(t("planCode"), "code")}
                {field(t("planNameAr"), "name_ar")}
                {field(t("planNameEn"), "name_en")}
                {field(t("monthlyPrice"), "monthly_price", { type: "number" })}
                {field(t("annualPrice"), "annual_price", { type: "number" })}
                {field(t("trialDaysLabel"), "trial_days", { type: "number" })}
                {field(t("sortOrder"), "sort_order", { type: "number" })}
                <div className="flex items-center gap-6 pt-6">
                  <label className="flex items-center gap-2 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      checked={form.is_public}
                      onChange={(e) => setForm({ ...form, is_public: e.target.checked })}
                      className="h-4 w-4 accent-brand-600"
                    />
                    {t("isPublic")}
                  </label>
                  <label className="flex items-center gap-2 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      checked={form.is_active}
                      onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                      className="h-4 w-4 accent-brand-600"
                    />
                    {t("isActive")}
                  </label>
                </div>
              </div>
              <div className="mt-4">
                {field(t("limits"), "limits", { textarea: true })}
                <p className="mt-1 text-xs text-slate-500" dir="ltr">
                  {t("limitsHint")}
                </p>
              </div>
              {formError && (
                <div className="mt-3 rounded-lg bg-red-50 px-4 py-2.5 text-sm text-red-700 ring-1 ring-red-200">
                  {formError}
                </div>
              )}
              <DialogFooter>
                <button
                  onClick={submit}
                  disabled={saveMutation.isPending}
                  className="inline-flex h-10 items-center rounded-lg bg-brand-600 px-4 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
                >
                  {tc("save")}
                </button>
                <button
                  onClick={() => setForm(null)}
                  className="inline-flex h-10 items-center rounded-lg px-4 text-sm font-medium text-slate-600 ring-1 ring-inset ring-slate-200 hover:bg-slate-50"
                >
                  {tc("cancel")}
                </button>
              </DialogFooter>
            </DialogContent>
          )}
        </Dialog>
      </div>
    </Shell>
  );
}
