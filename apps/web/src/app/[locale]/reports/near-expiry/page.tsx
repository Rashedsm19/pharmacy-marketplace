"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Shell from "@/components/layout/shell";
import { ExpiryBadge } from "@/components/ui/expiry-badge";
import { reportsApi, branchesApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Loader2, Download } from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";

export default function NearExpiryReportPage() {
  const [branchId, setBranchId] = useState("");
  const [days, setDays] = useState(90);

  const { data: branches } = useQuery({
    queryKey: ["branches"],
    queryFn: () => branchesApi.list().then((r) => r.data),
  });

  const { data: report, isLoading } = useQuery({
    queryKey: ["report-near-expiry", branchId, days],
    queryFn: () =>
      reportsApi.nearExpiry({ branch_id: branchId || undefined, days }).then((r) => r.data),
  });

  const branchList = Array.isArray(branches) ? branches : (branches?.items ?? []);
  const items = report?.items ?? [];
  const chartData = report?.by_zone ?? [];

  return (
    <Shell>
      <div className="space-y-6">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <h1 className="text-2xl font-bold text-gray-900">تقرير قرب انتهاء الصلاحية</h1>
          <button className="flex items-center gap-2 border border-gray-300 text-gray-600 px-4 py-2 rounded-lg text-sm hover:bg-gray-50">
            <Download className="h-4 w-4" />
            تصدير CSV
          </button>
        </div>

        {/* Filters */}
        <div className="flex gap-3 flex-wrap">
          <select
            value={branchId}
            onChange={(e) => setBranchId(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="">جميع الفروع</option>
            {branchList.map((b: { id: string; name_ar?: string; name: string }) => (
              <option key={b.id} value={b.id}>{b.name_ar ?? b.name}</option>
            ))}
          </select>
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value={30}>خلال 30 يوم</option>
            <option value={90}>خلال 90 يوم</option>
            <option value={180}>خلال 180 يوم</option>
          </select>
        </div>

        {/* Summary cards */}
        {report?.summary && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { label: "إجمالي الدفعات", value: report.summary.total_batches, color: "text-gray-900" },
              { label: "أقل من 30 يوم", value: report.summary.critical, color: "text-red-600" },
              { label: "30-90 يوم", value: report.summary.warning, color: "text-orange-600" },
              { label: "90-180 يوم", value: report.summary.notice, color: "text-yellow-600" },
            ].map((item) => (
              <div key={item.label} className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
                <p className="text-gray-400 text-xs">{item.label}</p>
                <p className={`font-bold text-2xl mt-1 ${item.color}`}>{item.value ?? 0}</p>
              </div>
            ))}
          </div>
        )}

        {/* Chart */}
        {chartData.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h2 className="font-semibold text-gray-900 mb-4">توزيع حسب الفرع والمنطقة</h2>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="branch_name" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="critical" name="حرج" fill="#ef4444" />
                  <Bar dataKey="warning" name="تحذير" fill="#f97316" />
                  <Bar dataKey="notice" name="تنبيه" fill="#eab308" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Table */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          {isLoading ? (
            <div className="flex items-center justify-center h-48">
              <Loader2 className="h-6 w-6 animate-spin text-brand-600" />
            </div>
          ) : items.length === 0 ? (
            <div className="text-center py-16 text-gray-500">لا توجد دفعات قريبة الانتهاء</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">المنتج</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">الدفعة</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">الفرع</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">الكمية</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">تاريخ الانتهاء</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">الحالة</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {items.map((item: {
                  id: string;
                  product_name_ar?: string;
                  product_name: string;
                  batch_number: string;
                  branch_name_ar?: string;
                  branch_name: string;
                  quantity_on_hand: number;
                  expiry_date: string;
                  days_until_expiry: number;
                }) => (
                  <tr key={item.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-900">
                      {item.product_name_ar ?? item.product_name}
                    </td>
                    <td className="px-4 py-3 text-gray-600" dir="ltr">{item.batch_number}</td>
                    <td className="px-4 py-3 text-gray-600">{item.branch_name_ar ?? item.branch_name}</td>
                    <td className="px-4 py-3 text-gray-600">{item.quantity_on_hand}</td>
                    <td className="px-4 py-3 text-gray-600">{formatDate(item.expiry_date, "ar-SA")}</td>
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
