"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocale } from "next-intl";
import Link from "next/link";
import { toast } from "sonner";
import Shell from "@/components/layout/shell";
import { Badge } from "@/components/ui/badge";
import { offersApi } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import { Eye, XCircle, Loader2 } from "lucide-react";

const STATUS_LABELS: Record<string, string> = {
  pending: "قيد الانتظار",
  accepted: "مقبول",
  rejected: "مرفوض",
  cancelled: "ملغى",
  expired: "منتهي",
};

const STATUS_VARIANTS: Record<string, "success" | "default" | "danger" | "warning" | "info"> = {
  pending: "info",
  accepted: "success",
  rejected: "danger",
  cancelled: "default",
  expired: "warning",
};

export default function MyOffersPage() {
  const locale = useLocale();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [cancellingId, setCancellingId] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["my-offers", page],
    queryFn: () => offersApi.listMine({ page, page_size: 15 }).then((r) => r.data),
  });

  const cancelOffer = useMutation({
    mutationFn: (id: string) => offersApi.cancel(id),
    onSuccess: () => {
      toast.success("تم إلغاء العرض");
      qc.invalidateQueries({ queryKey: ["my-offers"] });
      setCancellingId(null);
    },
    onError: () => toast.error("فشل إلغاء العرض"),
  });

  const offers = data?.items ?? [];
  const totalPages = Math.ceil((data?.total ?? 0) / 15);

  return (
    <Shell>
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">عروضي المقدمة</h1>

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          {isLoading ? (
            <div className="flex items-center justify-center h-48">
              <Loader2 className="h-6 w-6 animate-spin text-brand-600" />
            </div>
          ) : offers.length === 0 ? (
            <div className="text-center py-16">
              <p className="text-gray-500 mb-4">لم تقدم أي عروض بعد</p>
              <Link
                href={`/${locale}/marketplace`}
                className="text-brand-600 hover:text-brand-700 text-sm font-medium"
              >
                تصفح السوق
              </Link>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">المنتج</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">سعر العرض</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">الكمية</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">تاريخ التقديم</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">الحالة</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">الإجراءات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {offers.map((offer: {
                  id: string;
                  listing_id: string;
                  listing_product_name_ar?: string;
                  listing_product_name?: string;
                  offered_price: number;
                  quantity: number;
                  created_at: string;
                  status: string;
                  message?: string;
                }) => (
                  <tr key={offer.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <div>
                        <p className="font-medium text-gray-900">
                          {offer.listing_product_name_ar ?? offer.listing_product_name ?? "—"}
                        </p>
                        {offer.message && (
                          <p className="text-xs text-gray-400 mt-0.5 truncate max-w-40">{offer.message}</p>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-brand-600 font-semibold">
                      {formatCurrency(offer.offered_price)}
                    </td>
                    <td className="px-4 py-3 text-gray-600">{offer.quantity}</td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {formatDate(offer.created_at, "ar-SA")}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={STATUS_VARIANTS[offer.status] ?? "default"}>
                        {STATUS_LABELS[offer.status] ?? offer.status}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Link
                          href={`/${locale}/marketplace/${offer.listing_id}`}
                          className="text-brand-600 hover:text-brand-700 p-1 rounded"
                          title="عرض العرض"
                        >
                          <Eye className="h-4 w-4" />
                        </Link>
                        {offer.status === "pending" && (
                          cancellingId === offer.id ? (
                            <div className="flex items-center gap-1 text-xs text-gray-500">
                              <span>تأكيد؟</span>
                              <button
                                onClick={() => cancelOffer.mutate(offer.id)}
                                className="text-red-600 hover:text-red-700 font-medium"
                                disabled={cancelOffer.isPending}
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
                              onClick={() => setCancellingId(offer.id)}
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

        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm disabled:opacity-50"
            >
              السابق
            </button>
            <span className="text-sm text-gray-600">صفحة {page} من {totalPages}</span>
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
