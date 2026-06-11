"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Shell from "@/components/layout/shell";
import { reportsApi } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import { Loader2, Download, TrendingDown } from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";

export default function ExpiredLossReportPage() {
  const currentYear = new Date().getFullYear();
  const [year, setYear] = useState(currentYear);
  const [month, setMonth] = useState<number | "">(new Date().getMonth() + 1);

  const { data: report, isLoading } = useQuery({
    queryKey: ["report-expired-loss", year, month],
    queryFn: () =>
      reportsApi.expiredLoss({ year, month: month || undefined }).then((r) => r.data),
  });

  const items = report?.items ?? [];
  const chartData = report?.by_month ?? [];

  return (
    <Shell>
      <div className="space-y-6">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-2">
            <TrendingDown className="h-6 w-6 text-red-500" />
            <h1 className="text-2xl font-bold text-gray-900">تقرير خسائر الصلاحية</h1>
          </div>
          <button className="flex items-center gap-2 border border-gray-300 text-gray-600 px-4 py-2 rounded-lg text-sm hover:bg-gray-50">
            <Download className="h-4 w-4" />
            تصدير CSV
          </button>
        </div>

        {/* Filters */}
        <div className="flex gap-3 flex-wrap">
          <select
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            {[currentYear, currentYear - 1, currentYear - 2].map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
          <select
            value={month}
            onChange={(e) => setMonth(e.target.value ? Number(e.target.value) : "")}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="">جميع الأشهر</option>
            {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
              <option key={m} value={m}>
                {new Date(2000, m - 1).toLocaleDateString("ar-SA", { month: "long" })}
              </option>
            ))}
          </select>
        </div>

        {/* Summary cards */}
        {report?.summary && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-red-50 border border-red-200 rounded-xl p-5">
              <p className="text-red-600 text-sm font-medium">إجمالي الخسارة</p>
              <p className="font-bold text-2xl text-red-700 mt-1">
                {formatCurrency(report.summary.total_loss_value)}
              </p>
            </div>
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <p className="text-gray-500 text-sm">عدد الدفعات المنتهية</p>
              <p className="font-bold text-2xl text-gray-900 mt-1">{report.summary.total_batches}</p>
            </div>
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <p className="text-gray-500 text-sm">إجمالي الوحدات</p>
              <p className="font-bold text-2xl text-gray-900 mt-1">{report.summary.total_units}</p>
            </div>
          </div>
        )}

        {/* Monthly trend chart */}
        {chartData.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h2 className="font-semibold text-gray-900 mb-4">الخسائر الشهرية</h2>
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="month_label" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(value: number) => formatCurrency(value)} />
                  <Bar dataKey="loss_value" name="قيمة الخسارة" fill="#ef4444" radius={[4, 4, 0, 0]} />
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
            <div className="text-center py-16 text-gray-500">لا توجد دفعات منتهية في هذه الفترة</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">المنتج</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">الدفعة</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">الفرع</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">الكمية المفقودة</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">قيمة الخسارة</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">تاريخ الانتهاء</th>
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
                  quantity_expired: number;
                  loss_value: number;
                  expiry_date: string;
                }) => (
                  <tr key={item.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-900">
                      {item.product_name_ar ?? item.product_name}
                    </td>
                    <td className="px-4 py-3 text-gray-600" dir="ltr">{item.batch_number}</td>
                    <td className="px-4 py-3 text-gray-600">{item.branch_name_ar ?? item.branch_name}</td>
                    <td className="px-4 py-3 text-gray-600">{item.quantity_expired}</td>
                    <td className="px-4 py-3 text-red-600 font-semibold">
                      {formatCurrency(item.loss_value)}
                    </td>
                    <td className="px-4 py-3 text-gray-500">{formatDate(item.expiry_date, "ar-SA")}</td>
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
