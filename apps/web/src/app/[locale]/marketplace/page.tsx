"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useLocale } from "next-intl";
import Shell from "@/components/layout/shell";
import { listingsApi, productsApi } from "@/lib/api";
import { formatCurrency, getExpiryZone } from "@/lib/utils";
import Link from "next/link";
import { Search, Package, Plus, ChevronLeft, ChevronRight } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ExpiryBadge } from "@/components/ui/expiry-badge";
import { EmptyState } from "@/components/ui/empty-state";

const zoneStripeGradient: Record<string, string> = {
  green: "from-emerald-400 to-emerald-500",
  yellow: "from-yellow-400 to-yellow-500",
  orange: "from-orange-400 to-orange-500",
  red: "from-rose-400 to-rose-500",
};

export default function MarketplacePage() {
  const locale = useLocale();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [categoryId, setCategoryId] = useState("");

  const { data: listings, isLoading } = useQuery({
    queryKey: ["listings", page, search, categoryId],
    queryFn: () =>
      listingsApi
        .list({
          page,
          page_size: 20,
          search: search || undefined,
          category_id: categoryId || undefined,
        })
        .then((r) => r.data),
  });

  const { data: categories } = useQuery({
    queryKey: ["categories"],
    queryFn: () => productsApi.listCategories().then((r) => r.data),
  });

  return (
    <Shell>
      <div className="space-y-6">
        <PageHeader
          title="السوق"
          subtitle="اكتشف الدفعات المعروضة من صيدليات معتمدة"
          actions={
            <Link href={`/${locale}/marketplace/create`}>
              <Button variant="gold">
                <Plus className="h-4 w-4" />
                إنشاء إعلان
              </Button>
            </Link>
          }
        />

        {/* Filters */}
        <Card className="p-4">
          <div className="flex flex-col md:flex-row md:items-center gap-3">
            <div className="relative w-full md:flex-1">
              <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="بحث في الإعلانات..."
                className="w-full h-10 pr-10 pl-4 bg-slate-50/60 ring-1 ring-inset ring-slate-200 rounded-lg text-sm placeholder:text-slate-400 focus:outline-none focus:bg-white focus:ring-2 focus:ring-brand-500"
              />
            </div>
            <select
              value={categoryId}
              onChange={(e) => setCategoryId(e.target.value)}
              className="w-full md:w-auto h-10 px-3 bg-slate-50/60 ring-1 ring-inset ring-slate-200 rounded-lg text-sm focus:outline-none focus:bg-white focus:ring-2 focus:ring-brand-500"
            >
              <option value="">كل الفئات</option>
              {(categories ?? []).map((c: { id: string; name_ar: string }) => (
                <option key={c.id} value={c.id}>
                  {c.name_ar}
                </option>
              ))}
            </select>
          </div>
        </Card>

        {/* Listings Grid */}
        {isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="bg-white rounded-2xl p-5 ring-1 ring-slate-200/70 shadow-soft animate-pulse"
              >
                <div className="h-4 bg-slate-100 rounded w-3/4 mb-2" />
                <div className="h-3 bg-slate-100 rounded w-1/2 mb-5" />
                <div className="h-8 bg-slate-100 rounded" />
              </div>
            ))}
          </div>
        ) : !listings?.items?.length ? (
          <Card>
            <EmptyState
              icon={Package}
              title="لا توجد إعلانات"
              description="لم يتم العثور على إعلانات مطابقة لبحثك"
            />
          </Card>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {listings.items.map(
                (l: {
                  id: string;
                  title: string;
                  title_ar?: string;
                  asking_price: number;
                  quantity_available: number;
                  days_until_expiry?: number;
                  expiry_zone?: string;
                  seller_org_name?: string;
                }) => {
                  const zone =
                    l.expiry_zone ??
                    (l.days_until_expiry !== undefined
                      ? getExpiryZone(l.days_until_expiry)
                      : "green");
                  return (
                    <Link
                      key={l.id}
                      href={`/${locale}/marketplace/${l.id}`}
                      className="group relative bg-white rounded-2xl ring-1 ring-slate-200/70 shadow-soft hover:ring-brand-300 hover:shadow-lift transition-all duration-200 overflow-hidden"
                    >
                      <div
                        className={`h-1 bg-gradient-to-r ${zoneStripeGradient[zone] ?? zoneStripeGradient.green}`}
                      />
                      <div className="p-5">
                        <div className="flex items-start justify-between gap-3 mb-2">
                          <h3 className="font-semibold text-slate-900 text-sm leading-snug line-clamp-2 group-hover:text-brand-700 transition-colors">
                            {l.title_ar ?? l.title}
                          </h3>
                          {l.days_until_expiry !== undefined && (
                            <ExpiryBadge
                              daysUntilExpiry={l.days_until_expiry}
                              className="flex-shrink-0"
                            />
                          )}
                        </div>
                        <p className="text-xs text-slate-500 mb-4 truncate">
                          {l.seller_org_name ?? "—"}
                        </p>
                        <div className="flex items-end justify-between">
                          <div>
                            <p className="text-[10px] uppercase tracking-wide text-slate-400 mb-0.5">
                              السعر المطلوب
                            </p>
                            <span className="text-lg font-bold text-slate-900 tabular-nums">
                              {formatCurrency(l.asking_price)}
                            </span>
                          </div>
                          <span className="text-xs text-slate-500 tabular-nums">
                            متوفر: {l.quantity_available}
                          </span>
                        </div>
                      </div>
                    </Link>
                  );
                }
              )}
            </div>

            {/* Pagination */}
            {(listings.pages ?? 0) > 1 && (
              <div className="flex justify-center items-center gap-1.5">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  aria-label="السابق"
                  className="h-9 w-9 inline-flex items-center justify-center rounded-lg ring-1 ring-slate-200 text-slate-500 hover:bg-slate-50 disabled:opacity-40"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
                <span className="px-3 py-2 text-sm text-slate-600 tabular-nums">
                  {page} من {listings.pages}
                </span>
                <button
                  onClick={() => setPage((p) => p + 1)}
                  disabled={page >= listings.pages}
                  aria-label="التالي"
                  className="h-9 w-9 inline-flex items-center justify-center rounded-lg ring-1 ring-slate-200 text-slate-500 hover:bg-slate-50 disabled:opacity-40"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </Shell>
  );
}
