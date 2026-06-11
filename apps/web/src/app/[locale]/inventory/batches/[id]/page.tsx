"use client";

import { useQuery } from "@tanstack/react-query";
import { useLocale } from "next-intl";
import { useParams } from "next/navigation";
import Shell from "@/components/layout/shell";
import { ExpiryBadge } from "@/components/ui/expiry-badge";
import { inventoryApi } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import Link from "next/link";
import { ChevronRight, Package } from "lucide-react";

export default function BatchDetailPage() {
  const locale = useLocale();
  const { id } = useParams<{ id: string }>();

  const { data: batch, isLoading } = useQuery({
    queryKey: ["batch", id],
    queryFn: () => inventoryApi.getBatch(id).then((r) => r.data),
  });

  const { data: fefo } = useQuery({
    queryKey: ["batch-fefo", id],
    queryFn: () => inventoryApi.fefoRecommendation(id).then((r) => r.data),
    enabled: !!batch,
  });

  if (isLoading) {
    return (
      <Shell>
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin h-8 w-8 border-4 border-brand-600 border-t-transparent rounded-full" />
        </div>
      </Shell>
    );
  }

  if (!batch) return <Shell><p className="text-gray-500">لم يتم العثور على الدفعة</p></Shell>;

  return (
    <Shell>
      <div className="max-w-3xl space-y-6">
        <div className="flex items-center gap-3">
          <Link href={`/${locale}/inventory/batches`} className="text-gray-500 hover:text-gray-700">
            <ChevronRight className="h-5 w-5" />
          </Link>
          <h1 className="text-2xl font-bold text-gray-900">
            {batch.product_name_ar ?? batch.product_name ?? "دفعة"}
          </h1>
          {batch.days_until_expiry !== undefined && (
            <ExpiryBadge daysUntilExpiry={batch.days_until_expiry} />
          )}
        </div>

        {/* Batch Details */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h2 className="font-semibold text-gray-900 mb-4">تفاصيل الدفعة</h2>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <Detail label="رقم الدفعة" value={batch.batch_number} />
            <Detail label="المنتج" value={batch.product_name_ar ?? batch.product_name} />
            <Detail label="الفرع" value={batch.branch_name} />
            <Detail
              label="تاريخ الانتهاء"
              value={formatDate(batch.expiry_date, "ar-SA")}
            />
            <Detail label="الكمية المتاحة" value={`${batch.quantity_available} من ${batch.quantity}`} />
            <Detail
              label="سعر الوحدة"
              value={batch.unit_cost ? formatCurrency(batch.unit_cost) : "غير محدد"}
            />
            <Detail label="المورد" value={batch.supplier ?? "غير محدد"} />
            <Detail label="حالة التخزين" value={batch.storage_condition_status} />
            <Detail
              label="مفتوح"
              value={batch.is_opened ? "نعم" : "لا"}
            />
            <Detail
              label="صُرف لمريض"
              value={batch.is_patient_dispensed ? "نعم" : "لا"}
            />
          </div>
        </div>

        {/* FEFO Recommendation */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h2 className="font-semibold text-gray-900 mb-2">توصية FEFO</h2>
          <p className="text-sm text-gray-500 mb-4">
            الدفعات الموصى بصرفها أولاً (الأقرب للانتهاء)
          </p>
          {!fefo?.length ? (
            <div className="flex items-center gap-2 text-gray-400 text-sm">
              <Package className="h-4 w-4" />
              لا توجد دفعات أخرى لهذا المنتج
            </div>
          ) : (
            <div className="space-y-2">
              {fefo.map((b: { id: string; batch_number: string; days_until_expiry?: number; quantity_available: number }, idx: number) => (
                <div
                  key={b.id}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-bold text-gray-400">#{idx + 1}</span>
                    <div>
                      <p className="text-sm font-medium">{b.batch_number}</p>
                      <p className="text-xs text-gray-500">كمية متاحة: {b.quantity_available}</p>
                    </div>
                  </div>
                  {b.days_until_expiry !== undefined && (
                    <ExpiryBadge daysUntilExpiry={b.days_until_expiry} />
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </Shell>
  );
}

function Detail({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div>
      <p className="text-gray-500 text-xs mb-0.5">{label}</p>
      <p className="font-medium text-gray-900">{value ?? "—"}</p>
    </div>
  );
}
