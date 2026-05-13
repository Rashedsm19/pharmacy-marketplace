"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocale } from "next-intl";
import { toast } from "sonner";
import Shell from "@/components/layout/shell";
import { Badge } from "@/components/ui/badge";
import { transactionsApi } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import { Truck, CheckCircle, Loader2, ChevronDown, ChevronUp } from "lucide-react";

const STATUS_LABELS: Record<string, string> = {
  pending: "قيد الانتظار",
  dispatched: "تم الشحن",
  completed: "مكتمل",
  disputed: "متنازع عليه",
  cancelled: "ملغى",
};

const STATUS_VARIANTS: Record<string, "success" | "default" | "danger" | "warning" | "info"> = {
  pending: "info",
  dispatched: "warning",
  completed: "success",
  disputed: "danger",
  cancelled: "default",
};

export default function MyTransactionsPage() {
  const locale = useLocale();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [roleFilter, setRoleFilter] = useState<"" | "seller" | "buyer">("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [processingId, setProcessingId] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["my-transactions", page, roleFilter],
    queryFn: () =>
      transactionsApi.list({ page, page_size: 15, role: roleFilter || undefined }).then((r) => r.data),
  });

  const dispatch = useMutation({
    mutationFn: (id: string) => transactionsApi.dispatch(id),
    onSuccess: () => {
      toast.success("تم تسجيل الشحن بنجاح");
      qc.invalidateQueries({ queryKey: ["my-transactions"] });
      setProcessingId(null);
    },
    onError: () => toast.error("فشل تسجيل الشحن"),
  });

  const confirmReceipt = useMutation({
    mutationFn: (id: string) => transactionsApi.confirmReceipt(id),
    onSuccess: () => {
      toast.success("تم تأكيد الاستلام وإتمام المعاملة");
      qc.invalidateQueries({ queryKey: ["my-transactions"] });
      setProcessingId(null);
    },
    onError: () => toast.error("فشل تأكيد الاستلام"),
  });

  const transactions = data?.items ?? [];
  const totalPages = Math.ceil((data?.total ?? 0) / 15);

  return (
    <Shell>
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">معاملاتي</h1>

        <div className="flex gap-2">
          {(["", "seller", "buyer"] as const).map((r) => (
            <button
              key={r}
              onClick={() => { setRoleFilter(r); setPage(1); }}
              className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
                roleFilter === r
                  ? "bg-blue-600 text-white border-blue-600"
                  : "border-gray-300 text-gray-600 hover:bg-gray-50"
              }`}
            >
              {r === "" ? "الكل" : r === "seller" ? "كبائع" : "كمشتري"}
            </button>
          ))}
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          {isLoading ? (
            <div className="flex items-center justify-center h-48">
              <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
            </div>
          ) : transactions.length === 0 ? (
            <div className="text-center py-16">
              <p className="text-gray-500">لا توجد معاملات</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {transactions.map((tx: {
                id: string;
                listing_id: string;
                product_name_ar?: string;
                product_name?: string;
                seller_org_name?: string;
                buyer_org_name?: string;
                total_amount: number;
                quantity: number;
                status: string;
                created_at: string;
                dispatched_at?: string;
                completed_at?: string;
                role?: string;
                tracking_number?: string;
              }) => (
                <div key={tx.id}>
                  <div
                    className="flex items-center gap-4 px-4 py-4 hover:bg-gray-50 cursor-pointer"
                    onClick={() => setExpandedId(expandedId === tx.id ? null : tx.id)}
                  >
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-gray-900 truncate">
                        {tx.product_name_ar ?? tx.product_name ?? "—"}
                      </p>
                      <p className="text-xs text-gray-400 mt-0.5">
                        {tx.role === "seller" ? `المشتري: ${tx.buyer_org_name}` : `البائع: ${tx.seller_org_name}`}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="font-semibold text-blue-600">{formatCurrency(tx.total_amount)}</p>
                      <p className="text-xs text-gray-400">{tx.quantity} وحدة</p>
                    </div>
                    <Badge variant={STATUS_VARIANTS[tx.status] ?? "default"}>
                      {STATUS_LABELS[tx.status] ?? tx.status}
                    </Badge>
                    {expandedId === tx.id ? (
                      <ChevronUp className="h-4 w-4 text-gray-400 flex-shrink-0" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-gray-400 flex-shrink-0" />
                    )}
                  </div>

                  {expandedId === tx.id && (
                    <div className="px-4 pb-4 bg-gray-50 border-t border-gray-100">
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-3 text-sm">
                        <div>
                          <p className="text-gray-400 text-xs">تاريخ الإنشاء</p>
                          <p className="font-medium">{formatDate(tx.created_at, "ar-SA")}</p>
                        </div>
                        {tx.dispatched_at && (
                          <div>
                            <p className="text-gray-400 text-xs">تاريخ الشحن</p>
                            <p className="font-medium">{formatDate(tx.dispatched_at, "ar-SA")}</p>
                          </div>
                        )}
                        {tx.completed_at && (
                          <div>
                            <p className="text-gray-400 text-xs">تاريخ الإتمام</p>
                            <p className="font-medium">{formatDate(tx.completed_at, "ar-SA")}</p>
                          </div>
                        )}
                        {tx.tracking_number && (
                          <div>
                            <p className="text-gray-400 text-xs">رقم التتبع</p>
                            <p className="font-medium" dir="ltr">{tx.tracking_number}</p>
                          </div>
                        )}
                      </div>

                      <div className="flex gap-2 mt-4">
                        {tx.status === "pending" && tx.role === "seller" && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setProcessingId(tx.id);
                              dispatch.mutate(tx.id);
                            }}
                            disabled={processingId === tx.id && dispatch.isPending}
                            className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-60"
                          >
                            {processingId === tx.id && dispatch.isPending ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <Truck className="h-3.5 w-3.5" />
                            )}
                            تسجيل الشحن
                          </button>
                        )}
                        {tx.status === "dispatched" && tx.role === "buyer" && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setProcessingId(tx.id);
                              confirmReceipt.mutate(tx.id);
                            }}
                            disabled={processingId === tx.id && confirmReceipt.isPending}
                            className="flex items-center gap-1.5 bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-60"
                          >
                            {processingId === tx.id && confirmReceipt.isPending ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <CheckCircle className="h-3.5 w-3.5" />
                            )}
                            تأكيد الاستلام
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
