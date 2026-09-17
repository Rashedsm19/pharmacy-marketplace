"use client";

import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import Shell from "@/components/layout/shell";
import { PageHeader } from "@/components/ui/page-header";
import {
  AlertTriangle,
  TrendingDown,
  PiggyBank,
  Star,
  GitCompareArrows,
  ChevronLeft,
} from "lucide-react";

export default function ReportsIndexPage() {
  const t = useTranslations("reports");
  const locale = useLocale();

  const reports = [
    { href: "near-expiry", icon: AlertTriangle, label: t("nearExpiry") },
    { href: "expired-loss", icon: TrendingDown, label: t("expiredLoss") },
    { href: "recoverable-value", icon: PiggyBank, label: t("recoverableValue") },
    { href: "top-products", icon: Star, label: t("topProducts") },
    { href: "branch-comparison", icon: GitCompareArrows, label: t("branchComparison") },
  ];

  return (
    <Shell>
      <div className="space-y-6">
        <PageHeader title={t("title")} />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {reports.map((r) => (
            <Link
              key={r.href}
              href={`/${locale}/reports/${r.href}`}
              className="group flex items-center justify-between rounded-2xl bg-white p-5 ring-1 ring-slate-200 hover:ring-brand-300 hover:shadow-sm transition"
            >
              <span className="flex items-center gap-3">
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
                  <r.icon className="h-5 w-5" />
                </span>
                <span className="font-medium text-slate-800">{r.label}</span>
              </span>
              <ChevronLeft className="h-4 w-4 text-slate-300 group-hover:text-brand-500 rtl:rotate-0 ltr:rotate-180" />
            </Link>
          ))}
        </div>
      </div>
    </Shell>
  );
}
