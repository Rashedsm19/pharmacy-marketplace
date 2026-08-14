"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertTriangle, Loader2, MessageSquare } from "lucide-react";

import Shell from "@/components/layout/shell";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState } from "@/components/ui/empty-state";
import { Button } from "@/components/ui/button";
import { disputesApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Dispute, DisputeSummary } from "@/components/dispute-shared";

export default function MyDisputesPage() {
  const qc = useQueryClient();
  const [respondingId, setRespondingId] = useState<string | null>(null);
  const [response, setResponse] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["my-disputes"],
    queryFn: () => disputesApi.list({ page_size: 50 }).then((r) => r.data),
  });

  const respond = useMutation({
    mutationFn: ({ id, text }: { id: string; text: string }) =>
      disputesApi.respond(id, text),
    onSuccess: () => {
      toast.success("أرسل ردك");
      setRespondingId(null);
      setResponse("");
      qc.invalidateQueries({ queryKey: ["my-disputes"] });
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : "تعذر إرسال الرد");
    },
  });

  const disputes: Dispute[] = data?.items ?? [];

  return (
    <Shell>
      <div className="space-y-5">
        <PageHeader
          title="النزاعات"
          subtitle="بلاغات على معاملات منشأتك — المقدمة منك والواردة إليك"
        />

        {isLoading ? (
          <div className="flex items-center justify-center h-48">
            <Loader2 className="h-7 w-7 animate-spin text-brand-600" />
          </div>
        ) : disputes.length === 0 ? (
          <EmptyState
            icon={AlertTriangle}
            title="لا توجد نزاعات"
            description="لم يفتح أي بلاغ على معاملات منشأتك. يمكنك فتح بلاغ من صفحة المعاملة عند وصول شحنة ناقصة أو تالفة."
          />
        ) : (
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 divide-y divide-gray-100">
            {disputes.map((dispute) => (
              <div key={dispute.id} className="p-5">
                <div className="flex items-start justify-between gap-4 flex-wrap sm:flex-nowrap">
                  <DisputeSummary dispute={dispute} />
                  <div className="text-xs text-[#8a938e] flex-shrink-0">
                    {formatDate(dispute.created_at, "ar-SA")}
                  </div>
                </div>

                {dispute.seller_response && (
                  <div className="mt-3 rounded-lg bg-[#f7f1e6] px-4 py-3">
                    <p className="text-xs font-bold text-[#55605b] mb-1">رد الطرف الآخر</p>
                    <p className="text-sm text-[#1f2823]">{dispute.seller_response}</p>
                  </div>
                )}

                {dispute.resolution_notes && (
                  <div className="mt-3 rounded-lg bg-[#e4f7f5] px-4 py-3">
                    <p className="text-xs font-bold text-[#066a65] mb-1">قرار المنصة</p>
                    <p className="text-sm text-[#1f2823]">{dispute.resolution_notes}</p>
                    {dispute.refund_amount != null && (
                      <p className="text-sm font-bold text-[#066a65] mt-1">
                        مبلغ الاسترداد: {dispute.refund_amount} ر.س
                      </p>
                    )}
                  </div>
                )}

                {/* Only an unresolved case that has not been answered can be answered */}
                {dispute.status === "open" && (
                  <div className="mt-3">
                    {respondingId === dispute.id ? (
                      <div className="space-y-2">
                        <textarea
                          value={response}
                          onChange={(e) => setResponse(e.target.value)}
                          rows={3}
                          placeholder="اكتب ردك على البلاغ…"
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                        />
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            variant="primary"
                            disabled={response.trim().length < 5}
                            loading={respond.isPending}
                            onClick={() => respond.mutate({ id: dispute.id, text: response })}
                          >
                            إرسال الرد
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setRespondingId(null);
                              setResponse("");
                            }}
                          >
                            إلغاء
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setRespondingId(dispute.id)}
                      >
                        <MessageSquare className="h-3.5 w-3.5" />
                        الرد على البلاغ
                      </Button>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </Shell>
  );
}
