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
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";

export default function BatchesPage() {
  const locale = useLocale();
  const t = useTranslations("inventory");
  const [page, setPage] = useState(1);
  const [, setSearch] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["batches", page],
    queryFn: () =>
      inventoryApi.listBatches({ page, page_size: 20 }).then((r) => r.data),
  });

  return (
    <Shell>
      <div className="space-y-6">
        <PageHeader
          title={t("batches")}
          subtitle="جميع دفعات المخزون مع تواريخ الانتهاء"
          actions={
            <Link href={`/${locale}/inventory/batches/new`}>
              <Button variant="primary">
                <Plus className="h-4 w-4" />
                {t("addBatch")}
              </Button>
            </Link>
          }
        />

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
          minWidthClass="min-w-[820px]"
          columns={[
            {
              key: "product_name_ar",
              header: t("product"),
              render: (r: { product_name_ar?: string; product_name?: string }) =>
                <span className="font-medium text-slate-900">{r.product_name_ar ?? r.product_name ?? "—"}</span>,
            },
            {
              key: "batch_number",
              header: t("batchNumber"),
              hiddenOnMobile: true,
            },
            {
              key: "branch_name",
              header: t("branch"),
              hiddenOnMobile: true,
            },
            {
              key: "expiry_date",
              header: t("expiryDate"),
              render: (r: { expiry_date?: string }) =>
                r.expiry_date
                  ? new Date(r.expiry_date).toLocaleDateString("ar-SA")
                  : "—",
              hiddenOnMobile: true,
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
              hiddenOnMobile: true,
              render: (r: { unit_cost?: number }) =>
                r.unit_cost ? <span className="text-slate-700 tabular-nums">{formatCurrency(r.unit_cost)}</span> : "—",
            },
          ]}
          actions={(r: { id: string }) => (
            <Link
              href={`/${locale}/inventory/batches/${r.id}`}
              className="h-8 w-8 inline-flex items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-brand-600"
              title="عرض"
            >
              <Eye className="h-4 w-4" />
            </Link>
          )}
        />
      </div>
    </Shell>
  );
}
