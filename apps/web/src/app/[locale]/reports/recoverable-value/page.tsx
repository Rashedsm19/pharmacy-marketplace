"use client";

import { useQuery } from "@tanstack/react-query";
import Shell from "@/components/layout/shell";
import { reportsApi } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { ExpiryBadge } from "@/components/ui/expiry-badge";
import { TrendingUp, Download, Package, Percent, ShoppingBag } from "lucide-react";
import {
  PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { PageHeader } from "@/components/ui/page-header";
import { KpiCard } from "@/components/ui/kpi-card";
import { SectionCard } from "@/components/ui/section-card";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";

const ZONE_COLORS = {
  green: "#10b981",
  yellow: "#eab308",
  orange: "#f97316",
  red: "#f43f5e",
};

export default function RecoverableValueReportPage() {
  const { data: report, isLoading } = useQuery({
    queryKey: ["report-recoverable-value"],
    queryFn: () => reportsApi.recoverableValue().then((r) => r.data),
  });

  const items = report?.items ?? [];
  const pieData = report?.by_zone
    ? [
        { name: "صالح (>180)", value: report.by_zone.green ?? 0, color: ZONE_COLORS.green },
        { name: "تنبيه (90-180)", value: report.by_zone.yellow ?? 0, color: ZONE_COLORS.yellow },
        { name: "تحذير (30-90)", value: report.by_zone.orange ?? 0, color: ZONE_COLORS.orange },
        { name: "حرج (<30)", value: report.by_zone.red ?? 0, color: ZONE_COLORS.red },
      ].filter((d) => d.value > 0)
    : [];

  return (
    <Shell>
      <div className="space-y-6">
        <PageHeader
          title={
            <span className="inline-flex items-center gap-2">
              <TrendingUp className="h-5 w-5 sm:h-6 sm:w-6 text-emerald-500" />
              لوحة القيمة القابلة للاسترداد
            </span>
          }
          subtitle="تقدير القيمة التي يمكن استرجاعها من المخزون قبل الانتهاء"
          actions={
            <Button variant="outline" size="md">
              <Download className="h-4 w-4" />
              تصدير CSV
            </Button>
          }
        />

        {/* Summary KPIs */}
        {report?.summary && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <KpiCard
              icon={TrendingUp}
              label="إجمالي القيمة القابلة للاسترداد"
              value={formatCurrency(report.summary.total_recoverable_value)}
              tone="safe"
            />
            <KpiCard
              icon={ShoppingBag}
              label="الدفعات المؤهلة للإدراج"
              value={report.summary.eligible_batches}
              tone="brand"
            />
            <KpiCard
              icon={Percent}
              label="متوسط نسبة الاسترداد"
              value={
                report.summary.avg_recovery_rate
                  ? `${report.summary.avg_recovery_rate.toFixed(1)}%`
                  : "—"
              }
              tone="gold"
            />
          </div>
        )}

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
          {/* Zone distribution pie */}
          {pieData.length > 0 && (
            <SectionCard title="توزيع القيمة حسب منطقة الانتهاء">
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={56}
                      outerRadius={96}
                      paddingAngle={2}
                      dataKey="value"
                      stroke="#ffffff"
                      strokeWidth={2}
                    >
                      {pieData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(value: number) => formatCurrency(value)}
                      contentStyle={{
                        background: "white",
                        border: "1px solid #e2e8f0",
                        borderRadius: 10,
                        fontSize: 12,
                        boxShadow: "0 4px 12px -2px rgba(15,23,42,0.08)",
                      }}
                    />
                    <Legend
                      formatter={(v) => <span className="text-xs text-slate-600">{v}</span>}
                      iconType="circle"
                      iconSize={8}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </SectionCard>
          )}

          {/* Zone value cards */}
          {report?.by_zone && (
            <SectionCard title="القيمة حسب المنطقة" noPadding>
              <div className="divide-y divide-slate-100">
                {[
                  { zone: "green" as const, label: "صالح (180+ يوم)", value: report.by_zone.green, days: 200 },
                  { zone: "yellow" as const, label: "تنبيه (90-180 يوم)", value: report.by_zone.yellow, days: 120 },
                  { zone: "orange" as const, label: "تحذير (30-90 يوم)", value: report.by_zone.orange, days: 60 },
                  { zone: "red" as const, label: "حرج (أقل من 30 يوم)", value: report.by_zone.red, days: 15 },
                ].map((item) => (
                  <div
                    key={item.zone}
                    className="flex items-center justify-between px-5 sm:px-6 py-3.5"
                  >
                    <div className="flex items-center gap-3">
                      <ExpiryBadge daysUntilExpiry={item.days} showDays={false} />
                      <span className="text-sm text-slate-700">{item.label}</span>
                    </div>
                    <span className="font-bold text-slate-900 tabular-nums">
                      {formatCurrency(item.value ?? 0)}
                    </span>
                  </div>
                ))}
              </div>
            </SectionCard>
          )}
        </div>

        {/* Top items table */}
        <SectionCard title="أعلى المنتجات قيمةً للاسترداد" noPadding>
          {isLoading ? (
            <div className="p-5 space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="h-12 bg-slate-50 rounded-lg animate-pulse" />
              ))}
            </div>
          ) : items.length === 0 ? (
            <EmptyState icon={Package} title="لا توجد بيانات" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm tabular-nums min-w-[680px]">
                <thead className="bg-[#f7efe3] border-b border-[#eadfcc]">
                  <tr>
                    <th className="text-right px-5 py-3 text-[11px] uppercase tracking-normal font-semibold text-[#7d6d58]">المنتج</th>
                    <th className="text-right px-4 py-3 text-[11px] uppercase tracking-normal font-semibold text-[#7d6d58] hidden sm:table-cell">الفرع</th>
                    <th className="text-right px-4 py-3 text-[11px] uppercase tracking-normal font-semibold text-[#7d6d58]">الكمية</th>
                    <th className="text-right px-4 py-3 text-[11px] uppercase tracking-normal font-semibold text-[#7d6d58]">القيمة التقديرية</th>
                    <th className="text-right px-5 py-3 text-[11px] uppercase tracking-normal font-semibold text-[#7d6d58]">الحالة</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100/80">
                  {items.map((item: {
                    id: string;
                    product_name_ar?: string;
                    product_name: string;
                    branch_name_ar?: string;
                    branch_name: string;
                    quantity_on_hand: number;
                    estimated_value: number;
                    days_until_expiry: number;
                  }) => (
                    <tr key={item.id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="px-5 py-3 font-medium text-slate-900">
                        {item.product_name_ar ?? item.product_name}
                      </td>
                      <td className="px-4 py-3 text-slate-600 hidden sm:table-cell">
                        {item.branch_name_ar ?? item.branch_name}
                      </td>
                      <td className="px-4 py-3 text-slate-700">{item.quantity_on_hand}</td>
                      <td className="px-4 py-3 text-emerald-700 font-semibold">
                        {formatCurrency(item.estimated_value)}
                      </td>
                      <td className="px-5 py-3">
                        <ExpiryBadge daysUntilExpiry={item.days_until_expiry} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>
      </div>
    </Shell>
  );
}
