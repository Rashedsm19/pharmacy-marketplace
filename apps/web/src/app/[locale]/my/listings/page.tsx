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
import { Plus, Eye, XCircle, Loader2, Search } from "lucide-react";

const STATUS_LABELS: Record<string, string> = {
  active: "نشط",
  sold: "مباع",
  cancelled: "ملغى",
  expired: "منتهي",
};

const STATUS_VARIANTS: Record<string, "success" | "default" | "danger" | "warning"> = {
  active: "success",
  sold: "default",
  cancelled: "danger",
  expired: "warning",
};

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
      listingsApi.listMine({ search, status: statusFilter || undefined, page, page_size: 15 }).then((r) => r.data),
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
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">إعلاناتي</h1>
          <Link
            href={`/${locale}/marketplace/create`}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
          >
            <Plus className="h-4 w-4" />
            إعلان جديد
          </Link>
        </div>

        {/* Filters */}
        <div className="flex gap-3 flex-wrap">
          <div className="relative flex-1 min-w-48">
            <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              placeholder="بحث في الإعلانات..."
              className="w-full pr-9 pl-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">جميع الحالات</option>
            <option value="active">نشط</option>
            <option value="sold">مباع</option>
            <option value="cancelled">ملغى</option>
            <option value="expired">منتهي</option>
          </select>
        </div>

        {/* Table */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          {isLoading ? (
            <div className="flex items-center justify-center h-48">
              <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
            </div>
          ) : listings.length === 0 ? (
            <div className="text-center py-16">
              <p className="text-gray-500 mb-4">لا توجد إعلانات حتى الآن</p>
              <Link
                href={`/${locale}/marketplace/create`}
                className="text-blue-600 hover:text-blue-700 text-sm font-medium"
              >
                إنشاء أول إعلان
              </Link>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">المنتج</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">السعر</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">الكمية</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">الانتهاء</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">الحالة</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">المشاهدات</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">الإجراءات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
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
                  <tr key={listing.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-900">
                      {listing.product_name_ar ?? listing.product_name}
                    </td>
                    <td className="px-4 py-3 text-blue-600 font-semibold">
                      {formatCurrency(listing.asking_price)}
                    </td>
                    <td className="px-4 py-3 text-gray-600">{listing.quantity_available}</td>
                    <td className="px-4 py-3">
                      {listing.days_until_expiry !== undefined ? (
                        <ExpiryBadge daysUntilExpiry={listing.days_until_expiry} />
                      ) : listing.expiry_date ? (
                        <span className="text-gray-500">{formatDate(listing.expiry_date, "ar-SA")}</span>
                      ) : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={STATUS_VARIANTS[listing.status] ?? "default"}>
                        {STATUS_LABELS[listing.status] ?? listing.status}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-gray-500">{listing.view_count ?? 0}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Link
                          href={`/${locale}/marketplace/${listing.id}`}
                          className="text-blue-600 hover:text-blue-700 p-1 rounded"
                          title="عرض"
                        >
                          <Eye className="h-4 w-4" />
                        </Link>
                        {listing.status === "active" && (
                          cancellingId === listing.id ? (
                            <div className="flex items-center gap-1 text-xs text-gray-500">
                              <span>تأكيد؟</span>
                              <button
                                onClick={() => cancelListing.mutate(listing.id)}
                                className="text-red-600 hover:text-red-700 font-medium"
                                disabled={cancelListing.isPending}
                              >
                                نعم
                              </button>
                              <button
                                onClick={() => setCancellingId(null)}
                                className="text-gray-500 hover:text-gray-700"
                              >
                                لا
                              </button>
                            </div>
                          ) : (
                            <button
                              onClick={() => setCancellingId(listing.id)}
                              className="text-red-500 hover:text-red-600 p-1 rounded"
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
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm disabled:opacity-50"
            >
              السابق
            </button>
            <span className="text-sm text-gray-600">
              صفحة {page} من {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm disabled:opacity-50"
            >
              التالي
            </button>
          </div>
        )}
      </div>
    </Shell>
  );
}
