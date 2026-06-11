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
          subtitle="مؤشرات تشغيلية لمخزون المنشأة والعروض النشطة"
          actions={
            <Link href={`/${locale}/marketplace/create`}>
              <Button variant="gold">
                <ShoppingCart className="h-4 w-4" />
                نشر عرض جديد
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
            hint="عرض نشط"
          />
          <KpiCard
            icon={AlertTriangle}
            label={t("nearExpiryBatches")}
            value={nearExpiry?.length ?? "—"}
            tone="warning"
            hint="دفعة تتطلب إجراء"
          />
          <KpiCard
            icon={Bell}
            label={t("pendingOffers")}
            value={incomingOffers?.total ?? "—"}
            tone="gold"
            hint="طلب بانتظار الرد"
          />
          <KpiCard
            icon={TrendingUp}
            label={t("recoveredValue")}
            value={formatCurrency(totalRecovered)}
            tone="safe"
            hint="قيمة قابلة للاسترداد"
          />
        </div>

        {/* Near-Expiry + Donut */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          <SectionCard
            title={t("nearExpiryTable")}
            subtitle="دفعات تتطلب قراراً تشغيلياً خلال 90 يوماً"
            action={
              <Link
                href={`/${locale}/inventory/near-expiry`}
                className="inline-flex items-center gap-1 text-xs font-medium text-brand-700 hover:text-brand-800"
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
                title="لا توجد دفعات تتطلب إجراء"
                description="المخزون الحالي ضمن نطاق تشغيلي آمن"
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm tabular-nums min-w-[520px]">
                  <thead className="bg-[#f7efe3] border-b border-[#eadfcc]">
                    <tr>
                      <th className="px-5 py-3 text-right text-[11px] uppercase tracking-normal font-semibold text-[#7d6d58]">المنتج</th>
                      <th className="px-4 py-3 text-right text-[11px] uppercase tracking-normal font-semibold text-[#7d6d58] hidden sm:table-cell">الفرع</th>
                      <th className="px-4 py-3 text-right text-[11px] uppercase tracking-normal font-semibold text-[#7d6d58]">الحالة</th>
                      <th className="px-5 py-3 text-right text-[11px] uppercase tracking-normal font-semibold text-[#7d6d58]">الكمية</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#eadfcc]/80">
                    {urgentBatches.map((b: { id: string; product_name?: string; branch_name?: string; days_until_expiry?: number; quantity?: number }) => (
                      <tr key={b.id} className="hover:bg-[#fbf7f0]/70 transition-colors">
                        <td className="px-5 py-3 font-medium text-[#1f2a24]">
                          {b.product_name ?? "—"}
                        </td>
                        <td className="px-4 py-3 text-[#6d746d] hidden sm:table-cell">{b.branch_name ?? "—"}</td>
                        <td className="px-4 py-3">
                          <ExpiryBadge daysUntilExpiry={b.days_until_expiry ?? 999} />
                        </td>
                        <td className="px-5 py-3 text-[#4d554e]">{b.quantity}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </SectionCard>

          <SectionCard
            title={t("inventoryHealth")}
            subtitle="تصنيف الدفعات حسب مستوى الإجراء"
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
                        border: "1px solid #e2d4bf",
                        borderRadius: 10,
                        fontSize: 12,
                        boxShadow: "0 14px 30px -24px rgba(47,37,26,0.34)",
                      }}
                    />
                    <Legend
                      formatter={(v) => (
                        <span className="text-xs text-[#6d746d]">
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
            subtitle="آخر العروض المنشورة من منشأتك"
            action={
              <Link
                href={`/${locale}/my/listings`}
                className="inline-flex items-center gap-1 text-xs font-medium text-brand-700 hover:text-brand-800"
              >
                عرض الكل
                <ArrowLeft className="h-3.5 w-3.5" />
              </Link>
            }
          >
            {!listings?.items?.length ? (
              <EmptyState
                icon={ShoppingCart}
                title="لا توجد عروض نشطة"
                description="يمكنك نشر دفعة مؤهلة للتبادل عند الحاجة"
                action={
                  <Link href={`/${locale}/marketplace/create`}>
                    <Button variant="primary" size="sm">نشر عرض جديد</Button>
                  </Link>
                }
              />
            ) : (
              <ul className="space-y-1">
                {listings.items.map((l: { id: string; title: string; asking_price: number; quantity_available: number }) => (
                  <li
                    key={l.id}
                    className="flex items-center justify-between gap-3 py-2.5 border-b border-[#eadfcc] last:border-0"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-[#1f2a24] truncate">{l.title}</p>
                      <p className="text-xs text-[#6d746d] tabular-nums">
                        الكمية المتاحة: {l.quantity_available}
                      </p>
                    </div>
                    <span className="text-sm font-semibold text-[#1f2a24] tabular-nums whitespace-nowrap">
                      {formatCurrency(l.asking_price)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </SectionCard>

          <SectionCard
            title={t("incomingOffersWidget")}
            subtitle="طلبات شراء واردة من منشآت مرخصة"
            action={
              <Link
                href={`/${locale}/my/incoming-offers`}
                className="inline-flex items-center gap-1 text-xs font-medium text-brand-700 hover:text-brand-800"
              >
                عرض الكل
                <ArrowLeft className="h-3.5 w-3.5" />
              </Link>
            }
          >
            {!incomingOffers?.items?.length ? (
              <EmptyState
                icon={Bell}
                title="لا توجد طلبات واردة"
                description="ستظهر هنا طلبات الشراء عند ورودها على عروضك المنشورة"
              />
            ) : (
              <ul className="space-y-1">
                {incomingOffers.items.map((o: { id: string; offered_price: number; quantity: number; status: string }) => (
                  <li
                    key={o.id}
                    className="flex items-center justify-between gap-3 py-2.5 border-b border-[#eadfcc] last:border-0"
                  >
                    <span className="text-sm font-medium text-[#1f2a24] tabular-nums">
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
