"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Shell from "@/components/layout/shell";
import { reportsApi } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { Loader2, Download, Star } from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";

export default function TopProductsReportPage() {
  const [limit, setLimit] = useState(10);
  const [period, setPeriod] = useState<"30" | "90" | "180" | "365">("90");

  const { data: report, isLoading } = useQuery({
    queryKey: ["report-top-products", limit, period],
    queryFn: () =>
      reportsApi.topProducts({ limit, period_days: Number(period) }).then((r) => r.data),
  });

  const items = report?.items ?? [];

  return (
    <Shell>
      <div className="space-y-6">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-2">
            <Star className="h-6 w-6 text-yellow-500" />
            <h1 className="text-2xl font-bold text-gray-900">أكثر المنتجات طلباً</h1>
          </div>
          <button className="flex items-center gap-2 border border-gray-300 text-gray-600 px-4 py-2 rounded-lg text-sm hover:bg-gray-50">
            <Download className="h-4 w-4" />
            تصدير CSV
          </button>
        </div>

        {/* Filters */}
        <div className="flex gap-3 flex-wrap">
          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value as typeof period)}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="30">آخر 30 يوم</option>
            <option value="90">آخر 90 يوم</option>
            <option value="180">آخر 180 يوم</option>
            <option value="365">آخر سنة</option>
          </select>
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value={5}>أفضل 5</option>
            <option value={10}>أفضل 10</option>
            <option value={20}>أفضل 20</option>
          </select>
        </div>

        {/* Bar chart */}
        {items.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h2 className="font-semibold text-gray-900 mb-4">المنتجات حسب عدد الطلبات</h2>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={items.slice(0, 10).map((i: { product_name_ar?: string; product_name: string; offer_count: number }) => ({
                    name: i.product_name_ar ?? i.product_name,
                    offers: i.offer_count,
                  }))}
                  layout="vertical"
                  margin={{ top: 5, right: 30, left: 80, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis type="number" tick={{ fontSize: 11 }} />
                  <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={80} />
                  <Tooltip />
                  <Bar dataKey="offers" name="عدد الطلبات" fill="#0AA39B" radius={[0, 4, 4, 0]} />
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
            <div className="text-center py-16 text-gray-500">لا توجد بيانات للفترة المحددة</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">#</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">المنتج</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">الفئة</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">عدد الطلبات</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">إجمالي المبيعات</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">العروض</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {items.map((item: {
                  product_id: string;
                  product_name_ar?: string;
                  product_name: string;
                  category_name_ar?: string;
                  category_name?: string;
                  offer_count: number;
                  total_revenue: number;
                  listing_count: number;
                }, idx: number) => (
                  <tr key={item.product_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-400 font-medium">#{idx + 1}</td>
                    <td className="px-4 py-3 font-medium text-gray-900">
                      {item.product_name_ar ?? item.product_name}
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {item.category_name_ar ?? item.category_name ?? "—"}
                    </td>
                    <td className="px-4 py-3">
                      <span className="bg-brand-50 text-brand-700 text-xs font-semibold px-2 py-0.5 rounded-full">
                        {item.offer_count}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-green-600 font-semibold">
                      {formatCurrency(item.total_revenue)}
                    </td>
                    <td className="px-4 py-3 text-gray-600">{item.listing_count}</td>
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
