"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import Shell from "@/components/layout/shell";
import { DataTable } from "@/components/ui/data-table";
import { ExpiryBadge } from "@/components/ui/expiry-badge";
import { inventoryApi } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { Plus, Eye } from "lucide-react";

export default function BatchesPage() {
  const locale = useLocale();
  const t = useTranslations("inventory");
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["batches", page, search],
    queryFn: () =>
      inventoryApi.listBatches({ page, page_size: 20 }).then((r) => r.data),
  });

  return (
    <Shell>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">{t("batches")}</h1>
          <Link
            href={`/${locale}/inventory/batches/new`}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-medium px-4 py-2 rounded-lg text-sm transition-colors"
          >
            <Plus className="h-4 w-4" />
            {t("addBatch")}
          </Link>
        </div>

        <DataTable
          rowKey={(r: { id: string }) => r.id}
          isLoading={isLoading}
          data={data?.items ?? []}
          total={data?.total ?? 0}
          page={page}
          pageSize={20}
          onPageChange={setPage}
          onSearch={setSearch}
          searchPlaceholder="بحث بالمنتج أو رقم الدفعة..."
          emptyMessage="لا توجد دفعات"
          columns={[
            {
              key: "product_name_ar",
              header: t("product"),
              render: (r: { product_name_ar?: string; product_name?: string }) =>
                r.product_name_ar ?? r.product_name ?? "—",
            },
            {
              key: "batch_number",
              header: t("batchNumber"),
            },
            {
              key: "branch_name",
              header: t("branch"),
            },
            {
              key: "expiry_date",
              header: t("expiryDate"),
              render: (r: { expiry_date?: string }) =>
                r.expiry_date
                  ? new Date(r.expiry_date).toLocaleDateString("ar-SA")
                  : "—",
            },
            {
              key: "days_until_expiry",
              header: t("daysLeft"),
              render: (r: { days_until_expiry?: number }) =>
                r.days_until_expiry !== undefined ? (
                  <ExpiryBadge daysUntilExpiry={r.days_until_expiry} />
                ) : (
                  "—"
                ),
            },
            {
              key: "quantity_available",
              header: t("quantity"),
            },
            {
              key: "unit_cost",
              header: t("unitCost"),
              render: (r: { unit_cost?: number }) =>
                r.unit_cost ? formatCurrency(r.unit_cost) : "—",
            },
          ]}
          actions={(r: { id: string }) => (
            <Link
              href={`/${locale}/inventory/batches/${r.id}`}
              className="p-1.5 hover:bg-gray-100 rounded text-gray-500 hover:text-blue-600"
            >
              <Eye className="h-4 w-4" />
            </Link>
          )}
        />
      </div>
    </Shell>
  );
}
