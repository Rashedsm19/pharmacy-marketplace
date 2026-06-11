"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import Shell from "@/components/layout/shell";
import { adminApi } from "@/lib/api";
import { Loader2, Settings, Save } from "lucide-react";

type SettingValue = string | number | boolean;

interface PlatformSetting {
  key: string;
  value: SettingValue;
  description?: string;
  value_type: "string" | "number" | "boolean";
}

export default function AdminSettingsPage() {
  const qc = useQueryClient();
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<string>("");

  const { data: settings, isLoading } = useQuery({
    queryKey: ["admin-settings"],
    queryFn: () => adminApi.getSettings().then((r) => r.data),
  });

  const updateSetting = useMutation({
    mutationFn: ({ key, value }: { key: string; value: SettingValue }) =>
      adminApi.updateSetting(key, value),
    onSuccess: () => {
      toast.success("تم حفظ الإعداد");
      qc.invalidateQueries({ queryKey: ["admin-settings"] });
      setEditingKey(null);
    },
    onError: () => toast.error("فشل حفظ الإعداد"),
  });

  const settingsList: PlatformSetting[] = Array.isArray(settings) ? settings : [];

  const startEdit = (setting: PlatformSetting) => {
    setEditingKey(setting.key);
    setEditValue(String(setting.value));
  };

  const saveEdit = (setting: PlatformSetting) => {
    let value: SettingValue = editValue;
    if (setting.value_type === "number") value = Number(editValue);
    if (setting.value_type === "boolean") value = editValue === "true";
    updateSetting.mutate({ key: setting.key, value });
  };

  const SETTING_GROUPS: Record<string, string[]> = {
    "قواعد الإدراج": [
      "min_days_before_listing",
      "max_listing_duration_days",
      "min_listing_price",
    ],
    "العروض والحجز": [
      "offer_expiry_hours",
      "reservation_expiry_hours",
      "max_offers_per_listing",
    ],
    "إشعارات الصلاحية": [
      "expiry_alert_day_threshold_1",
      "expiry_alert_day_threshold_2",
      "expiry_alert_day_threshold_3",
    ],
    "عام": [],
  };

  const groupedSettings = (key: string) => {
    for (const [group, keys] of Object.entries(SETTING_GROUPS)) {
      if (keys.includes(key)) return group;
    }
    return "عام";
  };

  const groups: Record<string, PlatformSetting[]> = {};
  settingsList.forEach((s) => {
    const g = groupedSettings(s.key);
    if (!groups[g]) groups[g] = [];
    groups[g].push(s);
  });

  return (
    <Shell>
      <div className="max-w-3xl space-y-6">
        <div className="flex items-center gap-3">
          <Settings className="h-6 w-6 text-purple-600" />
          <h1 className="text-2xl font-bold text-gray-900">إعدادات المنصة</h1>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center h-48">
            <Loader2 className="h-6 w-6 animate-spin text-brand-600" />
          </div>
        ) : (
          Object.entries(groups).map(([groupName, groupSettings]) => (
            groupSettings.length > 0 && (
              <div key={groupName} className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
                <div className="px-5 py-4 border-b border-gray-100 bg-gray-50">
                  <h2 className="font-semibold text-gray-700 text-sm">{groupName}</h2>
                </div>
                <div className="divide-y divide-gray-50">
                  {groupSettings.map((setting) => (
                    <div key={setting.key} className="px-5 py-4 flex items-center gap-4">
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-gray-900 text-sm" dir="ltr">{setting.key}</p>
                        {setting.description && (
                          <p className="text-xs text-gray-400 mt-0.5">{setting.description}</p>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        {editingKey === setting.key ? (
                          <>
                            {setting.value_type === "boolean" ? (
                              <select
                                value={editValue}
                                onChange={(e) => setEditValue(e.target.value)}
                                className="px-2 py-1 border border-brand-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 w-24"
                              >
                                <option value="true">نعم</option>
                                <option value="false">لا</option>
                              </select>
                            ) : (
                              <input
                                value={editValue}
                                onChange={(e) => setEditValue(e.target.value)}
                                type={setting.value_type === "number" ? "number" : "text"}
                                dir="ltr"
                                className="px-2 py-1 border border-brand-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 w-28"
                              />
                            )}
                            <button
                              onClick={() => saveEdit(setting)}
                              disabled={updateSetting.isPending}
                              className="flex items-center gap-1 px-3 py-1 bg-brand-600 hover:bg-brand-700 text-white rounded text-xs font-medium disabled:opacity-60"
                            >
                              {updateSetting.isPending && editingKey === setting.key ? (
                                <Loader2 className="h-3 w-3 animate-spin" />
                              ) : (
                                <Save className="h-3 w-3" />
                              )}
                              حفظ
                            </button>
                            <button
                              onClick={() => setEditingKey(null)}
                              className="px-3 py-1 border border-gray-300 text-gray-600 rounded text-xs hover:bg-gray-50"
                            >
                              إلغاء
                            </button>
                          </>
                        ) : (
                          <>
                            <span className="font-mono text-sm bg-gray-100 px-3 py-1 rounded" dir="ltr">
                              {setting.value_type === "boolean"
                                ? (setting.value ? "نعم" : "لا")
                                : String(setting.value)}
                            </span>
                            <button
                              onClick={() => startEdit(setting)}
                              className="text-brand-600 hover:text-brand-700 text-xs font-medium"
                            >
                              تعديل
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )
          ))
        )}
      </div>
    </Shell>
  );
}
