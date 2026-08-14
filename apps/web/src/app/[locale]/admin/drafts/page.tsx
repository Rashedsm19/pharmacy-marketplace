"use client";

/**
 * The draft queue.
 *
 * An import creates a private product for every medicine it cannot match, which
 * is what keeps a first import from stalling. This is where those become part of
 * the catalogue every pharmacy shares — the batches already pointing at the
 * product keep pointing at it, so nobody's stock moves.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocale } from "next-intl";
import { toast } from "sonner";
import { CheckCheck, FileStack, Loader2, Pencil } from "lucide-react";

import Shell from "@/components/layout/shell";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { EmptyState } from "@/components/ui/empty-state";
import { errorMessage } from "@/lib/errors";
import { adminApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";

type Draft = {
  id: string;
  organization_name?: string | null;
  name: string;
  name_ar?: string | null;
  sku: string;
  barcode?: string | null;
  category_name?: string | null;
  source: string;
  batch_count: number;
  created_at: string;
};

const PAGE_SIZE = 25;

export default function AdminDraftsPage() {
  const locale = useLocale();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<string | null>(null);
  const [form, setForm] = useState({ name_ar: "", sku: "", barcode: "" });

  const { data, isLoading } = useQuery({
    queryKey: ["admin-drafts", page],
    queryFn: () =>
      adminApi.draftProducts({ page, page_size: PAGE_SIZE }).then((r) => r.data),
  });

  const promote = useMutation({
    mutationFn: ({
      id,
      corrections,
    }: {
      id: string;
      corrections?: { name_ar?: string; sku?: string; barcode?: string };
    }) => adminApi.promoteDraft(id, corrections),
    onSuccess: () => {
      toast.success("أضيف المنتج إلى الكتالوج العام");
      queryClient.invalidateQueries({ queryKey: ["admin-drafts"] });
      setEditing(null);
    },
    onError: (error: unknown) => {
      toast.error(
        errorMessage(error, "تعذر ضم المنتج")
      );
    },
  });

  const drafts: Draft[] = data?.items ?? [];
  const pages = data?.pages ?? 0;

  const startEditing = (draft: Draft) => {
    setEditing(draft.id);
    setForm({
      name_ar: draft.name_ar ?? draft.name,
      sku: draft.sku,
      barcode: draft.barcode ?? "",
    });
  };

  return (
    <Shell>
      <div className="space-y-6">
        <PageHeader
          title="مسودات المنتجات"
          subtitle="أدوية أنشأتها عمليات الاستيراد ولم تطابق بالكتالوج — راجعها وضمها"
        />

        <div className="rounded-2xl bg-[#f4eadf] px-5 py-4">
          <p className="text-sm text-[#7b5411] leading-relaxed">
            المسودة منتج <strong>خاص بالمنشأة</strong> التي استوردته: تعمل به فورا،
            ولا تراه المنشآت الأخرى. ضمه للكتالوج العام يجعله متاحا للجميع، ومخزون
            المنشأة يبقى مرتبطا به كما هو.
          </p>
        </div>

        <SectionCard
          noPadding
          title="الطابور"
          subtitle={
            data ? `${data.total.toLocaleString("ar-SA")} مسودة` : undefined
          }
        >
          {isLoading ? (
            <p className="px-6 py-10 text-sm text-[#8a9089]">جار التحميل…</p>
          ) : drafts.length === 0 ? (
            <EmptyState
              icon={CheckCheck}
              title="لا توجد مسودات"
              description="كل ما استورد حتى الآن طابق الكتالوج العام."
            />
          ) : (
            <>
              <ul className="divide-y divide-[#eadfcc]">
                {drafts.map((draft) => (
                  <li key={draft.id} className="px-5 sm:px-6 py-4">
                    {editing === draft.id ? (
                      <form
                        onSubmit={(event) => {
                          event.preventDefault();
                          promote.mutate({
                            id: draft.id,
                            corrections: {
                              name_ar: form.name_ar.trim() || undefined,
                              sku: form.sku.trim() || undefined,
                              barcode: form.barcode.trim() || undefined,
                            },
                          });
                        }}
                        className="space-y-3"
                      >
                        <div className="grid gap-3 sm:grid-cols-3">
                          <label className="block">
                            <span className="block text-xs font-medium text-[#5f665f] mb-1">
                              الاسم العربي
                            </span>
                            <input
                              value={form.name_ar}
                              onChange={(event) =>
                                setForm((f) => ({ ...f, name_ar: event.target.value }))
                              }
                              className="w-full h-10 px-3 rounded-xl bg-white ring-1 ring-inset ring-[#e1d3c0] text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                            />
                          </label>
                          <label className="block">
                            <span className="block text-xs font-medium text-[#5f665f] mb-1">
                              كود الكتالوج
                            </span>
                            <input
                              dir="ltr"
                              value={form.sku}
                              onChange={(event) =>
                                setForm((f) => ({ ...f, sku: event.target.value }))
                              }
                              className="w-full h-10 px-3 rounded-xl bg-white ring-1 ring-inset ring-[#e1d3c0] text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500"
                            />
                          </label>
                          <label className="block">
                            <span className="block text-xs font-medium text-[#5f665f] mb-1">
                              الباركود
                            </span>
                            <input
                              dir="ltr"
                              value={form.barcode}
                              onChange={(event) =>
                                setForm((f) => ({ ...f, barcode: event.target.value }))
                              }
                              placeholder="اختياري"
                              className="w-full h-10 px-3 rounded-xl bg-white ring-1 ring-inset ring-[#e1d3c0] text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500"
                            />
                          </label>
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            type="submit"
                            disabled={promote.isPending}
                            className="inline-flex items-center gap-2 h-9 px-4 rounded-full bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 disabled:opacity-60"
                          >
                            {promote.isPending && (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            )}
                            ضم بعد التعديل
                          </button>
                          <button
                            type="button"
                            onClick={() => setEditing(null)}
                            className="h-9 px-4 rounded-full text-sm text-[#5f665f] hover:bg-[#fbf7f0]"
                          >
                            إلغاء
                          </button>
                        </div>
                      </form>
                    ) : (
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="font-medium text-[#1f2a24]">
                            {draft.name_ar || draft.name}
                          </div>
                          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1 text-xs text-[#8a9089]">
                            <code dir="ltr" className="font-mono">
                              {draft.sku}
                            </code>
                            {draft.barcode && (
                              <code dir="ltr" className="font-mono">
                                باركود {draft.barcode}
                              </code>
                            )}
                            {draft.category_name && <span>{draft.category_name}</span>}
                            <span>
                              {draft.source === "api"
                                ? "عبر الواجهة البرمجية"
                                : "من ملف مرفوع"}
                            </span>
                          </div>
                          <div className="mt-2 flex flex-wrap items-center gap-2">
                            {draft.organization_name && (
                              <span className="px-2 py-0.5 rounded-md text-xs bg-[#f4eadf] text-[#7b5411]">
                                {draft.organization_name}
                              </span>
                            )}
                            <span className="text-xs text-[#8a9089]">
                              {draft.batch_count.toLocaleString("ar-SA")} تشغيلة مرتبطة
                              · {formatDate(draft.created_at, locale)}
                            </span>
                          </div>
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          <button
                            type="button"
                            onClick={() => startEditing(draft)}
                            className="inline-flex items-center gap-1.5 h-9 px-4 rounded-full text-sm ring-1 ring-inset ring-[#e1d3c0] text-[#5f665f] hover:bg-[#fbf7f0]"
                          >
                            <Pencil className="h-3.5 w-3.5" />
                            تعديل ثم ضم
                          </button>
                          <button
                            type="button"
                            onClick={() => promote.mutate({ id: draft.id })}
                            disabled={promote.isPending}
                            className="inline-flex items-center gap-1.5 h-9 px-4 rounded-full bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 disabled:opacity-60"
                          >
                            {promote.isPending && promote.variables?.id === draft.id ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <CheckCheck className="h-3.5 w-3.5" />
                            )}
                            ضم للكتالوج
                          </button>
                        </div>
                      </div>
                    )}
                  </li>
                ))}
              </ul>

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

        <p className="text-xs text-[#8a9089] flex items-center gap-1.5">
          <FileStack className="h-3.5 w-3.5" />
          إن كان الكود مستخدما في الكتالوج العام، استخدم «تعديل ثم ضم» وأدخل كودا
          آخر.
        </p>
      </div>
    </Shell>
  );
}
