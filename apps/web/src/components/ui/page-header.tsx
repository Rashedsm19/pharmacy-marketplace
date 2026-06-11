"use client";

import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface PageHeaderProps {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  back?: ReactNode;
  className?: string;
}

export function PageHeader({
  title,
  subtitle,
  actions,
  back,
  className,
}: PageHeaderProps) {
  return (
    <div
      className={cn(
        "flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between",
        className
      )}
    >
      <div className="min-w-0">
        {back && <div className="mb-1.5">{back}</div>}
        <h1 className="text-xl sm:text-2xl font-semibold text-[#1f2a24] tracking-normal">
          {title}
        </h1>
        {subtitle && (
          <p className="text-sm text-[#6d746d] mt-1 leading-relaxed">
            {subtitle}
          </p>
        )}
      </div>
      {actions && (
        <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>
      )}
    </div>
  );
}

export default PageHeader;
