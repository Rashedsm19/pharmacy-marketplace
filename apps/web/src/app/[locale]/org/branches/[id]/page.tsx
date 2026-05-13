"use client";

import { useQuery } from "@tanstack/react-query";
import { useLocale } from "next-intl";
import { useParams } from "next/navigation";
import Link from "next/link";
import Shell from "@/components/layout/shell";
import { Badge } from "@/components/ui/badge";
import { branchesApi, inventoryApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { ChevronRight, Loader2, CheckCircle, XCircle, Thermometer, Shield } from "lucide-react";

export default function BranchDetailPage() {
  const locale = useLocale();
  const { id } = useParams<{ id: string }>();

  const { data: branch, isLoading } = useQuery({
    queryKey: ["branch", id],
    queryFn: () => branchesApi.get(id).then((r) => r.data),
  });

  const { data: batchStats } = useQuery({
    queryKey: ["branch-batch-stats", id],
    queryFn: () => inventoryApi.listBatches({ branch_id: id, page: 1, page_size: 1 }).then((r) => r.data),
    enabled: !!id,
  });

  if (isLoading) {
    return (
      <Shell>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
        </div>
      </Shell>
    );
  }

  if (!branch) {
    return (
      <Shell>
        <p className="text-gray-500">لم يتم العثور على الفرع</p>
      </Shell>
    );
  }

  const storageCompliant = branch.storage_condition_status === "compliant";

  return (
    <Shell>
      <div className="max-w-3xl space-y-6">
        <div className="flex items-center gap-3">
          <Link href={`/${locale}/org/branches`} className="text-gray-500 hover:text-gray-700">
            <ChevronRight className="h-5 w-5" />
          </Link>
          <h1 className="text-2xl font-bold text-gray-900">{branch.name_ar ?? branch.name}</h1>
          <Badge variant={branch.is_active ? "success" : "default"}>
            {branch.is_active ? "نشط" : "غير نشط"}
          </Badge>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
          {/* Branch info */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 space-y-4">
            <h2 className="font-semibold text-gray-900">معلومات الفرع</h2>
            <div className="space-y-3 text-sm">
              <DetailRow label="الاسم العربي" value={branch.name_ar} />
              <DetailRow label="الاسم الإنجليزي" value={branch.name} />
              <DetailRow label="العنوان" value={branch.address} />
              <DetailRow label="الهاتف" value={branch.phone} />
              <DetailRow label="مدير الفرع" value={branch.manager_name} />
              <DetailRow
                label="تاريخ الإنشاء"
                value={branch.created_at ? formatDate(branch.created_at, "ar-SA") : undefined}
              />
            </div>
          </div>

          {/* Storage compliance */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 space-y-4">
            <div className="flex items-center gap-2">
              <Shield className="h-5 w-5 text-blue-600" />
              <h2 className="font-semibold text-gray-900">الامتثال التخزيني</h2>
            </div>

            <div className={`flex items-center gap-2 p-3 rounded-lg ${storageCompliant ? "bg-green-50" : "bg-red-50"}`}>
              {storageCompliant ? (
                <CheckCircle className="h-5 w-5 text-green-500" />
              ) : (
                <XCircle className="h-5 w-5 text-red-500" />
              )}
              <span className={`font-medium text-sm ${storageCompliant ? "text-green-800" : "text-red-800"}`}>
                {storageCompliant ? "مطابق لمعايير التخزين" : "غير مطابق لمعايير التخزين"}
              </span>
            </div>

            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-gray-500">مساحة التخزين</span>
                <span className="font-medium">{branch.storage_area_sqm ? `${branch.storage_area_sqm} م²` : "—"}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-500 flex items-center gap-1">
                  <Thermometer className="h-3.5 w-3.5" />
                  تخزين بارد
                </span>
                {branch.has_cold_storage ? (
                  <CheckCircle className="h-4 w-4 text-green-500" />
                ) : (
                  <XCircle className="h-4 w-4 text-gray-300" />
                )}
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-500">تخزين مسيطر</span>
                {branch.has_controlled_storage ? (
                  <CheckCircle className="h-4 w-4 text-green-500" />
                ) : (
                  <XCircle className="h-4 w-4 text-gray-300" />
                )}
              </div>
              {branch.last_inspection_date && (
                <div className="flex items-center justify-between">
                  <span className="text-gray-500">آخر تفتيش</span>
                  <span className="font-medium">{formatDate(branch.last_inspection_date, "ar-SA")}</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Batch summary */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h2 className="font-semibold text-gray-900 mb-4">ملخص المخزون</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
            {[
              { label: "إجمالي الدفعات", value: batchStats?.total ?? branch.batch_count ?? 0 },
              { label: "الدفعات النشطة", value: branch.active_batch_count ?? "—" },
              { label: "قريبة الانتهاء", value: branch.near_expiry_count ?? "—" },
              { label: "الإعلانات النشطة", value: branch.active_listings_count ?? "—" },
            ].map((item) => (
              <div key={item.label} className="bg-gray-50 rounded-lg p-3">
                <p className="text-gray-400 text-xs">{item.label}</p>
                <p className="font-bold text-gray-900 text-xl mt-1">{item.value}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="flex gap-3">
          <Link
            href={`/${locale}/inventory/batches?branch_id=${id}`}
            className="flex-1 text-center border border-gray-300 text-gray-700 py-2.5 rounded-lg text-sm font-medium hover:bg-gray-50"
          >
            عرض دفعات الفرع
          </Link>
          <Link
            href={`/${locale}/inventory/near-expiry?branch_id=${id}`}
            className="flex-1 text-center bg-blue-600 hover:bg-blue-700 text-white py-2.5 rounded-lg text-sm font-medium"
          >
            الدفعات قريبة الانتهاء
          </Link>
        </div>
      </div>
    </Shell>
  );
}

function DetailRow({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-gray-500">{label}</span>
      <span className="font-medium text-gray-900">{value ?? "—"}</span>
    </div>
  );
}
