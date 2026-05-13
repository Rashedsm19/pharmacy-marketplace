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
import { Eye } from "lucide-react";

export default function NearExpiryPage() {
  const locale = useLocale();
  const [days, setDays] = useState(180);

  const { data = [], isLoading } = useQuery({
    queryKey: ["near-expiry", days],
    queryFn: () => inventoryApi.listNearExpiry(days).then((r) => r.data),
  });

  return (
    <Shell>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">الدفعات قرب انتهاء الصلاحية</h1>
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-600">عرض الدفعات خلال</label>
            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value={30}>30 يوم</option>
              <option value={90}>90 يوم</option>
              <option value={180}>180 يوم</option>
            </select>
          </div>
        </div>

        {/* Summary cards */}
        <div className="grid grid-cols-3 gap-4">
          {[
            { zone: "red", label: "حرج (< 30 يوم)", cls: "bg-red-50 border-red-200" },
            { zone: "orange", label: "تحذير (30-90 يوم)", cls: "bg-orange-50 border-orange-200" },
            { zone: "yellow", label: "تنبيه (90-180 يوم)", cls: "bg-yellow-50 border-yellow-200" },
          ].map(({ zone, label, cls }) => {
            const count = data.filter((b: { expiry_zone?: string }) => b.expiry_zone === zone).length;
            return (
              <div key={zone} className={`rounded-xl p-4 border ${cls}`}>
                <p className="text-2xl font-bold">{count}</p>
                <p className="text-sm text-gray-600">{label}</p>
              </div>
            );
          })}
        </div>

        <DataTable
          rowKey={(r: { id: string }) => r.id}
          isLoading={isLoading}
          data={data}
          total={data.length}
          emptyMessage="لا توجد دفعات قرب الانتهاء"
          columns={[
            {
              key: "product_name_ar",
              header: "المنتج",
              render: (r: { product_name_ar?: string }) => r.product_name_ar ?? "—",
            },
            { key: "branch_name", header: "الفرع" },
            { key: "batch_number", header: "رقم الدفعة" },
            {
              key: "expiry_date",
              header: "تاريخ الانتهاء",
              render: (r: { expiry_date?: string }) =>
                r.expiry_date ? formatDate(r.expiry_date, "ar-SA") : "—",
            },
            {
              key: "days_until_expiry",
              header: "الأيام المتبقية",
              render: (r: { days_until_expiry?: number }) =>
                r.days_until_expiry !== undefined ? (
                  <ExpiryBadge daysUntilExpiry={r.days_until_expiry} />
                ) : "—",
            },
            { key: "quantity_available", header: "الكمية" },
            {
              key: "unit_cost",
              header: "القيمة المقدرة",
              render: (r: { unit_cost?: number; quantity_available?: number }) =>
                r.unit_cost
                  ? formatCurrency((r.unit_cost ?? 0) * (r.quantity_available ?? 0))
                  : "—",
            },
          ]}
          actions={(r: { id: string }) => (
            <Link
              href={`/${locale}/inventory/batches/${r.id}`}
              className="p-1.5 hover:bg-gray-100 rounded text-gray-500 hover:text-blue-600"
            >
              <Eye className="h-4 w-4" />
            </Link>
          )}
        />
      </div>
    </Shell>
  );
}
