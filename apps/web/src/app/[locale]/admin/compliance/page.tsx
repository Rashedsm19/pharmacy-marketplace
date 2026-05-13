"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import Shell from "@/components/layout/shell";
import { Badge } from "@/components/ui/badge";
import { adminApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Loader2, Shield, CheckCircle, XCircle, AlertTriangle } from "lucide-react";

export default function AdminCompliancePage() {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState<"all" | "non_compliant" | "pending_review">("non_compliant");

  const { data, isLoading } = useQuery({
    queryKey: ["admin-compliance", page, filter],
    queryFn: () => adminApi.getCompliance({ page, page_size: 15, filter }).then((r) => r.data),
  });

  const updateCompliance = useMutation({
    mutationFn: ({ branchId, status }: { branchId: string; status: string }) =>
      adminApi.updateBranchCompliance(branchId, status),
    onSuccess: () => {
      toast.success("تم تحديث حالة الامتثال");
      qc.invalidateQueries({ queryKey: ["admin-compliance"] });
    },
    onError: () => toast.error("فشل تحديث الامتثال"),
  });

  const branches = data?.items ?? [];
  const totalPages = Math.ceil((data?.total ?? 0) / 15);

  return (
    <Shell>
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <Shield className="h-6 w-6 text-purple-600" />
          <h1 className="text-2xl font-bold text-gray-900">مراجعة الامتثال</h1>
        </div>

        {/* Filter tabs */}
        <div className="flex gap-2 border-b border-gray-200">
          {([
            { key: "non_compliant", label: "غير مطابق" },
            { key: "pending_review", label: "بانتظار المراجعة" },
            { key: "all", label: "الكل" },
          ] as const).map((tab) => (
            <button
              key={tab.key}
              onClick={() => { setFilter(tab.key); setPage(1); }}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                filter === tab.key
                  ? "border-purple-600 text-purple-700"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          {isLoading ? (
            <div className="flex items-center justify-center h-48">
              <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
            </div>
          ) : branches.length === 0 ? (
            <div className="text-center py-16">
              <CheckCircle className="h-12 w-12 text-green-300 mx-auto mb-3" />
              <p className="text-gray-500">لا توجد مشكلات امتثال</p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">الفرع</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">المنشأة</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">حالة التخزين</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">آخر تفتيش</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">المشكلات</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">الإجراءات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {branches.map((b: {
                  id: string;
                  name_ar?: string;
                  name: string;
                  org_name_ar?: string;
                  org_name: string;
                  storage_condition_status: string;
                  last_inspection_date?: string;
                  compliance_issues?: string[];
                }) => (
                  <tr key={b.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-900">{b.name_ar ?? b.name}</td>
                    <td className="px-4 py-3 text-gray-600">{b.org_name_ar ?? b.org_name}</td>
                    <td className="px-4 py-3">
                      <Badge variant={b.storage_condition_status === "compliant" ? "success" : "danger"}>
                        {b.storage_condition_status === "compliant" ? "مطابق" : "غير مطابق"}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {b.last_inspection_date ? formatDate(b.last_inspection_date, "ar-SA") : "لم يتم التفتيش"}
                    </td>
                    <td className="px-4 py-3">
                      {b.compliance_issues?.length ? (
                        <div className="flex items-center gap-1 text-orange-600">
                          <AlertTriangle className="h-3.5 w-3.5" />
                          <span className="text-xs">{b.compliance_issues.length} مشكلة</span>
                        </div>
                      ) : (
                        <span className="text-gray-400 text-xs">لا مشكلات</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-1.5">
                        <button
                          onClick={() => updateCompliance.mutate({ branchId: b.id, status: "compliant" })}
                          className="flex items-center gap-1 px-2 py-1 bg-green-100 hover:bg-green-200 text-green-700 rounded text-xs"
                        >
                          <CheckCircle className="h-3 w-3" />
                          مطابق
                        </button>
                        <button
                          onClick={() => updateCompliance.mutate({ branchId: b.id, status: "non_compliant" })}
                          className="flex items-center gap-1 px-2 py-1 bg-red-100 hover:bg-red-200 text-red-700 rounded text-xs"
                        >
                          <XCircle className="h-3 w-3" />
                          غير مطابق
                        </button>
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
            <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm disabled:opacity-50">السابق</button>
            <span className="text-sm text-gray-600">صفحة {page} من {totalPages}</span>
            <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages} className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm disabled:opacity-50">التالي</button>
          </div>
        )}
      </div>
    </Shell>
  );
}
