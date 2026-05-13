"use client";

import { useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import Shell from "@/components/layout/shell";
import { inventoryApi, listingsApi, offersApi, reportsApi } from "@/lib/api";
import { formatCurrency, getExpiryZone } from "@/lib/utils";
import { Package, ShoppingCart, Bell, TrendingUp, AlertTriangle, ArrowLeft } from "lucide-react";
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
  Tooltip,
} from "recharts";
import Link from "next/link";
import { KpiCard } from "@/components/ui/kpi-card";
import { SectionCard } from "@/components/ui/section-card";
import { ExpiryBadge } from "@/components/ui/expiry-badge";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";

const statusBadgeMap: Record<string, "warning" | "success" | "default" | "danger"> = {
  pending: "warning",
  accepted: "success",
  rejected: "danger",
  cancelled: "default",
  expired: "default",
};

const statusLabelMap: Record<string, string> = {
  pending: "بانتظار الرد",
  accepted: "مقبول",
  rejected: "مرفوض",
  cancelled: "ملغي",
  expired: "منتهي",
};

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
    .slice(0, 8);

  const totalRecovered = (recoverableData || []).reduce(
    (sum: number, r: { estimated_value?: number }) => sum + (r.estimated_value ?? 0),
    0
  );

  const pieData = (recoverableData || []).map(
    (r: { expiry_zone: string; batch_count: number }) => ({
      name: r.expiry_zone,
      value: r.batch_count,
    })
  );

  const pieColors: Record<string, string> = {
    green: "#10b981",
    yellow: "#eab308",
    orange: "#f97316",
    red: "#f43f5e",
  };
  const zoneLabels: Record<string, string> = {
    green: "صالح",
    yellow: "تنبيه",
    orange: "تحذير",
    red: "حرج",
  };

  return (
    <Shell>
      <div className="space-y-6">
        <PageHeader
          title={t("title")}
          subtitle="نظرة عامة على المخزون والصفقات النشطة"
          actions={
            <Link href={`/${locale}/marketplace/create`}>
              <Button variant="gold">
                <ShoppingCart className="h-4 w-4" />
                إنشاء إعلان جديد
              </Button>
            </Link>
          }
        />

        {/* KPI Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <KpiCard
            icon={ShoppingCart}
            label={t("activeListings")}
            value={listings?.total ?? "—"}
            tone="brand"
            hint="إعلان نشط"
          />
          <KpiCard
            icon={AlertTriangle}
            label={t("nearExpiryBatches")}
            value={nearExpiry?.length ?? "—"}
            tone="warning"
            hint="دفعة قاربة الانتهاء"
          />
          <KpiCard
            icon={Bell}
            label={t("pendingOffers")}
            value={incomingOffers?.total ?? "—"}
            tone="gold"
            hint="عرض بانتظار الرد"
          />
          <KpiCard
            icon={TrendingUp}
            label={t("recoveredValue")}
            value={formatCurrency(totalRecovered)}
            tone="safe"
            hint="قيمة قابلة للاسترجاع"
          />
        </div>

        {/* Near-Expiry + Donut */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          <SectionCard
            title={t("nearExpiryTable")}
            subtitle="الدفعات الأكثر إلحاحاً (≤ 90 يوم)"
            action={
              <Link
                href={`/${locale}/inventory/near-expiry`}
                className="inline-flex items-center gap-1 text-xs font-medium text-brand-600 hover:text-brand-700"
              >
                عرض الكل
                <ArrowLeft className="h-3.5 w-3.5" />
              </Link>
            }
            className="lg:col-span-2"
            noPadding
          >
            {urgentBatches.length === 0 ? (
              <EmptyState
                icon={Package}
                title="لا توجد دفعات قرب الانتهاء"
                description="كل المخزون في المنطقة الآمنة"
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm tabular-nums min-w-[520px]">
                  <thead className="bg-slate-50/60 border-b border-slate-100">
                    <tr>
                      <th className="px-5 py-3 text-right text-[11px] uppercase tracking-wider font-semibold text-slate-500">المنتج</th>
                      <th className="px-4 py-3 text-right text-[11px] uppercase tracking-wider font-semibold text-slate-500 hidden sm:table-cell">الفرع</th>
                      <th className="px-4 py-3 text-right text-[11px] uppercase tracking-wider font-semibold text-slate-500">الحالة</th>
                      <th className="px-5 py-3 text-right text-[11px] uppercase tracking-wider font-semibold text-slate-500">الكمية</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100/80">
                    {urgentBatches.map((b: { id: string; product_name?: string; branch_name?: string; days_until_expiry?: number; quantity?: number }) => (
                      <tr key={b.id} className="hover:bg-slate-50/60 transition-colors">
                        <td className="px-5 py-3 font-medium text-slate-900">
                          {b.product_name ?? "—"}
                        </td>
                        <td className="px-4 py-3 text-slate-600 hidden sm:table-cell">{b.branch_name ?? "—"}</td>
                        <td className="px-4 py-3">
                          <ExpiryBadge daysUntilExpiry={b.days_until_expiry ?? 999} />
                        </td>
                        <td className="px-5 py-3 text-slate-700">{b.quantity}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </SectionCard>

          <SectionCard
            title={t("inventoryHealth")}
            subtitle="توزيع الدفعات حسب المنطقة"
          >
            {pieData.length > 0 ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={84}
                      innerRadius={44}
                      paddingAngle={2}
                      stroke="#ffffff"
                      strokeWidth={2}
                    >
                      {pieData.map((entry: { name: string }, i: number) => (
                        <Cell
                          key={i}
                          fill={pieColors[entry.name as keyof typeof pieColors] ?? "#94a3b8"}
                        />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(value: number, _name, props: { payload?: { name?: string } }) => {
                        const key = props?.payload?.name as string;
                        return [`${value} دفعة`, zoneLabels[key] ?? key];
                      }}
                      contentStyle={{
                        background: "white",
                        border: "1px solid #e2e8f0",
                        borderRadius: 10,
                        fontSize: 12,
                        boxShadow: "0 4px 12px -2px rgba(15,23,42,0.08)",
                      }}
                    />
                    <Legend
                      formatter={(v) => (
                        <span className="text-xs text-slate-600">
                          {zoneLabels[v as string] ?? v}
                        </span>
                      )}
                      iconType="circle"
                      iconSize={8}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <EmptyState title="لا توجد بيانات" />
            )}
          </SectionCard>
        </div>

        {/* Active Listings + Incoming Offers */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <SectionCard
            title={t("activeListingsSummary")}
            subtitle="آخر إعلاناتك المنشورة"
            action={
              <Link
                href={`/${locale}/my/listings`}
                className="inline-flex items-center gap-1 text-xs font-medium text-brand-600 hover:text-brand-700"
              >
                عرض الكل
                <ArrowLeft className="h-3.5 w-3.5" />
              </Link>
            }
          >
            {!listings?.items?.length ? (
              <EmptyState
                icon={ShoppingCart}
                title="لا توجد إعلانات نشطة"
                description="ابدأ بنشر دفعتك الأولى الآن"
                action={
                  <Link href={`/${locale}/marketplace/create`}>
                    <Button variant="primary" size="sm">إنشاء إعلان جديد</Button>
                  </Link>
                }
              />
            ) : (
              <ul className="space-y-1">
                {listings.items.map((l: { id: string; title: string; asking_price: number; quantity_available: number }) => (
                  <li
                    key={l.id}
                    className="flex items-center justify-between gap-3 py-2.5 border-b border-slate-100 last:border-0"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-slate-900 truncate">{l.title}</p>
                      <p className="text-xs text-slate-500 tabular-nums">
                        الكمية المتاحة: {l.quantity_available}
                      </p>
                    </div>
                    <span className="text-sm font-semibold text-slate-900 tabular-nums whitespace-nowrap">
                      {formatCurrency(l.asking_price)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </SectionCard>

          <SectionCard
            title={t("incomingOffersWidget")}
            subtitle="عروض شراء واردة من صيدليات أخرى"
            action={
              <Link
                href={`/${locale}/my/incoming-offers`}
                className="inline-flex items-center gap-1 text-xs font-medium text-brand-600 hover:text-brand-700"
              >
                عرض الكل
                <ArrowLeft className="h-3.5 w-3.5" />
              </Link>
            }
          >
            {!incomingOffers?.items?.length ? (
              <EmptyState
                icon={Bell}
                title="لا توجد عروض واردة"
                description="ستظهر هنا فور وصول عرض على أحد إعلاناتك"
              />
            ) : (
              <ul className="space-y-1">
                {incomingOffers.items.map((o: { id: string; offered_price: number; quantity: number; status: string }) => (
                  <li
                    key={o.id}
                    className="flex items-center justify-between gap-3 py-2.5 border-b border-slate-100 last:border-0"
                  >
                    <span className="text-sm font-medium text-slate-900 tabular-nums">
                      {formatCurrency(o.offered_price)} × {o.quantity}
                    </span>
                    <Badge variant={statusBadgeMap[o.status] ?? "default"} size="sm">
                      {statusLabelMap[o.status] ?? o.status}
                    </Badge>
                  </li>
                ))}
              </ul>
            )}
          </SectionCard>
        </div>
      </div>
    </Shell>
  );
}

// Suppress unused warning for zone helper if not used
void getExpiryZone;
