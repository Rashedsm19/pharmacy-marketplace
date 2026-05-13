"use client";

import { useQuery } from "@tanstack/react-query";
import Shell from "@/components/layout/shell";
import { reportsApi } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { ExpiryBadge } from "@/components/ui/expiry-badge";
import { Loader2, TrendingUp, Download } from "lucide-react";
import {
  PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer,
} from "recharts";

const ZONE_COLORS = {
  green: "#22c55e",
  yellow: "#eab308",
  orange: "#f97316",
  red: "#ef4444",
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
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-6 w-6 text-green-500" />
            <h1 className="text-2xl font-bold text-gray-900">لوحة القيمة القابلة للاسترداد</h1>
          </div>
          <button className="flex items-center gap-2 border border-gray-300 text-gray-600 px-4 py-2 rounded-lg text-sm hover:bg-gray-50">
            <Download className="h-4 w-4" />
            تصدير CSV
          </button>
        </div>

        {/* Summary */}
        {report?.summary && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-green-50 border border-green-200 rounded-xl p-5">
              <p className="text-green-700 text-sm font-medium">إجمالي القيمة القابلة للاسترداد</p>
              <p className="font-bold text-2xl text-green-800 mt-1">
                {formatCurrency(report.summary.total_recoverable_value)}
              </p>
            </div>
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <p className="text-gray-500 text-sm">الدفعات المؤهلة للإدراج</p>
              <p className="font-bold text-2xl text-gray-900 mt-1">{report.summary.eligible_batches}</p>
            </div>
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <p className="text-gray-500 text-sm">متوسط نسبة الاسترداد</p>
              <p className="font-bold text-2xl text-gray-900 mt-1">
                {report.summary.avg_recovery_rate ? `${report.summary.avg_recovery_rate.toFixed(1)}%` : "—"}
              </p>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          {/* Zone distribution pie */}
          {pieData.length > 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
              <h2 className="font-semibold text-gray-900 mb-4">توزيع القيمة حسب منطقة الانتهاء</h2>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={100}
                      paddingAngle={2}
                      dataKey="value"
                    >
                      {pieData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(value: number) => formatCurrency(value)} />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Zone value cards */}
          {report?.by_zone && (
            <div className="space-y-3">
              {[
                { zone: "green" as const, label: "صالح (180+ يوم)", value: report.by_zone.green },
                { zone: "yellow" as const, label: "تنبيه (90-180 يوم)", value: report.by_zone.yellow },
                { zone: "orange" as const, label: "تحذير (30-90 يوم)", value: report.by_zone.orange },
                { zone: "red" as const, label: "حرج (أقل من 30 يوم)", value: report.by_zone.red },
              ].map((item) => (
                <div key={item.zone} className="bg-white rounded-xl shadow-sm border border-gray-100 p-4 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <ExpiryBadge daysUntilExpiry={
                      item.zone === "green" ? 200 :
                      item.zone === "yellow" ? 120 :
                      item.zone === "orange" ? 60 : 15
                    } />
                    <span className="text-sm text-gray-700">{item.label}</span>
                  </div>
                  <span className="font-bold text-gray-900">{formatCurrency(item.value ?? 0)}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Top items table */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <div className="p-4 border-b border-gray-100">
            <h2 className="font-semibold text-gray-900">أعلى المنتجات قيمةً للاسترداد</h2>
          </div>
          {isLoading ? (
            <div className="flex items-center justify-center h-48">
              <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
            </div>
          ) : items.length === 0 ? (
            <div className="text-center py-12 text-gray-500">لا توجد بيانات</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">المنتج</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">الفرع</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">الكمية</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">القيمة التقديرية</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">الأيام المتبقية</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
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
                  <tr key={item.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-900">
                      {item.product_name_ar ?? item.product_name}
                    </td>
                    <td className="px-4 py-3 text-gray-600">{item.branch_name_ar ?? item.branch_name}</td>
                    <td className="px-4 py-3 text-gray-600">{item.quantity_on_hand}</td>
                    <td className="px-4 py-3 text-green-600 font-semibold">
                      {formatCurrency(item.estimated_value)}
                    </td>
                    <td className="px-4 py-3">
                      <ExpiryBadge daysUntilExpiry={item.days_until_expiry} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </Shell>
  );
}
