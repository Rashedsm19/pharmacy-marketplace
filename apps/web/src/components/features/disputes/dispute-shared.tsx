"use client";

import { Badge } from "@/components/ui/badge";

export type Dispute = {
  id: string;
  transaction_id: string;
  raised_by_organization_id: string;
  reason: string;
  status: string;
  description: string;
  disputed_quantity?: number | null;
  seller_response?: string | null;
  resolution_notes?: string | null;
  refund_amount?: number | null;
  created_at: string;
  transaction_reference?: string | null;
  raised_by_org_name?: string | null;
  product_name_ar?: string | null;
};

export const REASON_LABELS: Record<string, string> = {
  quantity_short: "نقص في الكمية",
  damaged: "تلف في المنتج",
  wrong_product: "منتج مختلف",
  expiry_mismatch: "تاريخ انتهاء غير مطابق",
  cold_chain_breach: "إخلال بسلسلة التبريد",
  suspected_counterfeit: "اشتباه بمنتج مزيف",
  not_received: "لم تصل الشحنة",
  other: "أخرى",
};

export const STATUS_LABELS: Record<
  string,
  { label: string; variant: "success" | "warning" | "danger" | "default" }
> = {
  open: { label: "مفتوح", variant: "warning" },
  seller_responded: { label: "بانتظار القرار", variant: "warning" },
  resolved_refund: { label: "قبل — استرداد", variant: "success" },
  resolved_replacement: { label: "قبل — استبدال", variant: "success" },
  resolved_rejected: { label: "رفض", variant: "danger" },
  withdrawn: { label: "مسحوب", variant: "default" },
};

/** A counterfeit claim carries regulatory weight, so it is marked apart. */
export function isCritical(reason: string) {
  return reason === "suspected_counterfeit";
}

export function DisputeStatusBadge({ status }: { status: string }) {
  const config = STATUS_LABELS[status] ?? { label: status, variant: "default" as const };
  return <Badge variant={config.variant}>{config.label}</Badge>;
}

export function DisputeSummary({ dispute }: { dispute: Dispute }) {
  return (
    <div className="min-w-0">
      <div className="flex items-center gap-2 flex-wrap mb-1">
        <span className="font-semibold text-[#1f2823]">
          {REASON_LABELS[dispute.reason] ?? dispute.reason}
        </span>
        <DisputeStatusBadge status={dispute.status} />
        {isCritical(dispute.reason) && (
          <span className="text-[11px] font-bold text-[#b4231f] bg-[#fbe7e5] px-2 py-0.5 rounded">
            بلاغ حرج
          </span>
        )}
      </div>
      <p className="text-sm text-[#55605b] leading-relaxed">{dispute.description}</p>
      <div className="flex items-center gap-3 mt-1.5 text-xs text-[#8a938e] flex-wrap">
        {dispute.product_name_ar && <span>{dispute.product_name_ar}</span>}
        {dispute.transaction_reference && (
          <span dir="ltr" className="tabular-nums">
            {dispute.transaction_reference}
          </span>
        )}
        {dispute.disputed_quantity != null && <span>الكمية: {dispute.disputed_quantity}</span>}
        {dispute.raised_by_org_name && <span>مقدم البلاغ: {dispute.raised_by_org_name}</span>}
      </div>
    </div>
  );
}
