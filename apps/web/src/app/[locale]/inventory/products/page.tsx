"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Shell from "@/components/layout/shell";
import { DataTable } from "@/components/ui/data-table";
import { productsApi } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

type ProductRow = {
  id: string;
  name_ar?: string;
  name?: string;
  sku?: string;
  category?: {
    name_ar?: string;
  };
  standard_price?: number;
  is_active?: boolean;
  is_controlled?: boolean;
  is_restricted?: boolean;
};

export default function ProductsPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["products", page, search],
    queryFn: () =>
      productsApi.list({ page, page_size: 20, search }).then((r) => r.data),
  });

  return (
    <Shell>
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">كتالوج المنتجات</h1>

        <DataTable<ProductRow>
          rowKey={(r: { id: string }) => r.id}
          isLoading={isLoading}
          data={data?.items ?? []}
          total={data?.total ?? 0}
          page={page}
          pageSize={20}
          onPageChange={setPage}
          onSearch={setSearch}
          searchPlaceholder="بحث بالاسم أو الرمز..."
          emptyMessage="لا توجد منتجات"
          columns={[
            {
              key: "name_ar",
              header: "الاسم",
              render: (r: { name_ar?: string; name?: string }) => r.name_ar ?? r.name ?? "—",
            },
            { key: "sku", header: "الرمز (SKU)" },
            {
              key: "category",
              header: "الفئة",
              render: (r: { category?: { name_ar?: string } }) =>
                r.category?.name_ar ?? "—",
            },
            {
              key: "standard_price",
              header: "السعر الافتراضي",
              render: (r: { standard_price?: number }) =>
                r.standard_price ? formatCurrency(r.standard_price) : "—",
            },
            {
              key: "is_active",
              header: "الحالة",
              render: (r: { is_active?: boolean }) => (
                <Badge variant={r.is_active ? "success" : "danger"}>
                  {r.is_active ? "نشط" : "غير نشط"}
                </Badge>
              ),
            },
            {
              key: "is_controlled",
              header: "مقيّد",
              render: (r: { is_controlled?: boolean; is_restricted?: boolean }) =>
                r.is_controlled || r.is_restricted ? (
                  <Badge variant="danger">نعم</Badge>
                ) : (
                  <Badge variant="success">لا</Badge>
                ),
            },
          ]}
        />
      </div>
    </Shell>
  );
}
