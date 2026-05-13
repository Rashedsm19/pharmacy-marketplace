"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocale } from "next-intl";
import Link from "next/link";
import { toast } from "sonner";
import Shell from "@/components/layout/shell";
import { Badge } from "@/components/ui/badge";
import { reservationsApi } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import { XCircle, ArrowRight, Loader2 } from "lucide-react";

const STATUS_LABELS: Record<string, string> = {
  active: "نشط",
  confirmed: "مؤكد",
  expired: "منتهي",
  cancelled: "ملغى",
};

const STATUS_VARIANTS: Record<string, "success" | "default" | "danger" | "warning" | "info"> = {
  active: "info",
  confirmed: "success",
  expired: "warning",
  cancelled: "default",
};

export default function MyReservationsPage() {
  const locale = useLocale();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [cancellingId, setCancellingId] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["my-reservations", page],
    queryFn: () => reservationsApi.list({ page, page_size: 15 }).then((r) => r.data),
  });

  const cancelReservation = useMutation({
    mutationFn: (id: string) => reservationsApi.cancel(id),
    onSuccess: () => {
      toast.success("تم إلغاء الحجز");
      qc.invalidateQueries({ queryKey: ["my-reservations"] });
      setCancellingId(null);
    },
    onError: () => toast.error("فشل إلغاء الحجز"),
  });

  const reservations = data?.items ?? [];
  const totalPages = Math.ceil((data?.total ?? 0) / 15);

  return (
    <Shell>
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">حجوزاتي</h1>

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          {isLoading ? (
            <div className="flex items-center justify-center h-48">
              <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
            </div>
          ) : reservations.length === 0 ? (
            <div className="text-center py-16">
              <p className="text-gray-500 mb-4">لا توجد حجوزات نشطة</p>
              <Link
                href={`/${locale}/marketplace`}
                className="text-blue-600 hover:text-blue-700 text-sm font-medium"
              >
                تصفح السوق
              </Link>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">المنتج</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">البائع</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">المبلغ</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">الكمية</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">تاريخ الانتهاء</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">الحالة</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">الإجراءات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {reservations.map((res: {
                  id: string;
                  listing_id: string;
                  product_name_ar?: string;
                  product_name?: string;
                  seller_org_name?: string;
                  reserved_price: number;
                  quantity: number;
                  expires_at: string;
                  status: string;
                  transaction_id?: string;
                }) => (
                  <tr key={res.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-900">
                      {res.product_name_ar ?? res.product_name ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-gray-600">{res.seller_org_name ?? "—"}</td>
                    <td className="px-4 py-3 text-blue-600 font-semibold">
                      {formatCurrency(res.reserved_price)}
                    </td>
                    <td className="px-4 py-3 text-gray-600">{res.quantity}</td>
                    <td className="px-4 py-3 text-xs text-gray-500">
                      {formatDate(res.expires_at, "ar-SA")}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={STATUS_VARIANTS[res.status] ?? "default"}>
                        {STATUS_LABELS[res.status] ?? res.status}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5">
                        {res.transaction_id && (
                          <Link
                            href={`/${locale}/my/transactions`}
                            className="text-blue-600 hover:text-blue-700 p-1 rounded"
                            title="عرض المعاملة"
                          >
                            <ArrowRight className="h-4 w-4" />
                          </Link>
                        )}
                        {res.status === "active" && (
                          cancellingId === res.id ? (
                            <div className="flex items-center gap-1 text-xs text-gray-500">
                              <span>تأكيد؟</span>
                              <button
                                onClick={() => cancelReservation.mutate(res.id)}
                                className="text-red-600 font-medium"
                                disabled={cancelReservation.isPending}
                              >
                                نعم
                              </button>
                              <button onClick={() => setCancellingId(null)} className="text-gray-500">
                                لا
                              </button>
                            </div>
                          ) : (
                            <button
                              onClick={() => setCancellingId(res.id)}
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
