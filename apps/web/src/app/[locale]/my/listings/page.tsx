"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocale } from "next-intl";
import Link from "next/link";
import { toast } from "sonner";
import Shell from "@/components/layout/shell";
import { ExpiryBadge } from "@/components/ui/expiry-badge";
import { Badge } from "@/components/ui/badge";
import { listingsApi } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import { Plus, Eye, XCircle, Search, ChevronRight, ChevronLeft, Package } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";

const STATUS_LABELS: Record<string, string> = {
  active: "نشط",
  sold: "مباع",
  cancelled: "ملغى",
  expired: "منتهي",
  reserved: "محجوز",
};

const STATUS_VARIANTS: Record<string, "success" | "default" | "danger" | "warning" | "brand"> = {
  active: "success",
  sold: "default",
  reserved: "brand",
  cancelled: "danger",
  expired: "warning",
};

const inputCls =
  "w-full h-10 pr-10 pl-3 bg-slate-50/60 ring-1 ring-inset ring-slate-200 rounded-lg text-sm placeholder:text-slate-400 focus:outline-none focus:bg-white focus:ring-2 focus:ring-brand-500";

export default function MyListingsPage() {
  const locale = useLocale();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [cancellingId, setCancellingId] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["my-listings", search, statusFilter, page],
    queryFn: () =>
      listingsApi
        .listMine({ search, status: statusFilter || undefined, page, page_size: 15 })
        .then((r) => r.data),
  });

  const cancelListing = useMutation({
    mutationFn: (id: string) => listingsApi.cancel(id),
    onSuccess: () => {
      toast.success("تم إلغاء الإعلان");
      qc.invalidateQueries({ queryKey: ["my-listings"] });
      setCancellingId(null);
    },
    onError: () => toast.error("فشل إلغاء الإعلان"),
  });

  const listings = data?.items ?? [];
  const totalPages = Math.ceil((data?.total ?? 0) / 15);

  return (
    <Shell>
      <div className="space-y-6">
        <PageHeader
          title="إعلاناتي"
          subtitle="إدارة الإعلانات المنشورة على السوق"
          actions={
            <Link href={`/${locale}/marketplace/create`}>
              <Button variant="gold">
                <Plus className="h-4 w-4" />
                إعلان جديد
              </Button>
            </Link>
          }
        />

        {/* Filters */}
        <Card className="p-4">
          <div className="flex flex-col md:flex-row md:items-center gap-3">
            <div className="relative w-full md:flex-1">
              <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input
                value={search}
                onChange={(e) => { setSearch(e.target.value); setPage(1); }}
                placeholder="بحث في الإعلانات..."
                className={inputCls}
              />
            </div>
            <select
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
              className="w-full md:w-auto h-10 px-3 bg-slate-50/60 ring-1 ring-inset ring-slate-200 rounded-lg text-sm focus:outline-none focus:bg-white focus:ring-2 focus:ring-brand-500"
            >
              <option value="">جميع الحالات</option>
              <option value="active">نشط</option>
              <option value="reserved">محجوز</option>
              <option value="sold">مباع</option>
              <option value="cancelled">ملغى</option>
              <option value="expired">منتهي</option>
            </select>
          </div>
        </Card>

        {/* Table */}
        <div className="bg-white ring-1 ring-slate-200/70 shadow-soft rounded-2xl overflow-hidden">
          {isLoading ? (
            <div className="p-5 space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="h-12 bg-slate-50 rounded-lg animate-pulse" />
              ))}
            </div>
          ) : listings.length === 0 ? (
            <EmptyState
              icon={Package}
              title="لا توجد إعلانات حتى الآن"
              description="ابدأ بنشر دفعتك الأولى على السوق الآن"
              action={
                <Link href={`/${locale}/marketplace/create`}>
                  <Button variant="primary" size="sm">إنشاء أول إعلان</Button>
                </Link>
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm tabular-nums min-w-[760px]">
                <thead className="bg-slate-50/60 border-b border-slate-100">
                  <tr>
                    <th className="text-right px-4 py-3 text-[11px] uppercase tracking-wider font-semibold text-slate-500">المنتج</th>
                    <th className="text-right px-4 py-3 text-[11px] uppercase tracking-wider font-semibold text-slate-500">السعر</th>
                    <th className="text-right px-4 py-3 text-[11px] uppercase tracking-wider font-semibold text-slate-500">الكمية</th>
                    <th className="text-right px-4 py-3 text-[11px] uppercase tracking-wider font-semibold text-slate-500">الانتهاء</th>
                    <th className="text-right px-4 py-3 text-[11px] uppercase tracking-wider font-semibold text-slate-500">الحالة</th>
                    <th className="text-right px-4 py-3 text-[11px] uppercase tracking-wider font-semibold text-slate-500 hidden md:table-cell">المشاهدات</th>
                    <th className="text-right px-4 py-3 text-[11px] uppercase tracking-wider font-semibold text-slate-500">إجراءات</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100/80">
                  {listings.map((listing: {
                    id: string;
                    product_name_ar?: string;
                    product_name: string;
                    asking_price: number;
                    quantity_available: number;
                    expiry_date?: string;
                    days_until_expiry?: number;
                    status: string;
                    view_count?: number;
                  }) => (
                    <tr key={listing.id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="px-4 py-3 font-medium text-slate-900">
                        {listing.product_name_ar ?? listing.product_name}
                      </td>
                      <td className="px-4 py-3 text-brand-700 font-semibold">
                        {formatCurrency(listing.asking_price)}
                      </td>
                      <td className="px-4 py-3 text-slate-700">{listing.quantity_available}</td>
                      <td className="px-4 py-3">
                        {listing.days_until_expiry !== undefined ? (
                          <ExpiryBadge daysUntilExpiry={listing.days_until_expiry} />
                        ) : listing.expiry_date ? (
                          <span className="text-slate-500">{formatDate(listing.expiry_date, "ar-SA")}</span>
                        ) : "—"}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={STATUS_VARIANTS[listing.status] ?? "default"}>
                          {STATUS_LABELS[listing.status] ?? listing.status}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-slate-500 hidden md:table-cell">{listing.view_count ?? 0}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1">
                          <Link
                            href={`/${locale}/marketplace/${listing.id}`}
                            className="h-8 w-8 inline-flex items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-700"
                            title="عرض"
                          >
                            <Eye className="h-4 w-4" />
                          </Link>
                          {listing.status === "active" && (
                            cancellingId === listing.id ? (
                              <div className="flex items-center gap-1 text-xs text-slate-500 mr-1">
                                <span>تأكيد؟</span>
                                <button
                                  onClick={() => cancelListing.mutate(listing.id)}
                                  className="text-rose-600 hover:text-rose-700 font-semibold"
                                  disabled={cancelListing.isPending}
                                >
                                  نعم
                                </button>
                                <button
                                  onClick={() => setCancellingId(null)}
                                  className="text-slate-500 hover:text-slate-700"
                                >
                                  لا
                                </button>
                              </div>
                            ) : (
                              <button
                                onClick={() => setCancellingId(listing.id)}
                                className="h-8 w-8 inline-flex items-center justify-center rounded-lg text-rose-500 hover:bg-rose-50 hover:text-rose-600"
                                title="إلغاء"
                              >
                                <XCircle className="h-4 w-4" />
                              </button>
                            )
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-1.5">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              aria-label="السابق"
              className="h-9 w-9 inline-flex items-center justify-center rounded-lg ring-1 ring-slate-200 text-slate-500 hover:bg-slate-50 disabled:opacity-40"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
            <span className="text-sm text-slate-600 px-3 tabular-nums">
              صفحة {page} من {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              aria-label="التالي"
              className="h-9 w-9 inline-flex items-center justify-center rounded-lg ring-1 ring-slate-200 text-slate-500 hover:bg-slate-50 disabled:opacity-40"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>
    </Shell>
  );
}
