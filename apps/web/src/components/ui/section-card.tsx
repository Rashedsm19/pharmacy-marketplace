"use client";

import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface SectionCardProps {
  title?: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  noPadding?: boolean;
}

export function SectionCard({
  title,
  subtitle,
  action,
  children,
  className,
  bodyClassName,
  noPadding,
}: SectionCardProps) {
  return (
    <section
      className={cn(
        "bg-white/90 ring-1 ring-[#e1d3c0] shadow-soft rounded-2xl overflow-hidden",
        className
      )}
    >
      {(title || action) && (
        <header className="flex items-start justify-between gap-3 px-5 sm:px-6 pt-5 pb-4 border-b border-[#eadfcc]">
          <div className="min-w-0">
            {title && (
              <h2 className="font-semibold text-[#1f2a24] text-base leading-tight">
                {title}
              </h2>
            )}
            {subtitle && (
              <p className="text-xs text-[#6d746d] mt-0.5">{subtitle}</p>
            )}
          </div>
          {action && <div className="flex-shrink-0">{action}</div>}
        </header>
      )}
      <div className={cn(noPadding ? "" : "px-5 sm:px-6 py-5", bodyClassName)}>
        {children}
      </div>
    </section>
  );
}

export default SectionCard;
