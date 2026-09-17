"use client";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { FileQuestion } from "lucide-react";
import EmptyState from "@/components/ui/empty-state";
import Button from "@/components/ui/button";

export default function LocaleNotFound() {
  const t = useTranslations("notFound");
  const locale = useLocale();

  return (
    <div className="min-h-[70vh] flex flex-col items-center justify-center">
      <p className="text-7xl font-black text-[#a88d60] select-none" aria-hidden>
        404
      </p>
      <EmptyState
        icon={FileQuestion}
        title={t("title")}
        description={t("description")}
        action={
          <Link href={`/${locale}/dashboard`}>
            <Button>{t("backToDashboard")}</Button>
          </Link>
        }
      />
    </div>
  );
}
