"use client";

/**
 * Bringing a whole inventory in from a spreadsheet.
 *
 * The page is built around the fact that the work happens on the server: the
 * upload returns a job, and this polls it. While a job is running the customer
 * sees rows counted rather than a spinner, because a ten thousand row file takes
 * long enough that a spinner reads as a hang.
 */

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useLocale } from "next-intl";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Download,
  FileSpreadsheet,
  KeyRound,
  Loader2,
  Upload,
  XCircle,
} from "lucide-react";

import Shell from "@/components/layout/shell";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { EmptyState } from "@/components/ui/empty-state";
import { importsApi } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { formatDate } from "@/lib/utils";

type ImportJob = {
  id: string;
  filename: string;
  source: string;
  status:
    | "queued"
    | "processing"
    | "completed"
    | "completed_with_errors"
    | "failed";
  total_rows: number;
  processed_rows: number;
  created_batches: number;
  updated_batches: number;
  created_products: number;
  matched_products: number;
  failed_rows: number;
  errors?: { line: number; reason: string; product_name?: string | null }[] | null;
  failure_reason?: string | null;
  has_error_file: boolean;
  created_at: string;
  finished_at?: string | null;
};

const RUNNING = new Set(["queued", "processing"]);

const STATUS_LABEL: Record<ImportJob["status"], string> = {
  queued: "في الانتظار",
  processing: "قيد المعالجة",
  completed: "اكتمل",
  completed_with_errors: "اكتمل مع أخطاء",
  failed: "فشل",
};

const STATUS_STYLE: Record<ImportJob["status"], string> = {
  queued: "bg-slate-100 text-slate-700 ring-slate-200",
  processing: "bg-blue-50 text-blue-700 ring-blue-200",
  completed: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  completed_with_errors: "bg-amber-50 text-amber-800 ring-amber-200",
  failed: "bg-red-50 text-red-700 ring-red-200",
};

function saveBlob(data: Blob, filename: string) {
  const url = window.URL.createObjectURL(data);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export default function InventoryImportPage() {
  const locale = useLocale();
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);

  const [dragging, setDragging] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(
    null
  );

  const { data: capacity } = useQuery({
    queryKey: ["import-capacity"],
    queryFn: () => importsApi.capacity().then((r) => r.data),
  });

  const { data: history } = useQuery<{ items: ImportJob[]; total: number }>({
    queryKey: ["import-jobs"],
    queryFn: () => importsApi.list({ page_size: 10 }).then((r) => r.data),
  });

  // Only the running job is polled, and only while it runs.
  const { data: activeJob } = useQuery<ImportJob>({
    queryKey: ["import-job", activeJobId],
    queryFn: () => importsApi.get(activeJobId as string).then((r) => r.data),
    enabled: Boolean(activeJobId),
    refetchInterval: (query) =>
      !query.state.data || RUNNING.has(query.state.data.status) ? 2000 : false,
    // A ten thousand row file takes minutes; people switch tabs while they
    // wait, and the progress must still be current when they come back.
    refetchIntervalInBackground: true,
  });

  useEffect(() => {
    if (activeJob && !RUNNING.has(activeJob.status)) {
      queryClient.invalidateQueries({ queryKey: ["import-jobs"] });
      queryClient.invalidateQueries({ queryKey: ["import-capacity"] });
    }
  }, [activeJob?.status, activeJob, queryClient]);

  const uploadMutation = useMutation({
    mutationFn: (file: File) => importsApi.upload(file).then((r) => r.data),
    onSuccess: (job: ImportJob) => {
      setActiveJobId(job.id);
      setMessage({
        kind: "ok",
        text: "تم رفع الملف — جاري المعالجة، ويمكنك متابعة التقدم أدناه.",
      });
      queryClient.invalidateQueries({ queryKey: ["import-jobs"] });
    },
    onError: (error: unknown) => {
      const detail =
        errorMessage(error, "تعذر رفع الملف. حاول مرة أخرى.");
      setMessage({ kind: "error", text: detail });
    },
  });

  const templateMutation = useMutation({
    mutationFn: () => importsApi.downloadTemplate().then((r) => r.data),
    onSuccess: (data: Blob) => saveBlob(data, "نموذج-مخزون-MedSave.xlsx"),
    onError: async (error: unknown) => {
      // The server's reason is far more useful than "try again", but an error
      // on a blob request arrives as a Blob, so it has to be read back.
      const body = (error as { response?: { data?: unknown } })?.response?.data;
      let detail: string | undefined;
      try {
        if (body instanceof Blob) {
          detail = JSON.parse(await body.text())?.detail;
        } else if (body && typeof body === "object") {
          detail = (body as { detail?: string }).detail;
        }
      } catch {
        /* fall through to the generic message */
      }
      setMessage({
        kind: "error",
        text: detail ?? "تعذر تحميل القالب. حاول مرة أخرى.",
      });
    },
  });

  const errorsMutation = useMutation({
    mutationFn: (id: string) => importsApi.downloadErrors(id).then((r) => r.data),
    onSuccess: (data: Blob) => saveBlob(data, "الصفوف-المرفوضة.xlsx"),
  });

  const handleFile = (file: File | undefined) => {
    if (!file) return;
    const name = file.name.toLowerCase();
    if (!name.endsWith(".xlsx") && !name.endsWith(".csv") && !name.endsWith(".xlsm")) {
      setMessage({
        kind: "error",
        text: "الملف يجب أن يكون بصيغة Excel أو CSV.",
      });
      return;
    }
    setMessage(null);
    uploadMutation.mutate(file);
  };

  const percent =
    activeJob && activeJob.total_rows > 0
      ? Math.min(
          100,
          Math.round((activeJob.processed_rows / activeJob.total_rows) * 100)
        )
      : null;

  return (
    <Shell>
      <div className="space-y-6">
        <PageHeader
          title="استيراد المخزون من ملف"
          subtitle="ارفع أصنافك دفعة واحدة، واعرف أيها يقترب من الانتهاء"
          actions={
            <Link
              href={`/${locale}/docs/integration`}
              className="inline-flex items-center gap-2 h-9 px-4 rounded-full text-sm font-medium ring-1 ring-inset ring-[#e1d3c0] text-[#5f665f] hover:bg-[#fbf7f0]"
            >
              <KeyRound className="h-4 w-4" />
              الربط بنظامك بدل الملف
            </Link>
          }
        />

        {message && (
          <div
            role="status"
            className={`rounded-2xl px-4 py-3 text-sm ring-1 ring-inset ${
              message.kind === "ok"
                ? "bg-emerald-50 text-emerald-800 ring-emerald-200"
                : "bg-red-50 text-red-800 ring-red-200"
            }`}
          >
            {message.text}
          </div>
        )}

        {/* ── The three steps, in order ───────────────────────────────── */}
        <div className="grid gap-4 lg:grid-cols-3">
          <SectionCard
            title="١ · تنزيل القالب"
            subtitle="أعمدة جاهزة، وفروعك مدرجة في قائمة منسدلة"
          >
            <p className="text-sm text-[#5f665f] leading-relaxed mb-4">
              القالب يحتوي على ورقتين: «البيانات» لتعبئة أصنافك، و«تعليمات» تشرح كل
              عمود. الحقول الإلزامية أربعة فقط: اسم الدواء، رقم التشغيلة، تاريخ
              الانتهاء، والكمية.
            </p>
            <button
              type="button"
              onClick={() => templateMutation.mutate()}
              disabled={templateMutation.isPending}
              className="inline-flex items-center gap-2 h-10 px-4 rounded-full bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 disabled:opacity-60"
            >
              {templateMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              تحميل القالب
            </button>
          </SectionCard>

          <SectionCard title="٢ · ادخال الاصناف" subtitle="من نظامك أو يدويا">
            <ul className="text-sm text-[#5f665f] space-y-2.5 leading-relaxed">
              <li className="flex gap-2">
                <span className="text-brand-600 font-semibold">•</span>
                <span>
                  أضف <strong className="text-[#1f2a24]">الباركود</strong> إن توفر —
                  فهو أدق وسيلة لمطابقة الدواء بكتالوجنا.
                </span>
              </li>
              <li className="flex gap-2">
                <span className="text-brand-600 font-semibold">•</span>
                <span>
                  تاريخ الانتهاء بصيغة{" "}
                  <code className="px-1.5 py-0.5 rounded bg-[#f4eadf] text-xs">
                    YYYY-MM-DD
                  </code>
                  .
                </span>
              </li>
              <li className="flex gap-2">
                <span className="text-brand-600 font-semibold">•</span>
                <span>
                  ما لا نتعرف عليه ينشأ كمنتج خاص بمنشأتك — لا يوقف الاستيراد.
                </span>
              </li>
            </ul>
          </SectionCard>

          <SectionCard title="٣ · ارفع الملف" subtitle="نعالجه ونخبرك بالنتيجة">
            <div
              onDragOver={(event) => {
                event.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(event) => {
                event.preventDefault();
                setDragging(false);
                handleFile(event.dataTransfer.files?.[0]);
              }}
              className={`rounded-2xl border-2 border-dashed p-6 text-center transition-colors ${
                dragging
                  ? "border-brand-500 bg-brand-50/50"
                  : "border-[#e1d3c0] bg-[#fdfbf7]"
              }`}
            >
              <FileSpreadsheet className="h-8 w-8 mx-auto text-[#a8927a] mb-2" />
              <p className="text-sm text-[#5f665f] mb-3">
                اسحب الملف هنا أو اختره من جهازك
              </p>
              <input
                ref={inputRef}
                type="file"
                accept=".xlsx,.xlsm,.csv"
                className="hidden"
                onChange={(event) => {
                  handleFile(event.target.files?.[0]);
                  event.target.value = "";
                }}
              />
              <button
                type="button"
                onClick={() => inputRef.current?.click()}
                disabled={uploadMutation.isPending}
                className="inline-flex items-center gap-2 h-10 px-4 rounded-full bg-[#1f2a24] text-white text-sm font-medium hover:bg-[#2c3a32] disabled:opacity-60"
              >
                {uploadMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Upload className="h-4 w-4" />
                )}
                اختيار ملف
              </button>
              <p className="text-xs text-[#8a9089] mt-3">
                Excel أو CSV · حتى ٢٥ ميجابايت
              </p>
            </div>
          </SectionCard>
        </div>

        {/* ── The running job ─────────────────────────────────────────── */}
        {activeJob && (
          <SectionCard
            title="العملية الحالية"
            subtitle={activeJob.filename}
            action={
              <span
                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium ring-1 ring-inset ${
                  STATUS_STYLE[activeJob.status]
                }`}
              >
                {RUNNING.has(activeJob.status) ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : activeJob.status === "completed" ? (
                  <CheckCircle2 className="h-3.5 w-3.5" />
                ) : activeJob.status === "failed" ? (
                  <XCircle className="h-3.5 w-3.5" />
                ) : (
                  <AlertTriangle className="h-3.5 w-3.5" />
                )}
                {STATUS_LABEL[activeJob.status]}
              </span>
            }
          >
            {RUNNING.has(activeJob.status) && (
              <div className="mb-5">
                <div className="flex justify-between text-xs text-[#5f665f] mb-1.5">
                  <span>
                    {activeJob.processed_rows.toLocaleString("ar-SA")} صف تمت معالجته
                  </span>
                  {percent !== null && <span>{percent}%</span>}
                </div>
                <div className="h-2 rounded-full bg-[#f0e6d8] overflow-hidden">
                  <div
                    className="h-full bg-brand-600 transition-all duration-500"
                    style={{ width: percent !== null ? `${percent}%` : "35%" }}
                  />
                </div>
              </div>
            )}

            <dl className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                ["تشغيلات جديدة", activeJob.created_batches, "text-emerald-700"],
                ["تشغيلات محدثة", activeJob.updated_batches, "text-blue-700"],
                ["أدوية مطابقة", activeJob.matched_products, "text-[#1f2a24]"],
                ["صفوف مرفوضة", activeJob.failed_rows, "text-red-700"],
              ].map(([label, value, tone]) => (
                <div
                  key={label as string}
                  className="rounded-xl bg-[#fdfbf7] ring-1 ring-[#eadfcc] px-3 py-2.5"
                >
                  <dt className="text-xs text-[#8a9089]">{label as string}</dt>
                  <dd className={`text-lg font-semibold ${tone as string}`}>
                    {(value as number).toLocaleString("ar-SA")}
                  </dd>
                </div>
              ))}
            </dl>

            {activeJob.failure_reason && (
              <p className="mt-4 text-sm text-amber-800 bg-amber-50 ring-1 ring-inset ring-amber-200 rounded-xl px-4 py-3">
                {activeJob.failure_reason}
              </p>
            )}

            {activeJob.errors && activeJob.errors.length > 0 && (
              <div className="mt-5">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-semibold text-[#1f2a24]">
                    صفوف تحتاج تصحيحا
                  </h3>
                  {activeJob.has_error_file && (
                    <button
                      type="button"
                      onClick={() => errorsMutation.mutate(activeJob.id)}
                      className="inline-flex items-center gap-1.5 text-xs font-medium text-brand-700 hover:text-brand-800"
                    >
                      <Download className="h-3.5 w-3.5" />
                      تنزيل الصفوف المرفوضة
                    </button>
                  )}
                </div>
                <ul className="divide-y divide-[#eadfcc] rounded-xl ring-1 ring-[#eadfcc] overflow-hidden">
                  {activeJob.errors.slice(0, 8).map((error) => (
                    <li
                      key={`${error.line}-${error.reason}`}
                      className="flex items-start gap-3 px-4 py-2.5 bg-white text-sm"
                    >
                      <span className="shrink-0 mt-0.5 px-2 py-0.5 rounded-md bg-[#f4eadf] text-xs text-[#7b5411] font-medium">
                        سطر {error.line}
                      </span>
                      <span className="text-[#5f665f]">
                        {error.product_name ? `${error.product_name} — ` : ""}
                        {error.reason}
                      </span>
                    </li>
                  ))}
                </ul>
                {activeJob.errors.length > 8 && (
                  <p className="text-xs text-[#8a9089] mt-2">
                    وهناك {(activeJob.failed_rows - 8).toLocaleString("ar-SA")} صفا
                    آخر في الملف المرفوض.
                  </p>
                )}
              </div>
            )}
          </SectionCard>
        )}

        {/* ── Capacity and history ────────────────────────────────────── */}
        <div className="grid gap-4 lg:grid-cols-3">
          <SectionCard title="سعة المخزون">
            {capacity ? (
              <>
                <div className="flex items-baseline gap-2 mb-3">
                  <span className="text-3xl font-semibold text-[#1f2a24] tabular-nums">
                    {capacity.used.toLocaleString("ar-SA")}
                  </span>
                  <span className="text-sm text-[#8a9089]">
                    من {capacity.limit.toLocaleString("ar-SA")} صنف
                  </span>
                </div>
                <div className="h-2 rounded-full bg-[#f0e6d8] overflow-hidden">
                  <div
                    className={`h-full transition-all ${
                      capacity.remaining === 0 ? "bg-red-500" : "bg-brand-600"
                    }`}
                    style={{
                      width: `${Math.min(
                        100,
                        (capacity.used / capacity.limit) * 100
                      )}%`,
                    }}
                  />
                </div>
                <p className="text-xs text-[#8a9089] mt-2">
                  يمكنك إضافة {capacity.remaining.toLocaleString("ar-SA")} صنف آخر.
                </p>
              </>
            ) : (
              <p className="text-sm text-[#8a9089]">جاري الحساب…</p>
            )}
          </SectionCard>

          <SectionCard
            className="lg:col-span-2"
            title="عمليات الاستيراد السابقة"
            subtitle="آخر عشر عمليات"
            noPadding
          >
            {history?.items?.length ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-[#fdfbf7] text-[#8a9089]">
                    <tr>
                      <th className="text-right font-medium px-5 py-2.5">الملف</th>
                      <th className="text-right font-medium px-3 py-2.5">التاريخ</th>
                      <th className="text-right font-medium px-3 py-2.5">النتيجة</th>
                      <th className="text-right font-medium px-3 py-2.5">الحالة</th>
                      <th className="px-3 py-2.5" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#eadfcc]">
                    {history.items.map((job) => (
                      <tr key={job.id} className="hover:bg-[#fdfbf7]">
                        <td className="px-5 py-3">
                          <button
                            type="button"
                            onClick={() => setActiveJobId(job.id)}
                            className="font-medium text-[#1f2a24] hover:text-brand-700 truncate max-w-[16rem] text-right"
                          >
                            {job.filename}
                          </button>
                          <div className="text-xs text-[#8a9089]">
                            {job.source === "api" ? "عبر الواجهة البرمجية" : "ملف مرفوع"}
                          </div>
                        </td>
                        <td className="px-3 py-3 text-[#5f665f] whitespace-nowrap">
                          {formatDate(job.created_at, locale)}
                        </td>
                        <td className="px-3 py-3 text-[#5f665f] whitespace-nowrap">
                          <span className="text-emerald-700">
                            +{job.created_batches.toLocaleString("ar-SA")}
                          </span>
                          {job.updated_batches > 0 && (
                            <span className="text-blue-700">
                              {" "}
                              ~{job.updated_batches.toLocaleString("ar-SA")}
                            </span>
                          )}
                          {job.failed_rows > 0 && (
                            <span className="text-red-700">
                              {" "}
                              ✕{job.failed_rows.toLocaleString("ar-SA")}
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-3">
                          <span
                            className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium ring-1 ring-inset ${
                              STATUS_STYLE[job.status]
                            }`}
                          >
                            {STATUS_LABEL[job.status]}
                          </span>
                        </td>
                        <td className="px-3 py-3 text-left">
                          {job.has_error_file && (
                            <button
                              type="button"
                              onClick={() => errorsMutation.mutate(job.id)}
                              className="text-xs text-brand-700 hover:text-brand-800 whitespace-nowrap"
                            >
                              الصفوف المرفوضة
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState
                icon={Clock}
                title="لم تستورد أي ملف بعد"
                description="حمل القالب، وادخل اصنافك، ثم ارفعه — وستظهر العملية هنا."
              />
            )}
          </SectionCard>
        </div>
      </div>
    </Shell>
  );
}
