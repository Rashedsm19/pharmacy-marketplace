"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import Shell from "@/components/layout/shell";
import { DataTable } from "@/components/ui/data-table";
import { ExpiryBadge } from "@/components/ui/expiry-badge";
import { PageHeader } from "@/components/ui/page-header";
import { KpiCard } from "@/components/ui/kpi-card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { branchesApi, restockApi } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import {
  Lightbulb,
  RefreshCw,
  ShoppingCart,
  Tag,
  Pause,
  PackageSearch,
  Eye,
  Ban,
  Lock,
} from "lucide-react";

type Recommendation = {
  id: string;
  kind: "replenishment" | "listing";
  status: string;
  action: "buy_from_marketplace" | "list_now" | "hold" | "reorder_supplier";
  evidence_strength: "sufficient" | "sparse" | "insufficient";
  suggested_qty: number;
  suggested_price: number | null;
  days_of_cover: number | null;
  daily_velocity: number;
  on_hand_qty: number;
  incoming_qty: number;
  nearest_expiry_date: string | null;
  matched_listing_id: string | null;
  reason_ar: string;
  reason_en: string;
  computed_at: string;
  inputs?: Record<string, unknown> | null;
  product_name?: string | null;
  product_name_ar?: string | null;
  product_sku?: string | null;
  branch_name?: string | null;
};

const ACTION_ICON = {
  buy_from_marketplace: ShoppingCart,
  list_now: Tag,
  hold: Pause,
  reorder_supplier: PackageSearch,
} as const;

function daysUntil(isoDate: string | null): number | undefined {
  if (!isoDate) return undefined;
  const ms = new Date(isoDate).getTime() - Date.now();
  return Math.ceil(ms / 86_400_000);
}

export default function RestockPage() {
  const t = useTranslations("restock");
  const tc = useTranslations("common");
  const locale = useLocale();
  const queryClient = useQueryClient();

  const [kind, setKind] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [branchId, setBranchId] = useState("");
  const [page, setPage] = useState(1);
  const [detail, setDetail] = useState<Recommendation | null>(null);
  const [actTarget, setActTarget] = useState<Recommendation | null>(null);
  const [actPrice, setActPrice] = useState("");
  const [actQty, setActQty] = useState("");
  const [notice, setNotice] = useState<string | null>(null);

  const params: Record<string, unknown> = { page, page_size: 20 };
  if (kind) params.kind = kind;
  if (statusFilter) params.status = statusFilter;
  if (branchId) params.branch_id = branchId;

  const listQuery = useQuery({
    queryKey: ["restock", "list", params],
    queryFn: () => restockApi.list(params).then((r) => r.data),
    retry: false,
  });
  const summaryQuery = useQuery({
    queryKey: ["restock", "summary"],
    queryFn: () => restockApi.summary().then((r) => r.data),
    retry: false,
  });
  const branchesQuery = useQuery({
    queryKey: ["branches", "all"],
    queryFn: () => branchesApi.list({ page_size: 100 }).then((r) => r.data),
    retry: false,
  });

  const forbidden =
    (listQuery.error as { response?: { status?: number } } | null)?.response?.status === 403;

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["restock"] });
  };

  const refreshMutation = useMutation({
    mutationFn: () => restockApi.refresh(),
    onSuccess: () => {
      setNotice(t("refreshDone"));
      invalidate();
    },
  });

  const dismissMutation = useMutation({
    mutationFn: (id: string) => restockApi.dismiss(id),
    onSuccess: () => {
      setNotice(t("dismissed"));
      invalidate();
    },
  });

  const actMutation = useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      data: { action: string; asking_price?: number; quantity?: number };
    }) => restockApi.act(id, data),
    onSuccess: (res) => {
      setActTarget(null);
      invalidate();
      const listingId = res.data?.listing_id;
      if (listingId && actTarget?.action === "buy_from_marketplace") {
        window.location.href = `/${locale}/marketplace/${listingId}`;
        return;
      }
      setNotice(t("listingCreated"));
    },
  });

  const summary = summaryQuery.data as
    | { total: number; counts: Record<string, number>; last_computed_at: string | null }
    | undefined;
  const rows: Recommendation[] = listQuery.data?.items ?? [];
  const branches: { id: string; name: string }[] = branchesQuery.data?.items ?? [];

  const actionLabel = (a: Recommendation["action"]) =>
    ({
      buy_from_marketplace: t("actionBuy"),
      list_now: t("actionList"),
      hold: t("actionHold"),
      reorder_supplier: t("actionReorder"),
    })[a];

  const statusLabel = (s: string) =>
    ({
      new: t("statusNew"),
      viewed: t("statusViewed"),
      accepted: t("statusAccepted"),
      dismissed: t("statusDismissed"),
      acted: t("statusActed"),
      superseded: t("statusSuperseded"),
    })[s] ?? s;

  const evidenceBadge = (e: Recommendation["evidence_strength"]) => {
    const map = {
      sufficient: { label: t("evidenceSufficient"), variant: "success" as const },
      sparse: { label: t("evidenceSparse"), variant: "warning" as const },
      insufficient: { label: t("evidenceInsufficient"), variant: "secondary" as const },
    };
    return map[e];
  };

  const actionable = (r: Recommendation) =>
    !["acted", "accepted", "superseded", "dismissed"].includes(r.status);

  const openAct = (r: Recommendation) => {
    setActTarget(r);
    setActPrice(r.suggested_price != null ? String(r.suggested_price) : "");
    setActQty(r.suggested_qty > 0 ? String(r.suggested_qty) : "");
  };

  if (forbidden) {
    return (
      <Shell>
        <EmptyState
          icon={Lock}
          title={t("restricted")}
          action={
            <Link
              href={`/${locale}/org/subscription`}
              className="inline-flex h-10 items-center rounded-lg bg-brand-600 px-4 text-sm font-medium text-white hover:bg-brand-700"
            >
              {t("restrictedCta")}
            </Link>
          }
        />
      </Shell>
    );
  }

  return (
    <Shell>
      <div className="space-y-6">
        <PageHeader
          title={t("title")}
          subtitle={t("subtitle")}
          actions={
            <button
              onClick={() => refreshMutation.mutate()}
              disabled={refreshMutation.isPending}
              className="inline-flex h-10 items-center gap-2 rounded-lg bg-brand-600 px-4 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${refreshMutation.isPending ? "animate-spin" : ""}`} />
              {refreshMutation.isPending ? t("refreshing") : t("refresh")}
            </button>
          }
        />

        {notice && (
          <div className="rounded-lg bg-safe-50 px-4 py-2.5 text-sm text-safe-700 ring-1 ring-safe-200">
            {notice}
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          <KpiCard icon={Lightbulb} label={t("total")} value={summary?.total ?? "—"} tone="brand" />
          <KpiCard
            icon={Tag}
            label={t("listingCount")}
            value={(summary?.counts ?? {})["listing.new"] ?? 0}
            tone="gold"
          />
          <KpiCard
            icon={PackageSearch}
            label={t("replenishmentCount")}
            value={(summary?.counts ?? {})["replenishment.new"] ?? 0}
            tone="notice"
          />
          <KpiCard
            icon={RefreshCw}
            label={t("lastComputed")}
            value={
              summary?.last_computed_at
                ? formatDate(summary.last_computed_at, locale === "ar" ? "ar-SA" : "en-US")
                : "—"
            }
            tone="slate"
          />
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <select
            value={kind}
            onChange={(e) => {
              setKind(e.target.value);
              setPage(1);
            }}
            aria-label={t("kind")}
            className="h-9 px-3 bg-white ring-1 ring-inset ring-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="">{t("kindAll")}</option>
            <option value="replenishment">{t("kindReplenishment")}</option>
            <option value="listing">{t("kindListing")}</option>
          </select>
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            aria-label={t("statusFilter")}
            className="h-9 px-3 bg-white ring-1 ring-inset ring-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="">{t("statusAll")}</option>
            {["new", "viewed", "dismissed", "acted", "superseded"].map((s) => (
              <option key={s} value={s}>
                {statusLabel(s)}
              </option>
            ))}
          </select>
          <select
            value={branchId}
            onChange={(e) => {
              setBranchId(e.target.value);
              setPage(1);
            }}
            aria-label={t("branch")}
            className="h-9 px-3 bg-white ring-1 ring-inset ring-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="">{t("branchAll")}</option>
            {branches.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        </div>

        {listQuery.isError && !forbidden ? (
          <EmptyState icon={Lightbulb} title={t("loadError")} />
        ) : (
          <DataTable<Recommendation>
            rowKey={(r) => r.id}
            isLoading={listQuery.isLoading}
            data={rows}
            total={listQuery.data?.total ?? 0}
            page={page}
            pageSize={20}
            onPageChange={setPage}
            emptyMessage={t("empty")}
            minWidthClass="min-w-[900px]"
            columns={[
              {
                key: "product",
                header: t("product"),
                render: (r) => (
                  <div>
                    <div className="font-medium text-slate-900">
                      {(locale === "ar" ? r.product_name_ar : r.product_name) ??
                        r.product_name_ar ??
                        r.product_name ??
                        "—"}
                    </div>
                    {r.product_sku && (
                      <div className="text-xs text-slate-500 tabular-nums">{r.product_sku}</div>
                    )}
                  </div>
                ),
              },
              { key: "branch_name", header: t("branch"), hiddenOnMobile: true },
              {
                key: "action",
                header: t("action"),
                render: (r) => {
                  const Icon = ACTION_ICON[r.action];
                  return (
                    <span className="inline-flex items-center gap-1.5 text-sm text-slate-800">
                      <Icon className="h-4 w-4 text-brand-600" />
                      {actionLabel(r.action)}
                    </span>
                  );
                },
              },
              {
                key: "suggested_qty",
                header: t("suggestedQty"),
                render: (r) => (
                  <span className="tabular-nums">{r.suggested_qty > 0 ? r.suggested_qty : "—"}</span>
                ),
              },
              {
                key: "suggested_price",
                header: t("suggestedPrice"),
                hiddenOnMobile: true,
                render: (r) =>
                  r.suggested_price != null ? (
                    <span className="tabular-nums">{formatCurrency(r.suggested_price)}</span>
                  ) : (
                    "—"
                  ),
              },
              {
                key: "expiry",
                header: t("expiry"),
                render: (r) => {
                  const d = daysUntil(r.nearest_expiry_date);
                  return d !== undefined ? <ExpiryBadge daysUntilExpiry={d} /> : "—";
                },
              },
              {
                key: "evidence_strength",
                header: t("evidence"),
                hiddenOnMobile: true,
                render: (r) => {
                  const b = evidenceBadge(r.evidence_strength);
                  return <Badge variant={b.variant}>{b.label}</Badge>;
                },
              },
              {
                key: "status",
                header: tc("status"),
                hiddenOnMobile: true,
                render: (r) => <Badge variant="default">{statusLabel(r.status)}</Badge>,
              },
            ]}
            actions={(r) => (
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setDetail(r)}
                  className="h-8 w-8 inline-flex items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-brand-600"
                  title={t("viewDetails")}
                  aria-label={t("viewDetails")}
                >
                  <Eye className="h-4 w-4" />
                </button>
                {actionable(r) && r.action === "buy_from_marketplace" && r.matched_listing_id && (
                  <button
                    onClick={() =>
                      actMutation.mutate({ id: r.id, data: { action: "open_listing" } })
                    }
                    className="h-8 w-8 inline-flex items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-brand-600"
                    title={t("actBuy")}
                    aria-label={t("actBuy")}
                  >
                    <ShoppingCart className="h-4 w-4" />
                  </button>
                )}
                {actionable(r) && r.action === "list_now" && (
                  <button
                    onClick={() => openAct(r)}
                    className="h-8 w-8 inline-flex items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-brand-600"
                    title={t("actList")}
                    aria-label={t("actList")}
                  >
                    <Tag className="h-4 w-4" />
                  </button>
                )}
                {actionable(r) && (
                  <button
                    onClick={() => dismissMutation.mutate(r.id)}
                    className="h-8 w-8 inline-flex items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-red-600"
                    title={t("dismiss")}
                    aria-label={t("dismiss")}
                  >
                    <Ban className="h-4 w-4" />
                  </button>
                )}
              </div>
            )}
          />
        )}

        {/* Detail dialog */}
        <Dialog open={detail !== null} onOpenChange={(open) => !open && setDetail(null)}>
          {detail && (
            <DialogContent title={t("viewDetails")} size="lg">
              <div className="space-y-4">
                {detail.evidence_strength === "insufficient" && (
                  <div className="rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800 ring-1 ring-amber-200">
                    <div className="font-semibold">{t("insufficientData")}</div>
                    <div>{t("insufficientDataDesc")}</div>
                  </div>
                )}
                <p className="text-sm text-slate-700">
                  {locale === "ar" ? detail.reason_ar : detail.reason_en}
                </p>
                <dl className="grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-3 text-sm">
                  <div>
                    <dt className="text-slate-500">{t("onHand")}</dt>
                    <dd className="font-medium tabular-nums">{detail.on_hand_qty}</dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">{t("incoming")}</dt>
                    <dd className="font-medium tabular-nums">{detail.incoming_qty}</dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">{t("dailyVelocity")}</dt>
                    <dd className="font-medium tabular-nums">{detail.daily_velocity}</dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">{t("daysOfCover")}</dt>
                    <dd className="font-medium tabular-nums">{detail.days_of_cover ?? "—"}</dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">{t("computedAt")}</dt>
                    <dd className="font-medium">
                      {formatDate(detail.computed_at, locale === "ar" ? "ar-SA" : "en-US")}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">{t("windowDays")}</dt>
                    <dd className="font-medium tabular-nums">{String(detail.inputs?.demand_window_days ?? "—")}</dd>
                  </div>
                </dl>
              </div>
            </DialogContent>
          )}
        </Dialog>

        {/* Create listing dialog */}
        <Dialog open={actTarget !== null} onOpenChange={(open) => !open && setActTarget(null)}>
          {actTarget && (
            <DialogContent title={t("actListTitle")} description={t("actListDesc")}>
              <div className="space-y-4">
                {actTarget.suggested_price == null && (
                  <div className="rounded-lg bg-amber-50 px-4 py-2.5 text-sm text-amber-800 ring-1 ring-amber-200">
                    {t("noPriceHint")}
                  </div>
                )}
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700">
                    {t("quantity")}
                  </label>
                  <input
                    type="number"
                    min={1}
                    value={actQty}
                    onChange={(e) => setActQty(e.target.value)}
                    className="h-10 w-full rounded-lg px-3 ring-1 ring-inset ring-slate-200 focus:outline-none focus:ring-2 focus:ring-brand-500 tabular-nums"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700">
                    {t("price")}
                  </label>
                  <input
                    type="number"
                    min={0.01}
                    step="0.01"
                    value={actPrice}
                    onChange={(e) => setActPrice(e.target.value)}
                    className="h-10 w-full rounded-lg px-3 ring-1 ring-inset ring-slate-200 focus:outline-none focus:ring-2 focus:ring-brand-500 tabular-nums"
                  />
                </div>
                {actMutation.isError && (
                  <div className="rounded-lg bg-red-50 px-4 py-2.5 text-sm text-red-700 ring-1 ring-red-200">
                    {(actMutation.error as { response?: { data?: { detail?: string } } })?.response
                      ?.data?.detail ?? tc("error")}
                  </div>
                )}
                <DialogFooter>
                  <button
                    onClick={() =>
                      actMutation.mutate({
                        id: actTarget.id,
                        data: {
                          action: "create_listing",
                          asking_price: actPrice ? Number(actPrice) : undefined,
                          quantity: actQty ? Number(actQty) : undefined,
                        },
                      })
                    }
                    disabled={actMutation.isPending || !actPrice}
                    className="inline-flex h-10 items-center rounded-lg bg-brand-600 px-4 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
                  >
                    {t("createListing")}
                  </button>
                  <button
                    onClick={() => setActTarget(null)}
                    className="inline-flex h-10 items-center rounded-lg px-4 text-sm font-medium text-slate-600 ring-1 ring-inset ring-slate-200 hover:bg-slate-50"
                  >
                    {tc("cancel")}
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
