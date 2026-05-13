"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocale } from "next-intl";
import Link from "next/link";
import { toast } from "sonner";
import Shell from "@/components/layout/shell";
import { Badge } from "@/components/ui/badge";
import { ExpiryBadge } from "@/components/ui/expiry-badge";
import { adminApi } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import { Loader2, Eye, XCircle, ShieldAlert } from "lucide-react";

export default function AdminModerationPage() {
  const locale = useLocale();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("active");
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [removeReason, setRemoveReason] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["admin-moderation", page, statusFilter],
    queryFn: () =>
      adminApi.getModeration({ page, page_size: 15, status: statusFilter }).then((r) => r.data),
  });

  const removeListing = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      adminApi.removeListing(id, reason),
    onSuccess: () => {
      toast.success("تم إزالة الإعلان");
      qc.invalidateQueries({ queryKey: ["admin-moderation"] });
      setRemovingId(null);
      setRemoveReason("");
    },
    onError: () => toast.error("فشل إزالة الإعلان"),
  });

  const listings = data?.items ?? [];
  const totalPages = Math.ceil((data?.total ?? 0) / 15);

  return (
    <Shell>
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <ShieldAlert className="h-6 w-6 text-purple-600" />
          <h1 className="text-2xl font-bold text-gray-900">إدارة الإعلانات</h1>
        </div>

        {/* Filter */}
        <div className="flex gap-3">
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="active">نشط</option>
            <option value="cancelled">ملغى</option>
            <option value="sold">مباع</option>
            <option value="">الكل</option>
          </select>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          {isLoading ? (
            <div className="flex items-center justify-center h-48">
              <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
            </div>
          ) : listings.length === 0 ? (
            <div className="text-center py-16 text-gray-500">لا توجد إعلانات</div>
          ) : (
            <div className="divide-y divide-gray-100">
              {listings.map((listing: {
                id: string;
                title?: string;
                product_name_ar?: string;
                product_name: string;
                seller_org_name?: string;
                asking_price: number;
                quantity_available: number;
                days_until_expiry?: number;
                status: string;
                view_count?: number;
                offer_count?: number;
                created_at: string;
              }) => (
                <div key={listing.id} className="p-5">
                  {removingId === listing.id ? (
                    <div className="space-y-3">
                      <p className="font-medium text-gray-900">سبب الإزالة</p>
                      <textarea
                        value={removeReason}
                        onChange={(e) => setRemoveReason(e.target.value)}
                        rows={2}
                        placeholder="اذكر سبب الإزالة..."
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none"
                      />
                      <div className="flex gap-2">
                        <button
                          onClick={() => { setRemovingId(null); setRemoveReason(""); }}
                          className="px-4 py-2 border border-gray-300 text-gray-600 rounded-lg text-sm"
                        >
                          إلغاء
                        </button>
                        <button
                          onClick={() => removeListing.mutate({ id: listing.id, reason: removeReason })}
                          disabled={!removeReason.trim() || removeListing.isPending}
                          className="flex items-center gap-1.5 px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium disabled:opacity-60"
                        >
                          {removeListing.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                          إزالة الإعلان
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-start gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <h3 className="font-semibold text-gray-900">
                            {listing.product_name_ar ?? listing.product_name}
                          </h3>
                          <Badge variant={listing.status === "active" ? "success" : "default"}>
                            {listing.status === "active" ? "نشط" : listing.status}
                          </Badge>
                          {listing.days_until_expiry !== undefined && (
                            <ExpiryBadge daysUntilExpiry={listing.days_until_expiry} />
                          )}
                        </div>
                        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs text-gray-500 mt-2">
                          <span>البائع: {listing.seller_org_name ?? "—"}</span>
                          <span>السعر: {formatCurrency(listing.asking_price)}</span>
                          <span>الكمية: {listing.quantity_available}</span>
                          <span>المشاهدات: {listing.view_count ?? 0}</span>
                          <span>العروض: {listing.offer_count ?? 0}</span>
                        </div>
                        <p className="text-xs text-gray-400 mt-1">{formatDate(listing.created_at, "ar-SA")}</p>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <Link
                          href={`/${locale}/marketplace/${listing.id}`}
                          className="text-blue-600 hover:text-blue-700 p-1.5 rounded hover:bg-blue-50"
                          title="عرض"
                        >
                          <Eye className="h-4 w-4" />
                        </Link>
                        {listing.status === "active" && (
                          <button
                            onClick={() => setRemovingId(listing.id)}
                            className="text-red-500 hover:text-red-600 p-1.5 rounded hover:bg-red-50"
                            title="إزالة"
                          >
                            <XCircle className="h-4 w-4" />
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2">
            <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm disabled:opacity-50">السابق</button>
            <span className="text-sm text-gray-600">صفحة {page} من {totalPages}</span>
            <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages} className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm disabled:opacity-50">التالي</button>
          </div>
        )}
      </div>
    </Shell>
  );
}
