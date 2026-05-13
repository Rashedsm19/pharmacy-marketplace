"use client";

import { useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import Shell from "@/components/layout/shell";
import { inventoryApi, listingsApi, offersApi, reportsApi } from "@/lib/api";
import { formatCurrency, expiryZoneColors, getExpiryZone } from "@/lib/utils";
import { Package, ShoppingCart, Bell, TrendingUp, AlertTriangle } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import Link from "next/link";

export default function DashboardPage() {
  const locale = useLocale();
  const t = useTranslations("dashboard");

  const { data: nearExpiry } = useQuery({
    queryKey: ["near-expiry-batches"],
    queryFn: () => inventoryApi.listNearExpiry(180).then((r) => r.data),
  });

  const { data: listings } = useQuery({
    queryKey: ["my-listings"],
    queryFn: () => listingsApi.list({ my_listings: true, page_size: 5 }).then((r) => r.data),
  });

  const { data: incomingOffers } = useQuery({
    queryKey: ["incoming-offers"],
    queryFn: () => offersApi.incoming({ page_size: 5 }).then((r) => r.data),
  });

  const { data: recoverableData } = useQuery({
    queryKey: ["recoverable-value"],
    queryFn: () => reportsApi.recoverableValue().then((r) => r.data),
  });

  const urgentBatches = (nearExpiry || [])
    .filter((b: { days_until_expiry?: number }) => (b.days_until_expiry ?? 999) <= 90)
    .slice(0, 10);

  const totalRecovered = (recoverableData || []).reduce(
    (sum: number, r: { estimated_value?: number }) => sum + (r.estimated_value ?? 0),
    0
  );

  const kpis = [
    {
      label: t("activeListings"),
      value: listings?.total ?? "—",
      icon: ShoppingCart,
      color: "text-blue-600 bg-blue-50",
    },
    {
      label: t("nearExpiryBatches"),
      value: nearExpiry?.length ?? "—",
      icon: AlertTriangle,
      color: "text-amber-600 bg-amber-50",
    },
    {
      label: t("pendingOffers"),
      value: incomingOffers?.total ?? "—",
      icon: Bell,
      color: "text-purple-600 bg-purple-50",
    },
    {
      label: t("recoveredValue"),
      value: formatCurrency(totalRecovered),
      icon: TrendingUp,
      color: "text-green-600 bg-green-50",
    },
  ];

  // Chart data
  const pieData = (recoverableData || []).map(
    (r: { expiry_zone: string; batch_count: number }) => ({
      name: r.expiry_zone,
      value: r.batch_count,
    })
  );

  const pieColors = {
    green: "#16a34a",
    yellow: "#ca8a04",
    orange: "#ea580c",
    red: "#dc2626",
  };

  return (
    <Shell>
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">{t("title")}</h1>

        {/* KPI Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          {kpis.map((kpi) => (
            <div
              key={kpi.label}
              className="bg-white rounded-xl p-5 shadow-sm border border-gray-100 flex items-center gap-4"
            >
              <div className={`p-3 rounded-xl ${kpi.color}`}>
                <kpi.icon className="h-6 w-6" />
              </div>
              <div>
                <p className="text-2xl font-bold text-gray-900">{kpi.value}</p>
                <p className="text-sm text-gray-500">{kpi.label}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          {/* Near-Expiry Table */}
          <div className="xl:col-span-2 bg-white rounded-xl shadow-sm border border-gray-100">
            <div className="p-5 border-b border-gray-100 flex items-center justify-between">
              <h2 className="font-semibold text-gray-900">{t("nearExpiryTable")}</h2>
              <Link
                href={`/${locale}/inventory/near-expiry`}
                className="text-sm text-blue-600 hover:underline"
              >
                عرض الكل
              </Link>
            </div>
            <div className="overflow-x-auto">
              {urgentBatches.length === 0 ? (
                <div className="p-8 text-center text-gray-400">
                  <Package className="h-12 w-12 mx-auto mb-2 opacity-30" />
                  <p>لا توجد دفعات قرب الانتهاء</p>
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-right font-medium text-gray-600">المنتج</th>
                      <th className="px-4 py-3 text-right font-medium text-gray-600">الفرع</th>
                      <th className="px-4 py-3 text-right font-medium text-gray-600">الأيام المتبقية</th>
                      <th className="px-4 py-3 text-right font-medium text-gray-600">الكمية</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {urgentBatches.map((b: { id: string; product_name?: string; branch_name?: string; days_until_expiry?: number; quantity?: number }) => {
                      const zone = getExpiryZone(b.days_until_expiry ?? 999);
                      return (
                        <tr key={b.id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 font-medium text-gray-900">
                            {b.product_name ?? "—"}
                          </td>
                          <td className="px-4 py-3 text-gray-600">{b.branch_name ?? "—"}</td>
                          <td className="px-4 py-3">
                            <span
                              className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium border ${expiryZoneColors[zone]}`}
                            >
                              {b.days_until_expiry ?? "—"} يوم
                            </span>
                          </td>
                          <td className="px-4 py-3 text-gray-600">{b.quantity}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          {/* Inventory Health Donut */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <h2 className="font-semibold text-gray-900 mb-4">{t("inventoryHealth")}</h2>
            {pieData.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80}>
                    {pieData.map((entry: { name: string }, i: number) => (
                      <Cell
                        key={i}
                        fill={pieColors[entry.name as keyof typeof pieColors] ?? "#94a3b8"}
                      />
                    ))}
                  </Pie>
                  <Legend />
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-40 flex items-center justify-center text-gray-400 text-sm">
                لا توجد بيانات
              </div>
            )}
          </div>
        </div>

        {/* Active Listings + Incoming Offers */}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          {/* Active Listings */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100">
            <div className="p-5 border-b border-gray-100 flex items-center justify-between">
              <h2 className="font-semibold text-gray-900">{t("activeListingsSummary")}</h2>
              <Link href={`/${locale}/my/listings`} className="text-sm text-blue-600 hover:underline">
                عرض الكل
              </Link>
            </div>
            <div className="p-4">
              {!listings?.items?.length ? (
                <div className="py-6 text-center text-gray-400 text-sm">
                  <ShoppingCart className="h-10 w-10 mx-auto mb-2 opacity-30" />
                  <p>لا توجد إعلانات نشطة</p>
                  <Link
                    href={`/${locale}/marketplace/create`}
                    className="text-blue-600 text-xs hover:underline mt-1 inline-block"
                  >
                    إنشاء إعلان جديد
                  </Link>
                </div>
              ) : (
                <ul className="space-y-2">
                  {listings.items.map((l: { id: string; title: string; asking_price: number; quantity_available: number }) => (
                    <li
                      key={l.id}
                      className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0"
                    >
                      <div>
                        <p className="text-sm font-medium text-gray-900 truncate max-w-48">{l.title}</p>
                        <p className="text-xs text-gray-500">الكمية: {l.quantity_available}</p>
                      </div>
                      <span className="text-sm font-semibold text-gray-800">
                        {formatCurrency(l.asking_price)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* Incoming Offers */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100">
            <div className="p-5 border-b border-gray-100 flex items-center justify-between">
              <h2 className="font-semibold text-gray-900">{t("incomingOffersWidget")}</h2>
              <Link
                href={`/${locale}/my/incoming-offers`}
                className="text-sm text-blue-600 hover:underline"
              >
                عرض الكل
              </Link>
            </div>
            <div className="p-4">
              {!incomingOffers?.items?.length ? (
                <div className="py-6 text-center text-gray-400 text-sm">
                  <Bell className="h-10 w-10 mx-auto mb-2 opacity-30" />
                  <p>لا توجد عروض واردة</p>
                </div>
              ) : (
                <ul className="space-y-2">
                  {incomingOffers.items.map((o: { id: string; offered_price: number; quantity: number; status: string }) => (
                    <li
                      key={o.id}
                      className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0"
                    >
                      <span className="text-sm font-medium text-gray-900">
                        {formatCurrency(o.offered_price)} × {o.quantity}
                      </span>
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                          o.status === "pending"
                            ? "bg-amber-100 text-amber-700"
                            : o.status === "accepted"
                            ? "bg-green-100 text-green-700"
                            : "bg-gray-100 text-gray-600"
                        }`}
                      >
                        {o.status}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      </div>
    </Shell>
  );
}
