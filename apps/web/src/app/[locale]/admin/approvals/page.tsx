"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import Shell from "@/components/layout/shell";
import { Badge } from "@/components/ui/badge";
import { adminApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { CheckCircle, XCircle, Loader2, Building2, Eye } from "lucide-react";

export default function AdminApprovalsPage() {
  const qc = useQueryClient();
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["admin-approvals", page],
    queryFn: () => adminApi.getApprovals({ page, page_size: 15 }).then((r) => r.data),
  });

  const approve = useMutation({
    mutationFn: (id: string) => adminApi.approveOrg(id),
    onSuccess: () => {
      toast.success("تم قبول المنشأة");
      qc.invalidateQueries({ queryKey: ["admin-approvals"] });
      setProcessingId(null);
    },
    onError: () => toast.error("فشل القبول"),
  });

  const reject = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => adminApi.rejectOrg(id, reason),
    onSuccess: () => {
      toast.success("تم رفض المنشأة");
      qc.invalidateQueries({ queryKey: ["admin-approvals"] });
      setRejectingId(null);
      setRejectReason("");
    },
    onError: () => toast.error("فشل الرفض"),
  });

  const orgs = data?.items ?? [];
  const totalPages = Math.ceil((data?.total ?? 0) / 15);

  return (
    <Shell>
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <Building2 className="h-6 w-6 text-purple-600" />
          <h1 className="text-2xl font-bold text-gray-900">طلبات الموافقة</h1>
          {data?.total ? (
            <span className="bg-purple-100 text-purple-700 text-xs font-semibold px-2.5 py-1 rounded-full">
              {data.total} طلب
            </span>
          ) : null}
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          {isLoading ? (
            <div className="flex items-center justify-center h-48">
              <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
            </div>
          ) : orgs.length === 0 ? (
            <div className="text-center py-16">
              <CheckCircle className="h-12 w-12 text-green-300 mx-auto mb-3" />
              <p className="text-gray-500">لا توجد طلبات معلقة</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {orgs.map((org: {
                id: string;
                name_ar?: string;
                name: string;
                license_number?: string;
                tax_number?: string;
                phone?: string;
                email?: string;
                created_at: string;
                status: string;
                branch_count?: number;
              }) => (
                <div key={org.id} className="p-5">
                  {rejectingId === org.id ? (
                    <div className="space-y-3">
                      <p className="font-medium text-gray-900">سبب الرفض لـ {org.name_ar ?? org.name}</p>
                      <textarea
                        value={rejectReason}
                        onChange={(e) => setRejectReason(e.target.value)}
                        rows={3}
                        placeholder="اذكر سبب الرفض..."
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
                      />
                      <div className="flex gap-2">
                        <button
                          onClick={() => { setRejectingId(null); setRejectReason(""); }}
                          className="px-4 py-2 border border-gray-300 text-gray-600 rounded-lg text-sm hover:bg-gray-50"
                        >
                          إلغاء
                        </button>
                        <button
                          onClick={() => reject.mutate({ id: org.id, reason: rejectReason })}
                          disabled={!rejectReason.trim() || reject.isPending}
                          className="flex items-center gap-1.5 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium disabled:opacity-60"
                        >
                          {reject.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                          تأكيد الرفض
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-start gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="font-semibold text-gray-900">{org.name_ar ?? org.name}</h3>
                          <Badge variant="warning">قيد المراجعة</Badge>
                        </div>
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs text-gray-500 mt-2">
                          {org.license_number && <span>الترخيص: {org.license_number}</span>}
                          {org.tax_number && <span>الرقم الضريبي: {org.tax_number}</span>}
                          {org.phone && <span dir="ltr">{org.phone}</span>}
                          {org.email && <span dir="ltr">{org.email}</span>}
                          <span>تاريخ التسجيل: {formatDate(org.created_at, "ar-SA")}</span>
                          {org.branch_count !== undefined && <span>{org.branch_count} فرع</span>}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <button
                          onClick={() => {
                            setProcessingId(org.id);
                            approve.mutate(org.id);
                          }}
                          disabled={processingId === org.id && approve.isPending}
                          className="flex items-center gap-1.5 px-3 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg text-xs font-medium disabled:opacity-60"
                        >
                          {processingId === org.id && approve.isPending ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <CheckCircle className="h-3.5 w-3.5" />
                          )}
                          قبول
                        </button>
                        <button
                          onClick={() => setRejectingId(org.id)}
                          className="flex items-center gap-1.5 px-3 py-2 bg-red-100 hover:bg-red-200 text-red-700 rounded-lg text-xs font-medium"
                        >
                          <XCircle className="h-3.5 w-3.5" />
                          رفض
                        </button>
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
