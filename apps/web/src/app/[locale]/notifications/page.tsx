"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Shell from "@/components/layout/shell";
import { Badge } from "@/components/ui/badge";
import { notificationsApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Loader2, Bell, Check, CheckCheck } from "lucide-react";

const TYPE_LABELS: Record<string, string> = {
  listing_created: "تم إنشاء عرض",
  listing_expired: "انتهى عرض",
  offer_received: "عرض جديد",
  offer_accepted: "تم قبول عرضك",
  offer_rejected: "تم رفض عرضك",
  reservation_created: "تم إنشاء حجز",
  reservation_expired: "انتهى الحجز",
  transaction_dispatched: "تم الشحن",
  transaction_completed: "اكتملت المعاملة",
  near_expiry_180: "تنبيه: 180 يوم على الانتهاء",
  near_expiry_90: "تحذير: 90 يوم على الانتهاء",
  near_expiry_30: "حرج: 30 يوم على الانتهاء",
  org_approved: "تمت الموافقة على منشأتك",
  org_rejected: "تم رفض طلب منشأتك",
};

export default function NotificationsPage() {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [unreadOnly, setUnreadOnly] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["notifications", page, unreadOnly],
    queryFn: () =>
      notificationsApi.list({ page, page_size: 20, unread_only: unreadOnly }).then((r) => r.data),
  });

  const markRead = useMutation({
    mutationFn: (id: string) => notificationsApi.markRead(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications"] });
      qc.invalidateQueries({ queryKey: ["notifications-unread-count"] });
    },
  });

  const markAllRead = useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications"] });
      qc.invalidateQueries({ queryKey: ["notifications-unread-count"] });
    },
  });

  const notifications = data?.items ?? [];
  const totalPages = Math.ceil((data?.total ?? 0) / 20);
  const unreadCount = notifications.filter((n: { is_read: boolean }) => !n.is_read).length;

  return (
    <Shell>
      <div className="max-w-2xl space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Bell className="h-6 w-6 text-brand-600" />
            <h1 className="text-2xl font-bold text-gray-900">الإشعارات</h1>
            {unreadCount > 0 && (
              <span className="bg-brand-100 text-brand-700 text-xs font-semibold px-2.5 py-1 rounded-full">
                {unreadCount} جديد
              </span>
            )}
          </div>
          {unreadCount > 0 && (
            <button
              onClick={() => markAllRead.mutate()}
              disabled={markAllRead.isPending}
              className="flex items-center gap-1.5 text-sm text-brand-600 hover:text-brand-700 font-medium"
            >
              {markAllRead.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <CheckCheck className="h-4 w-4" />
              )}
              قراءة الكل
            </button>
          )}
        </div>

        <div className="flex gap-2">
          {[
            { key: false, label: "الكل" },
            { key: true, label: "غير مقروءة" },
          ].map((opt) => (
            <button
              key={String(opt.key)}
              onClick={() => { setUnreadOnly(opt.key); setPage(1); }}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                unreadOnly === opt.key
                  ? "bg-brand-600 text-white border-brand-600"
                  : "border-gray-300 text-gray-600 hover:bg-gray-50"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          {isLoading ? (
            <div className="flex items-center justify-center h-48">
              <Loader2 className="h-6 w-6 animate-spin text-brand-600" />
            </div>
          ) : notifications.length === 0 ? (
            <div className="text-center py-16">
              <Bell className="h-12 w-12 text-gray-200 mx-auto mb-3" />
              <p className="text-gray-500">لا توجد إشعارات</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {notifications.map((notif: {
                id: string;
                type: string;
                title?: string;
                body?: string;
                is_read: boolean;
                created_at: string;
              }) => (
                <div
                  key={notif.id}
                  className={`flex items-start gap-3 px-5 py-4 hover:bg-gray-50 transition-colors ${
                    !notif.is_read ? "bg-brand-50/40" : ""
                  }`}
                >
                  <div className={`mt-1 h-2 w-2 rounded-full flex-shrink-0 ${!notif.is_read ? "bg-brand-500" : "bg-transparent"}`} />
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm ${!notif.is_read ? "font-semibold text-gray-900" : "font-medium text-gray-700"}`}>
                      {notif.title ?? TYPE_LABELS[notif.type] ?? notif.type}
                    </p>
                    {notif.body && (
                      <p className="text-xs text-gray-500 mt-0.5">{notif.body}</p>
                    )}
                    <p className="text-xs text-gray-400 mt-1">{formatDate(notif.created_at, "ar-SA")}</p>
                  </div>
                  {!notif.is_read && (
                    <button
                      onClick={() => markRead.mutate(notif.id)}
                      className="text-brand-400 hover:text-brand-600 p-1 flex-shrink-0"
                      title="تحديد كمقروء"
                    >
                      <Check className="h-4 w-4" />
                    </button>
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
