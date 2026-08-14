"use client";

/**
 * All inventory on the platform, across every pharmacy.
 *
 * The org-scoped screens deliberately cannot show this, so each row names the
 * pharmacy that holds the stock. The totals describe the platform, not the page
 * — the page is only a window onto it.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useLocale } from "next-intl";
import { Boxes, Building2, PackageX, Search, TriangleAlert } from "lucide-react";

import Shell from "@/components/layout/shell";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { EmptyState } from "@/components/ui/empty-state";
import { KpiCard } from "@/components/ui/kpi-card";
import { adminApi } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";

type Row = {
  id: string;
  organization_name: string;
  branch_name?: string | null;
  product_name: string;
  product_sku?: string | null;
  is_draft_product: boolean;
  batch_number: string;
  expiry_date: string;
  days_remaining: number;
  quantity: number;
  quantity_available: number;
  unit_cost?: number | null;
  status: string;
  zone: string;
};

const ZONES: { value: string; label: string }[] = [
  { value: "", label: "كل الفترات" },
  { value: "expired", label: "منتهية" },
  { value: "red", label: "أقل من ٣٠ يوماً" },
  { value: "orange", label: "٣٠ – ٩٠ يوماً" },
  { value: "yellow", label: "٩٠ – ١٨٠ يوماً" },
  { value: "green", label: "أكثر من ١٨٠ يوماً" },
];

const ZONE_STYLE: Record<string, string> = {
  expired: "bg-slate-800 text-white ring-slate-800",
  red: "bg-red-50 text-red-700 ring-red-200",
  orange: "bg-orange-50 text-orange-700 ring-orange-200",
  yellow: "bg-amber-50 text-amber-800 ring-amber-200",
  green: "bg-emerald-50 text-emerald-700 ring-emerald-200",
};

const ZONE_LABEL: Record<string, string> = {
  expired: "منتهية",
  red: "عاجل",
  orange: "قريب",
  yellow: "متوسط",
  green: "سليم",
};

const PAGE_SIZE = 25;

export default function AdminInventoryPage() {
  const locale = useLocale();
  const [page, setPage] = useState(1);
  const [zone, setZone] = useState("");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["admin-inventory", page, zone, query],
    queryFn: () =>
      adminApi
        .allInventory({
          page,
          page_size: PAGE_SIZE,
          zone: zone || undefined,
          search: query || undefined,
        })
        .then((r) => r.data),
  });

  const rows: Row[] = data?.items ?? [];
  const totals = data?.totals;
  const pages = data?.pages ?? 0;

  return (
    <Shell>
      <div className="space-y-6">
        <PageHeader
          title="مخزون المنصة"
          subtitle="كل الأصناف عبر جميع المنشآت — لا تراه المنشآت عن بعضها"
        />

        {totals && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard
              label="منشآت لديها مخزون"
              value={totals.organizations.toLocaleString("ar-SA")}
              icon={Building2}
              tone="brand"
            />
            <KpiCard
              label="إجمالي التشغيلات"
              value={totals.batches.toLocaleString("ar-SA")}
              icon={Boxes}
              hint={`${totals.units.toLocaleString("ar-SA")} وحدة متاحة · ${formatCurrency(
                totals.estimated_value
              )}`}
              tone="gold"
            />
            <KpiCard
              label="قرب الانتهاء"
              value={totals.near_expiry_batches.toLocaleString("ar-SA")}
              icon={TriangleAlert}
              hint="خلال ١٨٠ يوماً"
              tone="warning"
            />
            <KpiCard
              label="منتهية بالفعل"
              value={totals.expired_batches.toLocaleString("ar-SA")}
              icon={PackageX}
              hint="تحتاج إخراجاً من المخزون"
              tone="critical"
            />
          </div>
        )}

        <SectionCard
          noPadding
          title="التشغيلات"
          subtitle={
            data
              ? `${data.total.toLocaleString("ar-SA")} تشغيلة مطابقة للتصفية`
              : undefined
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
                  placeholder="دواء أو كود أو رقم تشغيلة"
                  className="h-9 w-56 pr-9 pl-3 rounded-full bg-white ring-1 ring-inset ring-[#e1d3c0] text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </form>
              <select
                value={zone}
                onChange={(event) => {
                  setZone(event.target.value);
                  setPage(1);
                }}
                className="h-9 px-3 rounded-full bg-white ring-1 ring-inset ring-[#e1d3c0] text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                {ZONES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          }
        >
          {isLoading ? (
            <p className="px-6 py-10 text-sm text-[#8a9089]">جارٍ التحميل…</p>
          ) : rows.length === 0 ? (
            <EmptyState
              icon={Boxes}
              title="لا توجد تشغيلات مطابقة"
              description="غيّر التصفية أو ابحث بكلمة أخرى."
            />
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-[#fdfbf7] text-[#8a9089]">
                    <tr>
                      <th className="text-right font-medium px-5 py-2.5">المنشأة</th>
                      <th className="text-right font-medium px-3 py-2.5">الدواء</th>
                      <th className="text-right font-medium px-3 py-2.5">التشغيلة</th>
                      <th className="text-right font-medium px-3 py-2.5">الانتهاء</th>
                      <th className="text-right font-medium px-3 py-2.5">المتاح</th>
                      <th className="text-right font-medium px-3 py-2.5">التكلفة</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#eadfcc]">
                    {rows.map((row) => (
                      <tr key={row.id} className="hover:bg-[#fdfbf7]">
                        <td className="px-5 py-3">
                          <div className="font-medium text-[#1f2a24]">
                            {row.organization_name}
                          </div>
                          {row.branch_name && (
                            <div className="text-xs text-[#8a9089]">
                              {row.branch_name}
                            </div>
                          )}
                        </td>
                        <td className="px-3 py-3">
                          <div className="text-[#1f2a24] flex items-center gap-2">
                            <span className="truncate max-w-[14rem]">
                              {row.product_name}
                            </span>
                            {row.is_draft_product && (
                              <span className="shrink-0 px-1.5 py-0.5 rounded text-[10px] bg-[#f4eadf] text-[#7b5411]">
                                مسودة
                              </span>
                            )}
                          </div>
                          {row.product_sku && (
                            <code
                              dir="ltr"
                              className="text-xs text-[#8a9089] font-mono"
                            >
                              {row.product_sku}
                            </code>
                          )}
                        </td>
                        <td className="px-3 py-3">
                          <code dir="ltr" className="text-xs font-mono text-[#5f665f]">
                            {row.batch_number}
                          </code>
                        </td>
                        <td className="px-3 py-3 whitespace-nowrap">
                          <span
                            className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ring-1 ring-inset ${
                              ZONE_STYLE[row.zone] ?? ZONE_STYLE.green
                            }`}
                          >
                            {ZONE_LABEL[row.zone] ?? row.zone}
                          </span>
                          <div className="text-xs text-[#8a9089] mt-0.5">
                            {formatDate(row.expiry_date, locale)}
                            {row.days_remaining > 0
                              ? ` · ${row.days_remaining.toLocaleString("ar-SA")} يوم`
                              : ""}
                          </div>
                        </td>
                        <td className="px-3 py-3 tabular-nums text-[#1f2a24]">
                          {row.quantity_available.toLocaleString("ar-SA")}
                          <span className="text-xs text-[#8a9089]">
                            {" "}
                            / {row.quantity.toLocaleString("ar-SA")}
                          </span>
                        </td>
                        <td className="px-3 py-3 tabular-nums text-[#5f665f] whitespace-nowrap">
                          {row.unit_cost != null ? formatCurrency(row.unit_cost) : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {pages > 1 && (
                <div className="flex items-center justify-between px-5 py-3 border-t border-[#eadfcc]">
                  <button
                    type="button"
                    onClick={() => setPage((current) => Math.max(1, current - 1))}
                    disabled={page === 1}
                    className="h-8 px-4 rounded-full text-sm ring-1 ring-inset ring-[#e1d3c0] text-[#5f665f] disabled:opacity-40 hover:bg-[#fbf7f0]"
                  >
                    السابق
                  </button>
                  <span className="text-xs text-[#8a9089]">
                    صفحة {page.toLocaleString("ar-SA")} من{" "}
                    {pages.toLocaleString("ar-SA")}
                  </span>
                  <button
                    type="button"
                    onClick={() => setPage((current) => Math.min(pages, current + 1))}
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
