"use client";

/**
 * Every import on the platform — uploaded files and API syncs alike.
 *
 * This is the view that answers "is the customer actually getting their stock
 * in?", so a failed or partly failed job is what the page makes easy to find.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useLocale } from "next-intl";
import { FileSpreadsheet, Plug, Upload } from "lucide-react";

import Shell from "@/components/layout/shell";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { EmptyState } from "@/components/ui/empty-state";
import { adminApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";

type ImportRow = {
  id: string;
  organization_name: string;
  created_by_name?: string | null;
  filename: string;
  source: string;
  status: string;
  total_rows: number;
  processed_rows: number;
  created_batches: number;
  updated_batches: number;
  created_products: number;
  failed_rows: number;
  failure_reason?: string | null;
  finished_at?: string | null;
  created_at: string;
};

const STATUS_LABEL: Record<string, string> = {
  queued: "في الانتظار",
  processing: "قيد المعالجة",
  completed: "اكتمل",
  completed_with_errors: "اكتمل مع أخطاء",
  failed: "فشل",
};

const STATUS_STYLE: Record<string, string> = {
  queued: "bg-slate-100 text-slate-700 ring-slate-200",
  processing: "bg-blue-50 text-blue-700 ring-blue-200",
  completed: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  completed_with_errors: "bg-amber-50 text-amber-800 ring-amber-200",
  failed: "bg-red-50 text-red-700 ring-red-200",
};

const FILTERS = [
  { value: "", label: "كل الحالات" },
  { value: "completed", label: "مكتملة" },
  { value: "completed_with_errors", label: "بأخطاء" },
  { value: "failed", label: "فاشلة" },
  { value: "queued", label: "في الانتظار" },
  { value: "processing", label: "قيد المعالجة" },
];

const PAGE_SIZE = 25;

export default function AdminImportsPage() {
  const locale = useLocale();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["admin-imports", page, status],
    queryFn: () =>
      adminApi
        .allImports({
          page,
          page_size: PAGE_SIZE,
          status_filter: status || undefined,
        })
        .then((r) => r.data),
    // Some rows are still running; keep the list honest without hammering it.
    refetchInterval: 15000,
  });

  const rows: ImportRow[] = data?.items ?? [];
  const pages = data?.pages ?? 0;

  return (
    <Shell>
      <div className="space-y-6">
        <PageHeader
          title="عمليات الاستيراد"
          subtitle="كل ما رفعته المنشآت أو أرسلته أنظمتها عبر الواجهة البرمجية"
        />

        <SectionCard
          noPadding
          title="السجل"
          subtitle={
            data ? `${data.total.toLocaleString("ar-SA")} عملية` : undefined
          }
          action={
            <select
              value={status}
              onChange={(event) => {
                setStatus(event.target.value);
                setPage(1);
              }}
              className="h-9 px-3 rounded-full bg-white ring-1 ring-inset ring-[#e1d3c0] text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              {FILTERS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          }
        >
          {isLoading ? (
            <p className="px-6 py-10 text-sm text-[#8a9089]">جار التحميل…</p>
          ) : rows.length === 0 ? (
            <EmptyState
              icon={Upload}
              title="لا توجد عمليات استيراد"
              description="ستظهر هنا فور رفع أي منشأة لملف أو إرسالها دفعة عبر الواجهة."
            />
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-[#fdfbf7] text-[#8a9089]">
                    <tr>
                      <th className="text-right font-medium px-5 py-2.5">المنشأة</th>
                      <th className="text-right font-medium px-3 py-2.5">المصدر</th>
                      <th className="text-right font-medium px-3 py-2.5">الصفوف</th>
                      <th className="text-right font-medium px-3 py-2.5">النتيجة</th>
                      <th className="text-right font-medium px-3 py-2.5">الحالة</th>
                      <th className="text-right font-medium px-3 py-2.5">التاريخ</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#eadfcc]">
                    {rows.map((row) => (
                      <tr key={row.id} className="hover:bg-[#fdfbf7] align-top">
                        <td className="px-5 py-3">
                          <div className="font-medium text-[#1f2a24]">
                            {row.organization_name}
                          </div>
                          {row.created_by_name && (
                            <div className="text-xs text-[#8a9089]">
                              {row.created_by_name}
                            </div>
                          )}
                        </td>
                        <td className="px-3 py-3">
                          <div className="flex items-center gap-1.5 text-[#5f665f]">
                            {row.source === "api" ? (
                              <Plug className="h-3.5 w-3.5 text-[#a8927a]" />
                            ) : (
                              <FileSpreadsheet className="h-3.5 w-3.5 text-[#a8927a]" />
                            )}
                            <span className="truncate max-w-[13rem] text-xs">
                              {row.filename}
                            </span>
                          </div>
                        </td>
                        <td className="px-3 py-3 tabular-nums text-[#5f665f] whitespace-nowrap">
                          {row.processed_rows.toLocaleString("ar-SA")}
                          {row.total_rows > 0 && (
                            <span className="text-xs text-[#8a9089]">
                              {" "}
                              / {row.total_rows.toLocaleString("ar-SA")}
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-3 whitespace-nowrap tabular-nums">
                          <span className="text-emerald-700">
                            +{row.created_batches.toLocaleString("ar-SA")}
                          </span>
                          {row.updated_batches > 0 && (
                            <span className="text-blue-700">
                              {" "}
                              ~{row.updated_batches.toLocaleString("ar-SA")}
                            </span>
                          )}
                          {row.failed_rows > 0 && (
                            <span className="text-red-700">
                              {" "}
                              ✕{row.failed_rows.toLocaleString("ar-SA")}
                            </span>
                          )}
                          {row.created_products > 0 && (
                            <div className="text-xs text-[#8a9089]">
                              {row.created_products.toLocaleString("ar-SA")} مسودة
                            </div>
                          )}
                        </td>
                        <td className="px-3 py-3">
                          <span
                            className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium ring-1 ring-inset ${
                              STATUS_STYLE[row.status] ?? STATUS_STYLE.queued
                            }`}
                          >
                            {STATUS_LABEL[row.status] ?? row.status}
                          </span>
                          {row.failure_reason && (
                            <div className="text-xs text-red-700 mt-1 max-w-[16rem]">
                              {row.failure_reason}
                            </div>
                          )}
                        </td>
                        <td className="px-3 py-3 text-xs text-[#8a9089] whitespace-nowrap">
                          {formatDate(row.created_at, locale)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {pages > 1 && (
                <div className="flex items-center justify-between px-5 py-3 border-t border-[#eadfcc]">
                  <button
                    type="button"
                    onClick={() => setPage((current) => Math.max(1, current - 1))}
                    disabled={page === 1}
                    className="h-8 px-4 rounded-full text-sm ring-1 ring-inset ring-[#e1d3c0] text-[#5f665f] disabled:opacity-40 hover:bg-[#fbf7f0]"
                  >
                    السابق
                  </button>
                  <span className="text-xs text-[#8a9089]">
                    صفحة {page.toLocaleString("ar-SA")} من{" "}
                    {pages.toLocaleString("ar-SA")}
                  </span>
                  <button
                    type="button"
                    onClick={() => setPage((current) => Math.min(pages, current + 1))}
                    disabled={page >= pages}
                    className="h-8 px-4 rounded-full text-sm ring-1 ring-inset ring-[#e1d3c0] text-[#5f665f] disabled:opacity-40 hover:bg-[#fbf7f0]"
                  >
                    التالي
                  </button>
                </div>
              )}
            </>
          )}
        </SectionCard>
      </div>
    </Shell>
  );
}
