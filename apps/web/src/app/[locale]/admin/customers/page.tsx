"use client";

/**
 * Every pharmacy on the platform, with the state of its account.
 *
 * This is where a support call starts, so the row carries what someone on a
 * phone needs before they open anything: who they are, whether the account
 * works, how much stock is at risk, and when they were last seen.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useLocale } from "next-intl";
import { Building2, Search, TriangleAlert, Users, Wallet } from "lucide-react";

import Shell from "@/components/layout/shell";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { EmptyState } from "@/components/ui/empty-state";
import { KpiCard } from "@/components/ui/kpi-card";
import { adminApi } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";

type Customer = {
  id: string;
  name: string;
  status: string;
  city?: string | null;
  commercial_registration_number?: string | null;
  users: number;
  active_users: number;
  branches: number;
  batches: number;
  units: number;
  stock_value: number;
  near_expiry: number;
  expired: number;
  active_listings: number;
  imports: number;
  sales: number;
  purchases: number;
  open_disputes: number;
  api_keys: number;
  last_activity_at?: string | null;
  created_at: string;
};

const STATUS: Record<string, { label: string; style: string }> = {
  approved: { label: "معتمدة", style: "bg-emerald-50 text-emerald-700 ring-emerald-200" },
  pending: { label: "قيد المراجعة", style: "bg-amber-50 text-amber-800 ring-amber-200" },
  suspended: { label: "موقوفة", style: "bg-red-50 text-red-700 ring-red-200" },
  rejected: { label: "مرفوضة", style: "bg-slate-100 text-slate-600 ring-slate-200" },
};

const FILTERS = [
  { value: "", label: "كل المنشآت" },
  { value: "approved", label: "معتمدة" },
  { value: "pending", label: "قيد المراجعة" },
  { value: "suspended", label: "موقوفة" },
  { value: "rejected", label: "مرفوضة" },
];

const PAGE_SIZE = 25;

export default function AdminCustomersPage() {
  const locale = useLocale();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["admin-customers", page, status, query],
    queryFn: () =>
      adminApi
        .customers({
          page,
          page_size: PAGE_SIZE,
          status_filter: status || undefined,
          search: query || undefined,
        })
        .then((r) => r.data),
  });

  const rows: Customer[] = data?.items ?? [];
  const pages = data?.pages ?? 0;

  const totals = rows.reduce(
    (acc, row) => ({
      users: acc.users + row.users,
      value: acc.value + row.stock_value,
      risk: acc.risk + row.near_expiry + row.expired,
    }),
    { users: 0, value: 0, risk: 0 }
  );

  return (
    <Shell>
      <div className="space-y-6">
        <PageHeader
          title="العملاء"
          subtitle="كل منشأة على المنصة — من هنا تبدأ أي حالة دعم"
        />

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard
            label="منشآت"
            value={(data?.total ?? 0).toLocaleString("ar-SA")}
            icon={Building2}
            tone="brand"
          />
          <KpiCard
            label="مستخدمون في هذه الصفحة"
            value={totals.users.toLocaleString("ar-SA")}
            icon={Users}
            tone="gold"
          />
          <KpiCard
            label="قيمة المخزون المعروضة"
            value={formatCurrency(totals.value)}
            icon={Wallet}
            tone="safe"
          />
          <KpiCard
            label="تشغيلات تحتاج انتباها"
            value={totals.risk.toLocaleString("ar-SA")}
            icon={TriangleAlert}
            hint="قرب الانتهاء أو منتهية"
            tone="warning"
          />
        </div>

        <SectionCard
          noPadding
          title="المنشآت"
          subtitle={
            data ? `${data.total.toLocaleString("ar-SA")} منشأة` : undefined
          }
          action={
            <div className="flex flex-wrap items-center gap-2">
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  setPage(1);
                  setQuery(search.trim());
                }}
                className="relative"
              >
                <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#a8927a]" />
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="اسم أو سجل تجاري أو بريد"
                  className="h-9 w-60 pr-9 pl-3 rounded-full bg-white ring-1 ring-inset ring-[#e1d3c0] text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </form>
              <select
                value={status}
                onChange={(event) => {
                  setStatus(event.target.value);
                  setPage(1);
                }}
                className="h-9 px-3 rounded-full bg-white ring-1 ring-inset ring-[#e1d3c0] text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                {FILTERS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          }
        >
          {isLoading ? (
            <p className="px-6 py-10 text-sm text-[#8a9089]">جاري التحميل…</p>
          ) : rows.length === 0 ? (
            <EmptyState
              icon={Building2}
              title="لا توجد منشآت مطابقة"
              description="غير التصفية أو ابحث بكلمة أخرى."
            />
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-[#fdfbf7] text-[#8a9089]">
                    <tr>
                      <th className="text-right font-medium px-5 py-2.5">المنشأة</th>
                      <th className="text-right font-medium px-3 py-2.5">الحالة</th>
                      <th className="text-right font-medium px-3 py-2.5">المستخدمون</th>
                      <th className="text-right font-medium px-3 py-2.5">المخزون</th>
                      <th className="text-right font-medium px-3 py-2.5">قرب الانتهاء</th>
                      <th className="text-right font-medium px-3 py-2.5">النشاط</th>
                      <th className="px-3 py-2.5" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#eadfcc]">
                    {rows.map((row) => {
                      const badge = STATUS[row.status] ?? STATUS.pending;
                      return (
                        <tr key={row.id} className="hover:bg-[#fdfbf7] align-top">
                          <td className="px-5 py-3">
                            <Link
                              href={`/${locale}/admin/customers/${row.id}`}
                              className="font-medium text-[#1f2a24] hover:text-brand-700"
                            >
                              {row.name}
                            </Link>
                            <div className="text-xs text-[#8a9089]">
                              {row.city ?? "—"}
                              {row.commercial_registration_number
                                ? ` · ${row.commercial_registration_number}`
                                : ""}
                            </div>
                          </td>
                          <td className="px-3 py-3">
                            <span
                              className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium ring-1 ring-inset ${badge.style}`}
                            >
                              {badge.label}
                            </span>
                            {row.open_disputes > 0 && (
                              <div className="text-xs text-red-700 mt-1">
                                {row.open_disputes.toLocaleString("ar-SA")} نزاع مفتوح
                              </div>
                            )}
                          </td>
                          <td className="px-3 py-3 tabular-nums text-[#5f665f] whitespace-nowrap">
                            {row.active_users.toLocaleString("ar-SA")}
                            <span className="text-xs text-[#8a9089]">
                              {" "}
                              / {row.users.toLocaleString("ar-SA")}
                            </span>
                            <div className="text-xs text-[#8a9089]">
                              {row.branches.toLocaleString("ar-SA")} فرع
                            </div>
                          </td>
                          <td className="px-3 py-3 tabular-nums text-[#5f665f] whitespace-nowrap">
                            {row.batches.toLocaleString("ar-SA")} تشغيلة
                            <div className="text-xs text-[#8a9089]">
                              {formatCurrency(row.stock_value)}
                            </div>
                          </td>
                          <td className="px-3 py-3 tabular-nums whitespace-nowrap">
                            <span className="text-amber-700">
                              {row.near_expiry.toLocaleString("ar-SA")}
                            </span>
                            {row.expired > 0 && (
                              <span className="text-red-700">
                                {" "}
                                · {row.expired.toLocaleString("ar-SA")} منتهية
                              </span>
                            )}
                          </td>
                          <td className="px-3 py-3 text-xs text-[#8a9089] whitespace-nowrap">
                            {row.last_activity_at
                              ? formatDate(row.last_activity_at, locale)
                              : "لم يستخدم بعد"}
                            <div>
                              {row.imports.toLocaleString("ar-SA")} استيراد ·{" "}
                              {row.sales.toLocaleString("ar-SA")} بيع
                            </div>
                          </td>
                          <td className="px-3 py-3 text-left">
                            <Link
                              href={`/${locale}/admin/customers/${row.id}`}
                              className="inline-flex h-8 px-4 items-center rounded-full text-xs ring-1 ring-inset ring-[#e1d3c0] text-[#5f665f] hover:bg-[#fbf7f0] whitespace-nowrap"
                            >
                              فتح الملف
                            </Link>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {pages > 1 && (
                <div className="flex items-center justify-between px-5 py-3 border-t border-[#eadfcc]">
                  <button
                    type="button"
                    onClick={() => setPage((c) => Math.max(1, c - 1))}
                    disabled={page === 1}
                    className="h-8 px-4 rounded-full text-sm ring-1 ring-inset ring-[#e1d3c0] text-[#5f665f] disabled:opacity-40 hover:bg-[#fbf7f0]"
                  >
                    السابق
                  </button>
                  <span className="text-xs text-[#8a9089]">
                    صفحة {page.toLocaleString("ar-SA")} من {pages.toLocaleString("ar-SA")}
                  </span>
                  <button
                    type="button"
                    onClick={() => setPage((c) => Math.min(pages, c + 1))}
                    disabled={page >= pages}
                    className="h-8 px-4 rounded-full text-sm ring-1 ring-inset ring-[#e1d3c0] text-[#5f665f] disabled:opacity-40 hover:bg-[#fbf7f0]"
                  >
                    التالي
                  </button>
                </div>
              )}
            </>
          )}
        </SectionCard>
      </div>
    </Shell>
  );
}
