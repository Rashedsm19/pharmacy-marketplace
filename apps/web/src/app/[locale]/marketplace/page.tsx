"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useLocale } from "next-intl";
import Shell from "@/components/layout/shell";
import { listingsApi, productsApi } from "@/lib/api";
import { formatCurrency, getExpiryZone, expiryZoneColors } from "@/lib/utils";
import Link from "next/link";
import { Search, Filter, Package, Plus } from "lucide-react";
import { cn } from "@/lib/utils";

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
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">السوق</h1>
          <Link
            href={`/${locale}/marketplace/create`}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-medium px-4 py-2 rounded-lg text-sm"
          >
            <Plus className="h-4 w-4" />
            إنشاء إعلان
          </Link>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4 flex gap-4 items-center flex-wrap">
          <div className="relative flex-1 min-w-48">
            <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="بحث في الإعلانات..."
              className="w-full pr-10 pl-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <select
            value={categoryId}
            onChange={(e) => setCategoryId(e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">كل الفئات</option>
            {(categories ?? []).map((c: { id: string; name_ar: string }) => (
              <option key={c.id} value={c.id}>
                {c.name_ar}
              </option>
            ))}
          </select>
        </div>

        {/* Listings Grid */}
        {isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="bg-white rounded-xl p-5 shadow-sm border border-gray-100 animate-pulse">
                <div className="h-4 bg-gray-200 rounded w-3/4 mb-2" />
                <div className="h-3 bg-gray-200 rounded w-1/2 mb-4" />
                <div className="h-8 bg-gray-200 rounded" />
              </div>
            ))}
          </div>
        ) : !listings?.items?.length ? (
          <div className="bg-white rounded-xl p-12 text-center shadow-sm border border-gray-100">
            <Package className="h-16 w-16 mx-auto text-gray-300 mb-4" />
            <h3 className="text-lg font-semibold text-gray-700 mb-1">لا توجد إعلانات</h3>
            <p className="text-gray-400 text-sm">لم يتم العثور على إعلانات مطابقة لبحثك</p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
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
                  const zone = l.expiry_zone ?? (l.days_until_expiry !== undefined ? getExpiryZone(l.days_until_expiry) : "green");
                  return (
                    <Link
                      key={l.id}
                      href={`/${locale}/marketplace/${l.id}`}
                      className="bg-white rounded-xl p-5 shadow-sm border border-gray-100 hover:border-blue-200 hover:shadow-md transition-all"
                    >
                      <div className="flex items-start justify-between mb-2">
                        <h3 className="font-semibold text-gray-900 text-sm leading-tight line-clamp-2">
                          {l.title_ar ?? l.title}
                        </h3>
                        <span
                          className={cn(
                            "text-xs px-2 py-0.5 rounded-full border ml-2 flex-shrink-0",
                            expiryZoneColors[zone as keyof typeof expiryZoneColors]
                          )}
                        >
                          {l.days_until_expiry} يوم
                        </span>
                      </div>
                      <p className="text-xs text-gray-500 mb-3">{l.seller_org_name ?? "—"}</p>
                      <div className="flex items-center justify-between">
                        <span className="text-lg font-bold text-blue-600">
                          {formatCurrency(l.asking_price)}
                        </span>
                        <span className="text-xs text-gray-500">
                          كمية: {l.quantity_available}
                        </span>
                      </div>
                    </Link>
                  );
                }
              )}
            </div>

            {/* Pagination */}
            {(listings.pages ?? 0) > 1 && (
              <div className="flex justify-center gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-sm disabled:opacity-40 hover:bg-gray-50"
                >
                  السابق
                </button>
                <span className="px-4 py-2 text-sm text-gray-600">
                  {page} من {listings.pages}
                </span>
                <button
                  onClick={() => setPage((p) => p + 1)}
                  disabled={page >= listings.pages}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-sm disabled:opacity-40 hover:bg-gray-50"
                >
                  التالي
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </Shell>
  );
}
