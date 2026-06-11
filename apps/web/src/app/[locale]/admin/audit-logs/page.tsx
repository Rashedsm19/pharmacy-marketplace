"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Shell from "@/components/layout/shell";
import { adminApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Loader2, FileText, ChevronDown, ChevronUp } from "lucide-react";

const ACTION_LABELS: Record<string, string> = {
  listing_created: "إنشاء عرض",
  listing_cancelled: "إلغاء عرض",
  listing_updated: "تحديث عرض",
  offer_accepted: "قبول عرض",
  offer_rejected: "رفض عرض",
  org_approved: "قبول منشأة",
  org_rejected: "رفض منشأة",
  org_suspended: "تعليق منشأة",
  transaction_completed: "إتمام معاملة",
  setting_updated: "تحديث إعداد",
  batch_created: "إنشاء دفعة",
  user_registered: "تسجيل مستخدم",
};

export default function AuditLogsPage() {
  const [page, setPage] = useState(1);
  const [action, setAction] = useState("");
  const [entityType, setEntityType] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["audit-logs", page, action, entityType],
    queryFn: () =>
      adminApi.getAuditLogs({ page, page_size: 20, action: action || undefined, entity_type: entityType || undefined }).then((r) => r.data),
  });

  const logs = data?.items ?? [];
  const totalPages = Math.ceil((data?.total ?? 0) / 20);

  return (
    <Shell>
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <FileText className="h-6 w-6 text-purple-600" />
          <h1 className="text-2xl font-bold text-gray-900">سجل التدقيق</h1>
        </div>

        {/* Filters */}
        <div className="flex gap-3 flex-wrap">
          <select
            value={action}
            onChange={(e) => { setAction(e.target.value); setPage(1); }}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="">جميع الإجراءات</option>
            {Object.entries(ACTION_LABELS).map(([key, label]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>
          <select
            value={entityType}
            onChange={(e) => { setEntityType(e.target.value); setPage(1); }}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="">جميع الكيانات</option>
            <option value="listing">عرض</option>
            <option value="offer">عرض</option>
            <option value="organization">منشأة</option>
            <option value="transaction">معاملة</option>
            <option value="batch">دفعة</option>
            <option value="setting">إعداد</option>
          </select>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          {isLoading ? (
            <div className="flex items-center justify-center h-48">
              <Loader2 className="h-6 w-6 animate-spin text-brand-600" />
            </div>
          ) : logs.length === 0 ? (
            <div className="text-center py-16 text-gray-500">لا توجد سجلات</div>
          ) : (
            <div className="divide-y divide-gray-100">
              {logs.map((log: {
                id: string;
                action: string;
                entity_type?: string;
                entity_id?: string;
                user_email?: string;
                user_org_name?: string;
                ip_address?: string;
                created_at: string;
                before_state?: Record<string, unknown>;
                after_state?: Record<string, unknown>;
                metadata?: Record<string, unknown>;
              }) => (
                <div key={log.id}>
                  <div
                    className="flex items-center gap-4 px-5 py-3.5 hover:bg-gray-50 cursor-pointer"
                    onClick={() => setExpandedId(expandedId === log.id ? null : log.id)}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-medium text-gray-900 text-sm">
                          {ACTION_LABELS[log.action] ?? log.action}
                        </span>
                        {log.entity_type && (
                          <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded" dir="ltr">
                            {log.entity_type}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 mt-0.5 text-xs text-gray-400">
                        {log.user_email && <span dir="ltr">{log.user_email}</span>}
                        {log.user_org_name && <span>{log.user_org_name}</span>}
                        {log.ip_address && <span dir="ltr">{log.ip_address}</span>}
                      </div>
                    </div>
                    <div className="text-xs text-gray-400 flex-shrink-0">
                      {formatDate(log.created_at, "ar-SA")}
                    </div>
                    {expandedId === log.id ? (
                      <ChevronUp className="h-4 w-4 text-gray-400 flex-shrink-0" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-gray-400 flex-shrink-0" />
                    )}
                  </div>

                  {expandedId === log.id && (
                    <div className="px-5 pb-4 bg-gray-50 border-t border-gray-100">
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-3 text-xs">
                        {log.entity_id && (
                          <div>
                            <p className="text-gray-400 mb-1">معرف الكيان</p>
                            <code className="text-gray-700 font-mono bg-white px-2 py-1 rounded border text-xs">
                              {log.entity_id}
                            </code>
                          </div>
                        )}
                        {log.before_state && Object.keys(log.before_state).length > 0 && (
                          <div>
                            <p className="text-gray-400 mb-1">قبل التعديل</p>
                            <pre className="bg-white rounded border px-2 py-1.5 overflow-auto max-h-32 text-xs text-gray-700">
                              {JSON.stringify(log.before_state, null, 2)}
                            </pre>
                          </div>
                        )}
                        {log.after_state && Object.keys(log.after_state).length > 0 && (
                          <div>
                            <p className="text-gray-400 mb-1">بعد التعديل</p>
                            <pre className="bg-white rounded border px-2 py-1.5 overflow-auto max-h-32 text-xs text-gray-700">
                              {JSON.stringify(log.after_state, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
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
