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
import { CheckCircle, XCircle, Eye, Loader2, MessageSquare } from "lucide-react";

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

export default function IncomingOffersPage() {
  const locale = useLocale();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [processingId, setProcessingId] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["incoming-offers", page],
    queryFn: () => offersApi.listIncoming({ page, page_size: 15 }).then((r) => r.data),
  });

  const acceptOffer = useMutation({
    mutationFn: (id: string) => offersApi.accept(id),
    onSuccess: () => {
      toast.success("تم قبول العرض وإنشاء الحجز");
      qc.invalidateQueries({ queryKey: ["incoming-offers"] });
      setProcessingId(null);
    },
    onError: () => toast.error("فشل قبول العرض"),
  });

  const rejectOffer = useMutation({
    mutationFn: (id: string) => offersApi.reject(id),
    onSuccess: () => {
      toast.success("تم رفض العرض");
      qc.invalidateQueries({ queryKey: ["incoming-offers"] });
      setProcessingId(null);
    },
    onError: () => toast.error("فشل رفض العرض"),
  });

  const offers = data?.items ?? [];
  const totalPages = Math.ceil((data?.total ?? 0) / 15);
  const pendingCount = offers.filter((o: { status: string }) => o.status === "pending").length;

  return (
    <Shell>
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-gray-900">العروض الواردة</h1>
          {pendingCount > 0 && (
            <span className="bg-blue-100 text-blue-700 text-xs font-semibold px-2.5 py-1 rounded-full">
              {pendingCount} جديد
            </span>
          )}
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          {isLoading ? (
            <div className="flex items-center justify-center h-48">
              <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
            </div>
          ) : offers.length === 0 ? (
            <div className="text-center py-16">
              <p className="text-gray-500">لا توجد عروض واردة</p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">الإعلان</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">المشتري</th>
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
                  listing_title?: string;
                  listing_product_name_ar?: string;
                  listing_product_name?: string;
                  buyer_org_name?: string;
                  offered_price: number;
                  quantity: number;
                  created_at: string;
                  status: string;
                  message?: string;
                }) => (
                  <tr key={offer.id} className={`hover:bg-gray-50 ${offer.status === "pending" ? "bg-blue-50/30" : ""}`}>
                    <td className="px-4 py-3">
                      <div>
                        <p className="font-medium text-gray-900">
                          {offer.listing_product_name_ar ?? offer.listing_product_name ?? "—"}
                        </p>
                        {offer.message && (
                          <div className="flex items-center gap-1 mt-0.5">
                            <MessageSquare className="h-3 w-3 text-gray-400" />
                            <p className="text-xs text-gray-400 truncate max-w-36">{offer.message}</p>
                          </div>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-600">{offer.buyer_org_name ?? "—"}</td>
                    <td className="px-4 py-3 text-blue-600 font-semibold">
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
                      <div className="flex items-center gap-1.5">
                        <Link
                          href={`/${locale}/marketplace/${offer.listing_id}`}
                          className="text-blue-600 hover:text-blue-700 p-1 rounded"
                          title="عرض الإعلان"
                        >
                          <Eye className="h-4 w-4" />
                        </Link>
                        {offer.status === "pending" && (
                          <>
                            {processingId === offer.id ? (
                              <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
                            ) : (
                              <>
                                <button
                                  onClick={() => {
                                    setProcessingId(offer.id);
                                    acceptOffer.mutate(offer.id);
                                  }}
                                  className="text-green-600 hover:text-green-700 p-1 rounded"
                                  title="قبول"
                                >
                                  <CheckCircle className="h-4 w-4" />
                                </button>
                                <button
                                  onClick={() => {
                                    setProcessingId(offer.id);
                                    rejectOffer.mutate(offer.id);
                                  }}
                                  className="text-red-500 hover:text-red-600 p-1 rounded"
                                  title="رفض"
                                >
                                  <XCircle className="h-4 w-4" />
                                </button>
                              </>
                            )}
                          </>
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
