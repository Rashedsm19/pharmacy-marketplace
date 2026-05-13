"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useLocale } from "next-intl";
import Shell from "@/components/layout/shell";
import { DataTable } from "@/components/ui/data-table";
import { ExpiryBadge } from "@/components/ui/expiry-badge";
import { inventoryApi } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import Link from "next/link";
import { Eye, AlertTriangle, AlertOctagon, BellRing } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { KpiCard } from "@/components/ui/kpi-card";

export default function NearExpiryPage() {
  const locale = useLocale();
  const [days, setDays] = useState(180);

  const { data = [], isLoading } = useQuery({
    queryKey: ["near-expiry", days],
    queryFn: () => inventoryApi.listNearExpiry(days).then((r) => r.data),
  });

  const redCount = data.filter((b: { expiry_zone?: string }) => b.expiry_zone === "red").length;
  const orangeCount = data.filter((b: { expiry_zone?: string }) => b.expiry_zone === "orange").length;
  const yellowCount = data.filter((b: { expiry_zone?: string }) => b.expiry_zone === "yellow").length;

  return (
    <Shell>
      <div className="space-y-6">
        <PageHeader
          title="الدفعات قرب انتهاء الصلاحية"
          subtitle="ركّز على الدفعات الأكثر إلحاحاً قبل أن تنتهي"
          actions={
            <div className="flex items-center gap-2">
              <label className="text-xs font-medium text-slate-600">عرض خلال</label>
              <select
                value={days}
                onChange={(e) => setDays(Number(e.target.value))}
                className="h-9 px-3 bg-white ring-1 ring-inset ring-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                <option value={30}>30 يوم</option>
                <option value={90}>90 يوم</option>
                <option value={180}>180 يوم</option>
              </select>
            </div>
          }
        />

        {/* Summary KPIs */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <KpiCard
            icon={AlertOctagon}
            label="حرج (< 30 يوم)"
            value={redCount}
            tone="critical"
            hint="دفعة"
          />
          <KpiCard
            icon={AlertTriangle}
            label="تحذير (30-90 يوم)"
            value={orangeCount}
            tone="warning"
            hint="دفعة"
          />
          <KpiCard
            icon={BellRing}
            label="تنبيه (90-180 يوم)"
            value={yellowCount}
            tone="notice"
            hint="دفعة"
          />
        </div>

        <DataTable
          rowKey={(r: { id: string }) => r.id}
          isLoading={isLoading}
          data={data}
          total={data.length}
          emptyMessage="لا توجد دفعات قرب الانتهاء"
          minWidthClass="min-w-[820px]"
          columns={[
            {
              key: "product_name_ar",
              header: "المنتج",
              render: (r: { product_name_ar?: string }) => (
                <span className="font-medium text-slate-900">{r.product_name_ar ?? "—"}</span>
              ),
            },
            { key: "branch_name", header: "الفرع", hiddenOnMobile: true },
            { key: "batch_number", header: "رقم الدفعة", hiddenOnMobile: true },
            {
              key: "expiry_date",
              header: "تاريخ الانتهاء",
              hiddenOnMobile: true,
              render: (r: { expiry_date?: string }) =>
                r.expiry_date ? formatDate(r.expiry_date, "ar-SA") : "—",
            },
            {
              key: "days_until_expiry",
              header: "الحالة",
              render: (r: { days_until_expiry?: number }) =>
                r.days_until_expiry !== undefined ? (
                  <ExpiryBadge daysUntilExpiry={r.days_until_expiry} />
                ) : "—",
            },
            { key: "quantity_available", header: "الكمية" },
            {
              key: "unit_cost",
              header: "القيمة",
              hiddenOnMobile: true,
              render: (r: { unit_cost?: number; quantity_available?: number }) =>
                r.unit_cost
                  ? <span className="text-slate-700 tabular-nums">{formatCurrency((r.unit_cost ?? 0) * (r.quantity_available ?? 0))}</span>
                  : "—",
            },
          ]}
          actions={(r: { id: string }) => (
            <Link
              href={`/${locale}/inventory/batches/${r.id}`}
              className="h-8 w-8 inline-flex items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-brand-600"
              title="عرض"
            >
              <Eye className="h-4 w-4" />
            </Link>
          )}
        />
      </div>
    </Shell>
  );
}
