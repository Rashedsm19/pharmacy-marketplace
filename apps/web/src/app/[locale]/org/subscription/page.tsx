"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import Shell from "@/components/layout/shell";
import { PageHeader } from "@/components/ui/page-header";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { EmptyState } from "@/components/ui/empty-state";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { subscriptionsApi } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import {
  CreditCard,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Receipt,
  Sparkles,
  CalendarClock,
} from "lucide-react";

type Plan = {
  id: string;
  code: string;
  version: number;
  name_ar: string;
  name_en: string;
  description_ar: string | null;
  description_en: string | null;
  monthly_price: string;
  annual_price: string;
  currency: string;
  trial_days: number;
  limits: Record<string, number | boolean | null>;
  is_active: boolean;
  is_public: boolean;
  sort_order: number;
};

type Subscription = {
  id: string;
  plan_id: string;
  status: string;
  billing_cycle: string;
  current_period_start: string | null;
  current_period_end: string | null;
  trial_end: string | null;
  cancel_at_period_end: boolean;
  grace_until: string | null;
  pending_plan_id: string | null;
};

type Usage = {
  resources: Record<string, number>;
  usage: Record<string, number>;
  limits: Record<string, number | null>;
  features: Record<string, boolean>;
  warnings: { resource?: string; metric?: string; current?: number; count?: number; limit: number }[];
  status: string;
};

type Checkout = {
  subscription_id: string;
  invoice_id: string;
  provider_ref: string;
  total: string;
  currency: string;
  sandbox: boolean;
};

const STATUS_VARIANT: Record<string, "success" | "warning" | "danger" | "default" | "info"> = {
  trialing: "info",
  active: "success",
  past_due: "warning",
  cancelled: "default",
  expired: "danger",
};

const ADDONS = [
  { code: "extra_listings", labelKey: "addonExtraListings" },
  { code: "extra_branch", labelKey: "addonExtraBranch" },
  { code: "extra_member", labelKey: "addonExtraMember" },
] as const;

export default function SubscriptionPage() {
  const t = useTranslations("subscription");
  const tc = useTranslations("common");
  const locale = useLocale();
  const dateLocale = locale === "ar" ? "ar-SA" : "en-US";
  const queryClient = useQueryClient();

  const [cycle, setCycle] = useState<"monthly" | "annual">("monthly");
  const [checkout, setCheckout] = useState<Checkout | null>(null);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [notice, setNotice] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const plansQuery = useQuery({
    queryKey: ["subscriptions", "plans"],
    queryFn: () => subscriptionsApi.plans().then((r) => r.data as Plan[]),
  });
  const currentQuery = useQuery({
    queryKey: ["subscriptions", "current"],
    queryFn: () => subscriptionsApi.current().then((r) => r.data),
  });
  const invoicesQuery = useQuery({
    queryKey: ["subscriptions", "invoices"],
    queryFn: () => subscriptionsApi.invoices().then((r) => r.data),
  });
  const addonsQuery = useQuery({
    queryKey: ["subscriptions", "addons"],
    queryFn: () => subscriptionsApi.addons().then((r) => r.data),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["subscriptions"] });
  };

  const onError = (err: unknown) =>
    setNotice({
      kind: "err",
      text:
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        t("actionError"),
    });

  const handleCheckout = (data: Checkout) => {
    if (data.sandbox) {
      setCheckout(data);
    } else {
      invalidate();
    }
  };

  const trialMutation = useMutation({
    mutationFn: (planId: string) => subscriptionsApi.startTrial(planId),
    onSuccess: () => {
      setNotice({ kind: "ok", text: tc("success") });
      invalidate();
    },
    onError,
  });
  const subscribeMutation = useMutation({
    mutationFn: ({ planId, c }: { planId: string; c: string }) =>
      subscriptionsApi.subscribe(planId, c),
    onSuccess: (res) => handleCheckout(res.data),
    onError,
  });
  const changeMutation = useMutation({
    mutationFn: ({ planId, c }: { planId: string; c: string }) =>
      subscriptionsApi.changePlan(planId, c),
    onSuccess: (res) => {
      if (res.data?.checkout) {
        handleCheckout({ ...res.data.checkout, total: "0", currency: "SAR" } as Checkout);
      } else {
        setNotice({ kind: "ok", text: tc("success") });
        invalidate();
      }
    },
    onError,
  });
  const cancelMutation = useMutation({
    mutationFn: () => subscriptionsApi.cancel(),
    onSuccess: () => {
      setConfirmCancel(false);
      setNotice({ kind: "ok", text: t("cancelled") });
      invalidate();
    },
    onError,
  });
  const reactivateMutation = useMutation({
    mutationFn: () => subscriptionsApi.reactivate(),
    onSuccess: (res) => {
      if (res.data?.checkout) {
        handleCheckout({ ...res.data.checkout, total: "0", currency: "SAR" } as Checkout);
      } else {
        setNotice({ kind: "ok", text: t("reactivated") });
        invalidate();
      }
    },
    onError,
  });
  const payMutation = useMutation({
    mutationFn: ({ ref, status }: { ref: string; status: "paid" | "failed" }) =>
      subscriptionsApi.simulatePayment(ref, status),
    onSuccess: (_res, vars) => {
      setCheckout(null);
      setNotice(
        vars.status === "paid"
          ? { kind: "ok", text: t("paymentSuccess") }
          : { kind: "err", text: t("paymentFailed") }
      );
      invalidate();
    },
    onError,
  });
  const addonMutation = useMutation({
    mutationFn: (code: string) => subscriptionsApi.purchaseAddon(code),
    onSuccess: (res) => handleCheckout(res.data),
    onError,
  });

  const current = currentQuery.data as
    | {
        subscription: Subscription | null;
        plan: Plan | null;
        entitlements: { features: Record<string, boolean>; limits: Record<string, number | null> };
        usage: Usage;
        sandbox: boolean;
      }
    | undefined;
  const sub = current?.subscription ?? null;
  const plan = current?.plan ?? null;
  const usage = current?.usage;
  const invoices = (invoicesQuery.data ?? []) as {
    id: string;
    period_start: string;
    period_end: string;
    amount: string;
    vat: string;
    total: string;
    currency: string;
    status: string;
    paid_at: string | null;
  }[];
  const activeAddons = ((addonsQuery.data ?? []) as { id: string; code: string; status: string; valid_until: string | null }[]).filter(
    (a) => a.status === "active"
  );
  const plans = plansQuery.data ?? [];

  const statusText = (s: string) =>
    ({
      trialing: t("statusTrialing"),
      active: t("statusActive"),
      past_due: t("statusPastDue"),
      cancelled: t("statusCancelled"),
      expired: t("statusExpired"),
    })[s] ?? s;

  const planName = (p: Plan) => (locale === "ar" ? p.name_ar : p.name_en);
  const featureLabel = (key: string) =>
    ({
      advanced_reports: t("featureAdvancedReports"),
      restock_intelligence: t("featureRestock"),
      api_access: t("featureApi"),
    })[key] ?? key;
  const resourceLabel = (key: string) =>
    ({
      active_listings: t("usageListings"),
      branches: t("usageBranches"),
      team_members: t("usageMembers"),
    })[key] ?? key;

  const limitFor = (key: string) =>
    usage?.limits?.[
      { active_listings: "max_active_listings", branches: "max_branches", team_members: "max_team_members" }[
        key
      ] ?? ""
    ] ?? null;

  const busy =
    trialMutation.isPending ||
    subscribeMutation.isPending ||
    changeMutation.isPending ||
    cancelMutation.isPending ||
    reactivateMutation.isPending;

  const subscribeTo = (p: Plan) => {
    setNotice(null);
    if (!sub || ["expired", "cancelled"].includes(sub.status)) {
      if (p.trial_days > 0 && !sub) trialMutation.mutate(p.id);
      else subscribeMutation.mutate({ planId: p.id, c: cycle });
      return;
    }
    if (sub.status === "trialing") {
      subscribeMutation.mutate({ planId: p.id, c: cycle });
      return;
    }
    changeMutation.mutate({ planId: p.id, c: cycle });
  };

  return (
    <Shell>
      <div className="space-y-6">
        <PageHeader title={t("title")} subtitle={t("subtitle")} />

        {notice && (
          <div
            className={`rounded-lg px-4 py-2.5 text-sm ring-1 ${
              notice.kind === "ok"
                ? "bg-safe-50 text-safe-700 ring-safe-200"
                : "bg-red-50 text-red-700 ring-red-200"
            }`}
          >
            {notice.text}
          </div>
        )}

        {/* Current subscription */}
        {currentQuery.isLoading ? (
          <div className="h-40 animate-pulse rounded-2xl bg-slate-100" />
        ) : currentQuery.isError ? (
          <EmptyState icon={CreditCard} title={t("loadError")} />
        ) : !sub ? (
          <EmptyState icon={CreditCard} title={t("noSubscription")} description={t("noSubscriptionDesc")} />
        ) : (
          <div className="rounded-2xl bg-white p-6 ring-1 ring-slate-200 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <h2 className="text-lg font-bold text-slate-900">
                  {plan ? planName(plan) : sub.plan_id}
                </h2>
                <Badge variant={STATUS_VARIANT[sub.status] ?? "default"}>
                  {statusText(sub.status)}
                </Badge>
                {plan?.code === "legacy" && (
                  <span className="text-xs text-slate-500">{t("legacyPlan")}</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                {sub.status === "active" && !sub.cancel_at_period_end && (
                  <button
                    onClick={() => setConfirmCancel(true)}
                    className="inline-flex h-9 items-center rounded-lg px-3 text-sm font-medium text-red-600 ring-1 ring-inset ring-red-200 hover:bg-red-50"
                  >
                    {t("cancel")}
                  </button>
                )}
                {(sub.status === "cancelled" ||
                  sub.status === "expired" ||
                  (sub.status === "active" && sub.cancel_at_period_end)) && (
                  <button
                    onClick={() => reactivateMutation.mutate()}
                    disabled={busy}
                    className="inline-flex h-9 items-center rounded-lg bg-brand-600 px-3 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
                  >
                    {t("reactivate")}
                  </button>
                )}
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
              <div>
                <div className="text-slate-500">{t("billingCycle")}</div>
                <div className="font-medium">
                  {sub.billing_cycle === "annual" ? t("annual") : t("monthly")}
                </div>
              </div>
              {sub.current_period_end && (
                <div>
                  <div className="text-slate-500">{t("currentPeriodEnd")}</div>
                  <div className="font-medium">{formatDate(sub.current_period_end, dateLocale)}</div>
                </div>
              )}
              {sub.trial_end && (
                <div>
                  <div className="text-slate-500">{t("trialEnds")}</div>
                  <div className="font-medium">{formatDate(sub.trial_end, dateLocale)}</div>
                </div>
              )}
              {sub.grace_until && sub.status === "past_due" && (
                <div>
                  <div className="text-slate-500">{t("graceUntil")}</div>
                  <div className="font-medium text-amber-700">
                    {formatDate(sub.grace_until, dateLocale)}
                  </div>
                </div>
              )}
            </div>

            {sub.cancel_at_period_end && (
              <div className="flex items-center gap-2 rounded-lg bg-amber-50 px-4 py-2.5 text-sm text-amber-800 ring-1 ring-amber-200">
                <CalendarClock className="h-4 w-4" />
                {t("cancelAtPeriodEnd")}
              </div>
            )}
            {sub.pending_plan_id && (
              <div className="flex items-center gap-2 rounded-lg bg-blue-50 px-4 py-2.5 text-sm text-blue-800 ring-1 ring-blue-200">
                <CalendarClock className="h-4 w-4" />
                {t("scheduledDowngrade")}
              </div>
            )}
          </div>
        )}

        {/* Usage meters */}
        {usage && (
          <div className="rounded-2xl bg-white p-6 ring-1 ring-slate-200 space-y-4">
            <h2 className="text-lg font-bold text-slate-900">{t("usage")}</h2>
            {(usage.warnings ?? []).length > 0 && (
              <div className="flex items-center gap-2 rounded-lg bg-amber-50 px-4 py-2.5 text-sm text-amber-800 ring-1 ring-amber-200">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                {t("usageWarning", {
                  current: usage.warnings[0].current ?? usage.warnings[0].count ?? 0,
                  limit: usage.warnings[0].limit,
                })}
              </div>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
              {Object.entries(usage.resources ?? {}).map(([key, value]) => {
                const limit = limitFor(key);
                return (
                  <div key={key}>
                    <div className="mb-1 flex items-center justify-between text-sm">
                      <span className="text-slate-600">{resourceLabel(key)}</span>
                      <span className="tabular-nums font-medium">
                        {value} / {limit ?? t("unlimited")}
                      </span>
                    </div>
                    <Progress
                      value={value}
                      max={limit ?? Math.max(value, 1)}
                      tone={limit && value / limit >= 0.8 ? "warning" : "brand"}
                    />
                  </div>
                );
              })}
            </div>
            <div className="flex flex-wrap gap-x-6 gap-y-2 border-t border-slate-100 pt-4 text-sm">
              {Object.entries(usage.features ?? {}).map(([key, on]) => (
                <span key={key} className="inline-flex items-center gap-1.5 text-slate-700">
                  {on ? (
                    <CheckCircle2 className="h-4 w-4 text-safe-600" />
                  ) : (
                    <XCircle className="h-4 w-4 text-slate-300" />
                  )}
                  {featureLabel(key)}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Plans */}
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-bold text-slate-900">{t("plans")}</h2>
              <p className="text-sm text-slate-500">{t("plansDesc")}</p>
            </div>
            <div className="flex rounded-lg bg-slate-100 p-1 text-sm">
              {(["monthly", "annual"] as const).map((c) => (
                <button
                  key={c}
                  onClick={() => setCycle(c)}
                  className={`rounded-md px-4 py-1.5 font-medium transition ${
                    cycle === c ? "bg-white text-brand-700 shadow-sm" : "text-slate-500"
                  }`}
                >
                  {c === "monthly" ? t("monthly") : t("annual")}
                </button>
              ))}
            </div>
          </div>

          {plansQuery.isLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {[0, 1, 2].map((i) => (
                <div key={i} className="h-64 animate-pulse rounded-2xl bg-slate-100" />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {plans.map((p) => {
                const isCurrent = plan?.id === p.id && sub && !["expired", "cancelled"].includes(sub.status);
                const price = cycle === "monthly" ? p.monthly_price : p.annual_price;
                return (
                  <div
                    key={p.id}
                    className={`flex flex-col rounded-2xl bg-white p-6 ring-1 ${
                      isCurrent ? "ring-2 ring-brand-500" : "ring-slate-200"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <h3 className="text-base font-bold text-slate-900">{planName(p)}</h3>
                      {isCurrent && <Badge variant="brand">{t("currentBadge")}</Badge>}
                    </div>
                    <div className="mt-3 flex items-baseline gap-1">
                      <span className="text-2xl font-bold tabular-nums text-slate-900">
                        {formatCurrency(Number(price))}
                      </span>
                      <span className="text-sm text-slate-500">
                        {cycle === "monthly" ? t("perMonth") : t("perYear")}
                      </span>
                    </div>
                    {p.trial_days > 0 && (
                      <div className="mt-1 text-xs text-safe-700">
                        {t("trialDays", { days: p.trial_days })}
                      </div>
                    )}
                    <ul className="mt-4 flex-1 space-y-2 text-sm text-slate-600">
                      {Object.entries(p.limits ?? {}).map(([key, val]) =>
                        typeof val === "boolean" ? (
                          <li key={key} className="flex items-center gap-1.5">
                            {val ? (
                              <CheckCircle2 className="h-4 w-4 text-safe-600" />
                            ) : (
                              <XCircle className="h-4 w-4 text-slate-300" />
                            )}
                            {featureLabel(key)}
                          </li>
                        ) : null
                      )}
                    </ul>
                    <button
                      onClick={() => subscribeTo(p)}
                      disabled={busy || Boolean(isCurrent)}
                      className={`mt-5 inline-flex h-10 items-center justify-center rounded-lg text-sm font-medium disabled:opacity-50 ${
                        isCurrent
                          ? "bg-slate-100 text-slate-400"
                          : "bg-brand-600 text-white hover:bg-brand-700"
                      }`}
                    >
                      {isCurrent
                        ? t("currentBadge")
                        : !sub && p.trial_days > 0
                          ? t("startTrial")
                          : sub?.status === "trialing"
                            ? t("subscribe")
                            : sub
                              ? t("changePlan")
                              : t("subscribe")}
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Add-ons */}
        <div className="rounded-2xl bg-white p-6 ring-1 ring-slate-200 space-y-4">
          <h2 className="text-lg font-bold text-slate-900">{t("addons")}</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {ADDONS.map((a) => {
              const owned = activeAddons.find((x) => x.code === a.code);
              return (
                <div
                  key={a.code}
                  className="flex items-center justify-between rounded-xl px-4 py-3 ring-1 ring-slate-200"
                >
                  <div>
                    <div className="text-sm font-medium text-slate-800">{t(a.labelKey)}</div>
                    {owned?.valid_until && (
                      <div className="text-xs text-slate-500">
                        {t("activeUntil")} {formatDate(owned.valid_until, dateLocale)}
                      </div>
                    )}
                  </div>
                  <button
                    onClick={() => addonMutation.mutate(a.code)}
                    disabled={addonMutation.isPending}
                    className="inline-flex h-9 items-center gap-1.5 rounded-lg px-3 text-sm font-medium text-brand-700 ring-1 ring-inset ring-brand-200 hover:bg-brand-50 disabled:opacity-50"
                  >
                    <Sparkles className="h-4 w-4" />
                    {t("buyAddon")}
                  </button>
                </div>
              );
            })}
          </div>
        </div>

        {/* Invoices */}
        <div className="rounded-2xl bg-white p-6 ring-1 ring-slate-200 space-y-4">
          <h2 className="flex items-center gap-2 text-lg font-bold text-slate-900">
            <Receipt className="h-5 w-5 text-slate-400" />
            {t("invoices")}
          </h2>
          {invoices.length === 0 ? (
            <p className="text-sm text-slate-500">{t("noInvoices")}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-start text-slate-500">
                    <th className="py-2 text-start font-medium">{t("invoiceDate")}</th>
                    <th className="py-2 text-start font-medium">{t("invoicePeriod")}</th>
                    <th className="py-2 text-start font-medium">{t("invoiceTotal")}</th>
                    <th className="py-2 text-start font-medium">{t("invoiceStatus")}</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices.map((inv) => (
                    <tr key={inv.id} className="border-b border-slate-50">
                      <td className="py-2.5">{formatDate(inv.period_start, dateLocale)}</td>
                      <td className="py-2.5 tabular-nums">
                        {formatDate(inv.period_start, dateLocale)} —{" "}
                        {formatDate(inv.period_end, dateLocale)}
                      </td>
                      <td className="py-2.5 tabular-nums font-medium">
                        {formatCurrency(Number(inv.total))}
                      </td>
                      <td className="py-2.5">
                        <Badge
                          variant={
                            inv.status === "paid"
                              ? "success"
                              : inv.status === "failed"
                                ? "danger"
                                : "warning"
                          }
                        >
                          {(
                            {
                              paid: t("invoicePaid"),
                              pending: t("invoicePending"),
                              failed: t("invoiceFailed"),
                              void: t("invoiceVoid"),
                            } as Record<string, string>
                          )[inv.status] ?? inv.status}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Cancel confirmation */}
        <Dialog open={confirmCancel} onOpenChange={setConfirmCancel}>
          <DialogContent title={t("cancelConfirmTitle")} description={t("cancelConfirmDesc")}>
            <DialogFooter>
              <button
                onClick={() => cancelMutation.mutate()}
                disabled={cancelMutation.isPending}
                className="inline-flex h-10 items-center rounded-lg bg-red-600 px-4 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
              >
                {t("cancelConfirm")}
              </button>
              <button
                onClick={() => setConfirmCancel(false)}
                className="inline-flex h-10 items-center rounded-lg px-4 text-sm font-medium text-slate-600 ring-1 ring-inset ring-slate-200 hover:bg-slate-50"
              >
                {tc("back")}
              </button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Sandbox checkout */}
        <Dialog open={checkout !== null} onOpenChange={(open) => !open && setCheckout(null)}>
          {checkout && (
            <DialogContent title={t("checkoutTitle")} description={t("checkoutSandbox")}>
              <div className="space-y-4">
                <div className="rounded-xl bg-slate-50 px-4 py-3 text-center">
                  <div className="text-sm text-slate-500">{t("checkoutAmount")}</div>
                  <div className="text-2xl font-bold tabular-nums text-slate-900">
                    {formatCurrency(Number(checkout.total))}
                  </div>
                </div>
                <DialogFooter>
                  <button
                    onClick={() =>
                      payMutation.mutate({ ref: checkout.provider_ref, status: "paid" })
                    }
                    disabled={payMutation.isPending}
                    className="inline-flex h-10 items-center rounded-lg bg-brand-600 px-4 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
                  >
                    {t("payNow")}
                  </button>
                  <button
                    onClick={() =>
                      payMutation.mutate({ ref: checkout.provider_ref, status: "failed" })
                    }
                    disabled={payMutation.isPending}
                    className="inline-flex h-10 items-center rounded-lg px-4 text-sm font-medium text-red-600 ring-1 ring-inset ring-red-200 hover:bg-red-50 disabled:opacity-50"
                  >
                    {t("paymentFailed")}
                  </button>
                </DialogFooter>
              </div>
            </DialogContent>
          )}
        </Dialog>
      </div>
    </Shell>
  );
}
