"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertTriangle, CheckCircle, Loader2, RotateCcw, XCircle } from "lucide-react";

import Shell from "@/components/layout/shell";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState } from "@/components/ui/empty-state";
import { Button } from "@/components/ui/button";
import { disputesApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Dispute, DisputeSummary } from "@/components/dispute-shared";

const OUTCOMES = [
  {
    value: "resolved_refund",
    label: "قبول واسترداد",
    hint: "تُعاد الكمية لمخزون البائع ويُسترد مقابلها",
    icon: <RotateCcw className="h-3.5 w-3.5" />,
    className: "bg-emerald-600 hover:bg-emerald-700",
  },
  {
    value: "resolved_replacement",
    label: "قبول واستبدال",
    hint: "يلتزم البائع بإرسال بديل، وتبقى الصفقة قائمة",
    icon: <CheckCircle className="h-3.5 w-3.5" />,
    className: "bg-brand-600 hover:bg-brand-700",
  },
  {
    value: "resolved_rejected",
    label: "رفض البلاغ",
    hint: "تبقى الصفقة مكتملة كما هي",
    icon: <XCircle className="h-3.5 w-3.5" />,
    className: "bg-rose-600 hover:bg-rose-700",
  },
];

export default function AdminDisputesPage() {
  const qc = useQueryClient();
  const [decidingId, setDecidingId] = useState<string | null>(null);
  const [outcome, setOutcome] = useState("resolved_refund");
  const [notes, setNotes] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["admin-disputes"],
    queryFn: () => disputesApi.queue({ page_size: 50 }).then((r) => r.data),
  });

  const resolve = useMutation({
    mutationFn: ({ id }: { id: string }) => disputesApi.resolve(id, outcome, notes),
    onSuccess: () => {
      toast.success("صدر القرار");
      setDecidingId(null);
      setNotes("");
      qc.invalidateQueries({ queryKey: ["admin-disputes"] });
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : "تعذّر إصدار القرار");
    },
  });

  const disputes: Dispute[] = data?.items ?? [];

  return (
    <Shell>
      <div className="space-y-5">
        <PageHeader
          title="طابور النزاعات"
          subtitle={`بلاغات تنتظر قرار المنصة — الأقدم أولاً${disputes.length ? ` · ${disputes.length}` : ""}`}
        />

        {isLoading ? (
          <div className="flex items-center justify-center h-48">
            <Loader2 className="h-7 w-7 animate-spin text-brand-600" />
          </div>
        ) : disputes.length === 0 ? (
          <EmptyState
            icon={AlertTriangle}
            title="لا بلاغات معلّقة"
            description="لا يوجد نزاع ينتظر قراراً. ستظهر البلاغات الجديدة هنا فور فتحها."
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
                    <p className="text-xs font-bold text-[#55605b] mb-1">ردّ الطرف الآخر</p>
                    <p className="text-sm text-[#1f2823]">{dispute.seller_response}</p>
                  </div>
                )}

                {decidingId === dispute.id ? (
                  <div className="mt-4 space-y-3 rounded-lg border border-[#e8dfcf] p-4">
                    <div className="flex flex-wrap gap-2">
                      {OUTCOMES.map((option) => (
                        <button
                          key={option.value}
                          type="button"
                          onClick={() => setOutcome(option.value)}
                          className={`rounded-lg px-3 py-2 text-xs font-bold border ${
                            outcome === option.value
                              ? "border-brand-600 bg-brand-50 text-brand-700"
                              : "border-gray-200 text-gray-600 hover:bg-gray-50"
                          }`}
                        >
                          {option.label}
                        </button>
                      ))}
                    </div>
                    <p className="text-xs text-[#8a938e]">
                      {OUTCOMES.find((o) => o.value === outcome)?.hint}
                    </p>
                    <textarea
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      rows={3}
                      placeholder="سبب القرار — يظهر للطرفين"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                    />
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="primary"
                        disabled={notes.trim().length < 5}
                        loading={resolve.isPending}
                        onClick={() => resolve.mutate({ id: dispute.id })}
                      >
                        إصدار القرار
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setDecidingId(null);
                          setNotes("");
                        }}
                      >
                        إلغاء
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="mt-3">
                    <Button size="sm" variant="primary" onClick={() => setDecidingId(dispute.id)}>
                      حسم البلاغ
                    </Button>
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
