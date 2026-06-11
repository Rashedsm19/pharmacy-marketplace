"use client";

import { useQuery } from "@tanstack/react-query";
import Shell from "@/components/layout/shell";
import { reportsApi } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Loader2, Download, BarChart2 } from "lucide-react";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from "recharts";

export default function BranchComparisonReportPage() {
  const { data: report, isLoading } = useQuery({
    queryKey: ["report-branch-comparison"],
    queryFn: () => reportsApi.branchComparison().then((r) => r.data),
  });

  const branches = report?.branches ?? [];
  const chartData = branches.map((b: {
    branch_name_ar?: string;
    branch_name: string;
    active_listings: number;
    completed_transactions: number;
    near_expiry_count: number;
    recovered_value: number;
    total_batches: number;
  }) => ({
    name: b.branch_name_ar ?? b.branch_name,
    "عروض نشطة": b.active_listings,
    "معاملات مكتملة": b.completed_transactions,
    "قريب الانتهاء": b.near_expiry_count,
  }));

  return (
    <Shell>
      <div className="space-y-6">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-2">
            <BarChart2 className="h-6 w-6 text-brand-500" />
            <h1 className="text-2xl font-bold text-gray-900">مقارنة أداء الفروع</h1>
          </div>
          <button className="flex items-center gap-2 border border-gray-300 text-gray-600 px-4 py-2 rounded-lg text-sm hover:bg-gray-50">
            <Download className="h-4 w-4" />
            تصدير CSV
          </button>
        </div>

        {/* Summary cards */}
        {report?.summary && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
              <p className="text-gray-400 text-xs">عدد الفروع</p>
              <p className="font-bold text-2xl text-gray-900 mt-1">{report.summary.total_branches}</p>
            </div>
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
              <p className="text-gray-400 text-xs">أفضل فرع (مبيعات)</p>
              <p className="font-bold text-sm text-gray-900 mt-1 truncate">
                {report.summary.top_branch_name_ar ?? report.summary.top_branch_name ?? "—"}
              </p>
            </div>
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
              <p className="text-gray-400 text-xs">إجمالي القيمة المستردة</p>
              <p className="font-bold text-gray-900 mt-1">{formatCurrency(report.summary.total_recovered_value ?? 0)}</p>
            </div>
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
              <p className="text-gray-400 text-xs">متوسط التعاملات لكل فرع</p>
              <p className="font-bold text-2xl text-gray-900 mt-1">
                {report.summary.avg_transactions_per_branch?.toFixed(1) ?? "—"}
              </p>
            </div>
          </div>
        )}

        {/* Bar chart comparison */}
        {chartData.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h2 className="font-semibold text-gray-900 mb-4">مقارنة مؤشرات الأداء الرئيسية</h2>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="عروض نشطة" fill="#0AA39B" radius={[2, 2, 0, 0]} />
                  <Bar dataKey="معاملات مكتملة" fill="#22c55e" radius={[2, 2, 0, 0]} />
                  <Bar dataKey="قريب الانتهاء" fill="#f97316" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Branch table */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          {isLoading ? (
            <div className="flex items-center justify-center h-48">
              <Loader2 className="h-6 w-6 animate-spin text-brand-600" />
            </div>
          ) : branches.length === 0 ? (
            <div className="text-center py-16 text-gray-500">لا توجد بيانات فروع</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">الفرع</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">الحالة</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">الدفعات</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">قريب الانتهاء</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">العروض</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">المعاملات</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">القيمة المستردة</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {branches.map((b: {
                  branch_id: string;
                  branch_name_ar?: string;
                  branch_name: string;
                  is_active: boolean;
                  storage_condition_status?: string;
                  total_batches: number;
                  near_expiry_count: number;
                  active_listings: number;
                  completed_transactions: number;
                  recovered_value: number;
                }) => (
                  <tr key={b.branch_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-900">
                      {b.branch_name_ar ?? b.branch_name}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5">
                        <Badge variant={b.is_active ? "success" : "default"}>
                          {b.is_active ? "نشط" : "غير نشط"}
                        </Badge>
                        {b.storage_condition_status && (
                          <Badge variant={b.storage_condition_status === "compliant" ? "success" : "danger"}>
                            {b.storage_condition_status === "compliant" ? "مطابق" : "غير مطابق"}
                          </Badge>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-600">{b.total_batches}</td>
                    <td className="px-4 py-3">
                      <span className={`font-semibold ${b.near_expiry_count > 0 ? "text-orange-600" : "text-gray-400"}`}>
                        {b.near_expiry_count}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-600">{b.active_listings}</td>
                    <td className="px-4 py-3 text-gray-600">{b.completed_transactions}</td>
                    <td className="px-4 py-3 text-green-600 font-semibold">
                      {formatCurrency(b.recovered_value)}
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
