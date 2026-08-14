"use client";

/**
 * Platform settings.
 *
 * These change how the marketplace behaves for everyone, so the screen's job is
 * to make each one understandable before it is edited: what it means, in which
 * unit, and within what range. The server supplies all of that — the screen
 * only renders it, in both Arabic and English.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocale } from "next-intl";
import { toast } from "sonner";
import { Loader2, Save, SlidersHorizontal } from "lucide-react";

import Shell from "@/components/layout/shell";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { errorMessage } from "@/lib/errors";
import { adminApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";

type Setting = {
  id: string;
  key: string;
  value: string | number | boolean | null;
  label_ar: string;
  label_en: string;
  description_ar: string;
  description_en: string;
  value_type: "number" | "percent" | "boolean" | "text";
  group_ar: string;
  group_en: string;
  unit_ar?: string | null;
  minimum?: number | null;
  maximum?: number | null;
  updated_at: string;
};

export default function AdminSettingsPage() {
  const locale = useLocale();
  const isArabic = locale.startsWith("ar");
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  const { data, isLoading } = useQuery<Setting[]>({
    queryKey: ["admin-settings"],
    queryFn: () => adminApi.getSettings().then((r) => r.data),
  });

  const save = useMutation({
    mutationFn: ({ key, value }: { key: string; value: unknown }) =>
      adminApi.updateSetting(key, value),
    onSuccess: () => {
      toast.success("تم حفظ الإعداد");
      queryClient.invalidateQueries({ queryKey: ["admin-settings"] });
      setEditing(null);
    },
    onError: (error: unknown) => {
      toast.error(
        errorMessage(error, "تعذر حفظ الإعداد")
      );
    },
  });

  const settings = data ?? [];

  // Grouping comes from the server, so a setting added later lands in the right
  // place without touching this screen.
  const groups = settings.reduce<Record<string, Setting[]>>((acc, setting) => {
    const name = isArabic ? setting.group_ar : setting.group_en;
    (acc[name] ??= []).push(setting);
    return acc;
  }, {});

  const display = (setting: Setting) => {
    if (setting.value_type === "boolean") {
      return setting.value ? "مفعل" : "معطل";
    }
    if (setting.value === null || setting.value === undefined) return "—";
    const number = Number(setting.value);
    const text = Number.isFinite(number)
      ? number.toLocaleString("ar-SA")
      : String(setting.value);
    return setting.unit_ar ? `${text} ${setting.unit_ar}` : text;
  };

  const beginEdit = (setting: Setting) => {
    setEditing(setting.key);
    setDraft(String(setting.value ?? ""));
  };

  const commit = (setting: Setting) => {
    const value =
      setting.value_type === "boolean"
        ? draft === "true"
        : setting.value_type === "text"
        ? draft
        : Number(draft);

    if (setting.value_type !== "boolean" && setting.value_type !== "text") {
      if (!Number.isFinite(value as number)) {
        toast.error("القيمة يجب أن تكون رقما");
        return;
      }
    }
    save.mutate({ key: setting.key, value });
  };

  return (
    <Shell>
      <div className="max-w-4xl space-y-6">
        <PageHeader
          title="إعدادات المنصة"
          subtitle="قواعد تسري على جميع المنشآت — راجعها قبل التعديل"
        />

        {isLoading ? (
          <p className="text-sm text-[#8a9089]">جار التحميل…</p>
        ) : (
          Object.entries(groups).map(([group, items]) => (
            <SectionCard key={group} title={group} noPadding>
              <ul className="divide-y divide-[#eadfcc]">
                {items.map((setting) => (
                  <li key={setting.key} className="px-5 sm:px-6 py-4">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        <div className="font-medium text-[#1f2a24]">
                          {setting.label_ar}
                        </div>
                        {/* The English name matters: an integrator reads the
                            API and a Saudi admin reads Arabic. */}
                        <div className="text-xs text-[#8a9089] mt-0.5">
                          {setting.label_en}
                        </div>
                        <p className="text-sm text-[#5f665f] leading-relaxed mt-2 max-w-xl">
                          {setting.description_ar}
                        </p>
                        <code
                          dir="ltr"
                          className="inline-block text-[11px] font-mono text-[#a8927a] mt-2"
                        >
                          {setting.key}
                        </code>
                      </div>

                      <div className="shrink-0 text-left min-w-[13rem]">
                        {editing === setting.key ? (
                          <div className="space-y-2">
                            {setting.value_type === "boolean" ? (
                              <select
                                value={draft}
                                onChange={(event) => setDraft(event.target.value)}
                                className="w-full h-10 px-3 rounded-xl bg-white ring-1 ring-inset ring-[#e1d3c0] text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                              >
                                <option value="true">مفعل</option>
                                <option value="false">معطل</option>
                              </select>
                            ) : (
                              <div className="flex items-center gap-2">
                                <input
                                  dir="ltr"
                                  type={setting.value_type === "text" ? "text" : "number"}
                                  value={draft}
                                  min={setting.minimum ?? undefined}
                                  max={setting.maximum ?? undefined}
                                  onChange={(event) => setDraft(event.target.value)}
                                  className="w-full h-10 px-3 rounded-xl bg-white ring-1 ring-inset ring-[#e1d3c0] text-sm text-right focus:outline-none focus:ring-2 focus:ring-brand-500"
                                />
                                {setting.unit_ar && (
                                  <span className="text-sm text-[#8a9089] shrink-0">
                                    {setting.unit_ar}
                                  </span>
                                )}
                              </div>
                            )}

                            {(setting.minimum != null || setting.maximum != null) && (
                              <p className="text-xs text-[#8a9089]">
                                المدى المسموح: {setting.minimum ?? "—"} إلى{" "}
                                {setting.maximum ?? "—"}
                              </p>
                            )}

                            <div className="flex items-center gap-2 justify-end">
                              <button
                                type="button"
                                onClick={() => commit(setting)}
                                disabled={save.isPending}
                                className="inline-flex items-center gap-1.5 h-9 px-4 rounded-full bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 disabled:opacity-60"
                              >
                                {save.isPending ? (
                                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                ) : (
                                  <Save className="h-3.5 w-3.5" />
                                )}
                                حفظ
                              </button>
                              <button
                                type="button"
                                onClick={() => setEditing(null)}
                                className="h-9 px-4 rounded-full text-sm text-[#5f665f] hover:bg-[#fbf7f0]"
                              >
                                إلغاء
                              </button>
                            </div>
                          </div>
                        ) : (
                          <>
                            <div className="text-2xl font-semibold text-[#1f2a24] tabular-nums">
                              {display(setting)}
                            </div>
                            <div className="text-xs text-[#8a9089] mt-0.5">
                              آخر تحديث {formatDate(setting.updated_at, locale)}
                            </div>
                            <button
                              type="button"
                              onClick={() => beginEdit(setting)}
                              className="inline-flex items-center gap-1.5 mt-2 h-8 px-4 rounded-full text-sm ring-1 ring-inset ring-[#e1d3c0] text-[#5f665f] hover:bg-[#fbf7f0]"
                            >
                              <SlidersHorizontal className="h-3.5 w-3.5" />
                              تعديل
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </SectionCard>
          ))
        )}
      </div>
    </Shell>
  );
}
