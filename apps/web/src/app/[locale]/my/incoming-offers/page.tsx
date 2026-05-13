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
import { CheckCircle, XCircle, Eye, Loader2, MessageSquare, ChevronRight, ChevronLeft, Bell } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState } from "@/components/ui/empty-state";

const STATUS_LABELS: Record<string, string> = {
  pending: "قيد الانتظار",
  accepted: "مقبول",
  rejected: "مرفوض",
  cancelled: "ملغى",
  expired: "منتهي",
};

const STATUS_VARIANTS: Record<string, "success" | "default" | "danger" | "warning" | "brand"> = {
  pending: "brand",
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
        <PageHeader
          title={
            <span className="inline-flex items-center gap-3">
              العروض الواردة
              {pendingCount > 0 && (
                <span className="inline-flex items-center justify-center min-w-[28px] h-7 px-2 bg-gold-50 text-gold-700 ring-1 ring-inset ring-gold-200 text-xs font-semibold rounded-full tabular-nums">
                  {pendingCount} جديد
                </span>
              )}
            </span>
          }
          subtitle="عروض شراء واردة من صيدليات أخرى — اقبل أو ارفض"
        />

        <div className="bg-white ring-1 ring-slate-200/70 shadow-soft rounded-2xl overflow-hidden">
          {isLoading ? (
            <div className="p-5 space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="h-12 bg-slate-50 rounded-lg animate-pulse" />
              ))}
            </div>
          ) : offers.length === 0 ? (
            <EmptyState
              icon={Bell}
              title="لا توجد عروض واردة"
              description="ستظهر هنا فور وصول عرض على أحد إعلاناتك"
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm tabular-nums min-w-[760px]">
                <thead className="bg-slate-50/60 border-b border-slate-100">
                  <tr>
                    <th className="text-right px-4 py-3 text-[11px] uppercase tracking-wider font-semibold text-slate-500">الإعلان</th>
                    <th className="text-right px-4 py-3 text-[11px] uppercase tracking-wider font-semibold text-slate-500 hidden md:table-cell">المشتري</th>
                    <th className="text-right px-4 py-3 text-[11px] uppercase tracking-wider font-semibold text-slate-500">السعر</th>
                    <th className="text-right px-4 py-3 text-[11px] uppercase tracking-wider font-semibold text-slate-500">الكمية</th>
                    <th className="text-right px-4 py-3 text-[11px] uppercase tracking-wider font-semibold text-slate-500 hidden lg:table-cell">التاريخ</th>
                    <th className="text-right px-4 py-3 text-[11px] uppercase tracking-wider font-semibold text-slate-500">الحالة</th>
                    <th className="text-right px-4 py-3 text-[11px] uppercase tracking-wider font-semibold text-slate-500">إجراءات</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100/80">
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
                    <tr
                      key={offer.id}
                      className={`hover:bg-slate-50/60 transition-colors ${
                        offer.status === "pending" ? "bg-brand-50/30" : ""
                      }`}
                    >
                      <td className="px-4 py-3">
                        <div>
                          <p className="font-medium text-slate-900">
                            {offer.listing_product_name_ar ?? offer.listing_product_name ?? "—"}
                          </p>
                          {offer.message && (
                            <div className="flex items-center gap-1 mt-0.5">
                              <MessageSquare className="h-3 w-3 text-slate-400" />
                              <p className="text-xs text-slate-400 truncate max-w-36">
                                {offer.message}
                              </p>
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-slate-600 hidden md:table-cell">{offer.buyer_org_name ?? "—"}</td>
                      <td className="px-4 py-3 text-brand-700 font-semibold">
                        {formatCurrency(offer.offered_price)}
                      </td>
                      <td className="px-4 py-3 text-slate-700">{offer.quantity}</td>
                      <td className="px-4 py-3 text-slate-500 text-xs hidden lg:table-cell">
                        {formatDate(offer.created_at, "ar-SA")}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={STATUS_VARIANTS[offer.status] ?? "default"}>
                          {STATUS_LABELS[offer.status] ?? offer.status}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1">
                          <Link
                            href={`/${locale}/marketplace/${offer.listing_id}`}
                            className="h-8 w-8 inline-flex items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-700"
                            title="عرض الإعلان"
                          >
                            <Eye className="h-4 w-4" />
                          </Link>
                          {offer.status === "pending" && (
                            <>
                              {processingId === offer.id ? (
                                <Loader2 className="h-4 w-4 animate-spin text-slate-400 mx-1" />
                              ) : (
                                <>
                                  <button
                                    onClick={() => {
                                      setProcessingId(offer.id);
                                      acceptOffer.mutate(offer.id);
                                    }}
                                    className="h-8 w-8 inline-flex items-center justify-center rounded-lg bg-emerald-50 text-emerald-700 hover:bg-emerald-100 ring-1 ring-inset ring-emerald-200"
                                    title="قبول"
                                  >
                                    <CheckCircle className="h-4 w-4" />
                                  </button>
                                  <button
                                    onClick={() => {
                                      setProcessingId(offer.id);
                                      rejectOffer.mutate(offer.id);
                                    }}
                                    className="h-8 w-8 inline-flex items-center justify-center rounded-lg bg-rose-50 text-rose-600 hover:bg-rose-100 ring-1 ring-inset ring-rose-200"
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
            </div>
          )}
        </div>

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
