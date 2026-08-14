"use client";

/**
 * Every account on the platform, searchable.
 *
 * The customer file is the place to act on one pharmacy's people. This screen
 * answers the other question support gets: "someone called, here is their
 * email" — find them, see which pharmacy they belong to, and go there.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useLocale } from "next-intl";
import { Search, Users } from "lucide-react";

import Shell from "@/components/layout/shell";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { EmptyState } from "@/components/ui/empty-state";
import { adminApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";

type Row = {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  is_deleted: boolean;
  last_login_at?: string | null;
  organization_id?: string | null;
  organization_name?: string | null;
  organization_status?: string | null;
  membership_role?: string | null;
};

const ROLE_LABEL: Record<string, string> = {
  super_admin: "مدير المنصة",
  org_admin: "مدير منشأة",
  pharmacist: "صيدلي",
  viewer: "مطّلع",
};

const ROLES = [
  { value: "", label: "كل الأدوار" },
  { value: "org_admin", label: "مدير منشأة" },
  { value: "pharmacist", label: "صيدلي" },
  { value: "viewer", label: "مطّلع" },
  { value: "super_admin", label: "مدير المنصة" },
];

const PAGE_SIZE = 25;

export default function AdminUsersPage() {
  const locale = useLocale();
  const [page, setPage] = useState(1);
  const [role, setRole] = useState("");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [includeDeleted, setIncludeDeleted] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["admin-users", page, role, query, includeDeleted],
    queryFn: () =>
      adminApi
        .users({
          page,
          page_size: PAGE_SIZE,
          role: role || undefined,
          search: query || undefined,
          include_deleted: includeDeleted,
        })
        .then((r) => r.data),
  });

  const rows: Row[] = data?.items ?? [];
  const pages = data?.pages ?? 0;

  return (
    <Shell>
      <div className="space-y-6">
        <PageHeader
          title="حسابات المستخدمين"
          subtitle="ابحث عن أي حساب على المنصة وافتح ملف منشأته"
        />

        <SectionCard
          noPadding
          title="الحسابات"
          subtitle={data ? `${data.total.toLocaleString("ar-SA")} حساب` : undefined}
          action={
            <div className="flex flex-wrap items-center gap-2">
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  setPage(1);
                  setQuery(search.trim());
                }}
                className="relative"
              >
                <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#a8927a]" />
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="بريد أو اسم"
                  className="h-9 w-52 pr-9 pl-3 rounded-full bg-white ring-1 ring-inset ring-[#e1d3c0] text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </form>
              <select
                value={role}
                onChange={(event) => {
                  setRole(event.target.value);
                  setPage(1);
                }}
                className="h-9 px-3 rounded-full bg-white ring-1 ring-inset ring-[#e1d3c0] text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                {ROLES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <label className="flex items-center gap-1.5 text-xs text-[#5f665f]">
                <input
                  type="checkbox"
                  checked={includeDeleted}
                  onChange={(event) => {
                    setIncludeDeleted(event.target.checked);
                    setPage(1);
                  }}
                  className="h-3.5 w-3.5 accent-brand-600"
                />
                إظهار المحذوفة
              </label>
            </div>
          }
        >
          {isLoading ? (
            <p className="px-6 py-10 text-sm text-[#8a9089]">جارٍ التحميل…</p>
          ) : rows.length === 0 ? (
            <EmptyState
              icon={Users}
              title="لا توجد حسابات مطابقة"
              description="جرّب بريداً أو اسماً آخر."
            />
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-[#fdfbf7] text-[#8a9089]">
                    <tr>
                      <th className="text-right font-medium px-5 py-2.5">الحساب</th>
                      <th className="text-right font-medium px-3 py-2.5">المنشأة</th>
                      <th className="text-right font-medium px-3 py-2.5">الدور</th>
                      <th className="text-right font-medium px-3 py-2.5">آخر دخول</th>
                      <th className="px-3 py-2.5" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#eadfcc]">
                    {rows.map((row) => (
                      <tr key={row.id} className="hover:bg-[#fdfbf7]">
                        <td className="px-5 py-3">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-medium text-[#1f2a24]">
                              {row.full_name}
                            </span>
                            {row.is_deleted ? (
                              <span className="px-2 py-0.5 rounded-full text-xs bg-slate-800 text-white">
                                محذوف
                              </span>
                            ) : (
                              !row.is_active && (
                                <span className="px-2 py-0.5 rounded-full text-xs bg-slate-100 text-slate-600">
                                  معطّل
                                </span>
                              )
                            )}
                          </div>
                          <div dir="ltr" className="text-xs text-[#8a9089] text-right">
                            {row.email}
                          </div>
                        </td>
                        <td className="px-3 py-3 text-[#5f665f]">
                          {row.organization_name ?? "—"}
                          {row.membership_role === "owner" && (
                            <span className="text-xs text-[#8a9089]"> · المالك</span>
                          )}
                        </td>
                        <td className="px-3 py-3 text-[#5f665f] whitespace-nowrap">
                          {ROLE_LABEL[row.role] ?? row.role}
                        </td>
                        <td className="px-3 py-3 text-xs text-[#8a9089] whitespace-nowrap">
                          {row.last_login_at
                            ? formatDate(row.last_login_at, locale)
                            : "لم يدخل بعد"}
                        </td>
                        <td className="px-3 py-3 text-left">
                          {row.organization_id && (
                            <Link
                              href={`/${locale}/admin/customers/${row.organization_id}`}
                              className="inline-flex h-8 px-4 items-center rounded-full text-xs ring-1 ring-inset ring-[#e1d3c0] text-[#5f665f] hover:bg-[#fbf7f0] whitespace-nowrap"
                            >
                              ملف المنشأة
                            </Link>
                          )}
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
                    onClick={() => setPage((c) => Math.max(1, c - 1))}
                    disabled={page === 1}
                    className="h-8 px-4 rounded-full text-sm ring-1 ring-inset ring-[#e1d3c0] text-[#5f665f] disabled:opacity-40 hover:bg-[#fbf7f0]"
                  >
                    السابق
                  </button>
                  <span className="text-xs text-[#8a9089]">
                    صفحة {page.toLocaleString("ar-SA")} من {pages.toLocaleString("ar-SA")}
                  </span>
                  <button
                    type="button"
                    onClick={() => setPage((c) => Math.min(pages, c + 1))}
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
