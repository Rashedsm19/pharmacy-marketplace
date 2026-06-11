"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import Shell from "@/components/layout/shell";
import { Badge } from "@/components/ui/badge";
import { adminApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { CheckCircle, XCircle, Building2, ChevronRight, ChevronLeft } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";

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
        <PageHeader
          title={
            <span className="inline-flex items-center gap-3">
              <Building2 className="h-5 w-5 sm:h-6 sm:w-6 text-gold-600" />
              طلبات الموافقة
              {data?.total ? (
                <span className="inline-flex items-center justify-center min-w-[28px] h-7 px-2 bg-gold-50 text-gold-700 ring-1 ring-inset ring-gold-200 text-xs font-semibold rounded-full tabular-nums">
                  {data.total}
                </span>
              ) : null}
            </span>
          }
          subtitle="مراجعة طلبات الصيدليات الجديدة قبل تفعيلها على المنصة"
        />

        <div className="bg-white ring-1 ring-slate-200/70 shadow-soft rounded-2xl overflow-hidden">
          {isLoading ? (
            <div className="p-5 space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="h-20 bg-slate-50 rounded-lg animate-pulse" />
              ))}
            </div>
          ) : orgs.length === 0 ? (
            <EmptyState
              icon={CheckCircle}
              title="لا توجد طلبات معلقة"
              description="جميع طلبات الانضمام تمت معالجتها"
            />
          ) : (
            <div className="divide-y divide-slate-100">
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
                      <p className="font-medium text-slate-900">
                        سبب الرفض لـ <span className="text-rose-700">{org.name_ar ?? org.name}</span>
                      </p>
                      <textarea
                        value={rejectReason}
                        onChange={(e) => setRejectReason(e.target.value)}
                        rows={3}
                        placeholder="اذكر سبب الرفض..."
                        className="w-full px-3 py-2 bg-slate-50/60 ring-1 ring-inset ring-slate-200 rounded-lg text-sm placeholder:text-slate-400 focus:outline-none focus:bg-white focus:ring-2 focus:ring-rose-500"
                      />
                      <div className="flex gap-2 justify-end">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => { setRejectingId(null); setRejectReason(""); }}
                        >
                          إلغاء
                        </Button>
                        <Button
                          variant="danger"
                          size="sm"
                          onClick={() => reject.mutate({ id: org.id, reason: rejectReason })}
                          disabled={!rejectReason.trim()}
                          loading={reject.isPending}
                        >
                          تأكيد الرفض
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-start gap-4 flex-wrap sm:flex-nowrap">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2">
                          <h3 className="font-semibold text-slate-900">
                            {org.name_ar ?? org.name}
                          </h3>
                          <Badge variant="warning">قيد المراجعة</Badge>
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-4 gap-y-1.5 text-xs text-slate-600">
                          {org.license_number && (
                            <div>
                              <span className="text-slate-400">الترخيص: </span>
                              <span className="font-medium tabular-nums">{org.license_number}</span>
                            </div>
                          )}
                          {org.tax_number && (
                            <div>
                              <span className="text-slate-400">الرقم الضريبي: </span>
                              <span className="font-medium tabular-nums">{org.tax_number}</span>
                            </div>
                          )}
                          {org.phone && (
                            <div dir="ltr" className="text-right">
                              <span className="text-slate-400">📞 </span>
                              <span className="font-medium">{org.phone}</span>
                            </div>
                          )}
                          {org.email && (
                            <div dir="ltr" className="text-right truncate">
                              <span className="text-slate-400">✉ </span>
                              <span className="font-medium">{org.email}</span>
                            </div>
                          )}
                          <div>
                            <span className="text-slate-400">التسجيل: </span>
                            <span className="font-medium">{formatDate(org.created_at, "ar-SA")}</span>
                          </div>
                          {org.branch_count !== undefined && (
                            <div>
                              <span className="text-slate-400">الفروع: </span>
                              <span className="font-medium tabular-nums">{org.branch_count}</span>
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => {
                            setProcessingId(org.id);
                            approve.mutate(org.id);
                          }}
                          loading={processingId === org.id && approve.isPending}
                          className="bg-emerald-600 hover:bg-emerald-700"
                        >
                          <CheckCircle className="h-3.5 w-3.5" />
                          قبول
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setRejectingId(org.id)}
                          className="text-rose-600 ring-rose-200 hover:bg-rose-50"
                        >
                          <XCircle className="h-3.5 w-3.5" />
                          رفض
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
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
