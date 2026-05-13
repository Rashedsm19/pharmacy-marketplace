"use client";

import { ReactNode, ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

interface StatPillProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: ReactNode;
  count?: number;
  active?: boolean;
}

export function StatPill({
  label,
  count,
  active = false,
  className,
  ...props
}: StatPillProps) {
  return (
    <button
      type="button"
      className={cn(
        "inline-flex items-center gap-2 h-8 px-3 rounded-full text-xs font-medium transition-colors",
        active
          ? "bg-brand-600 text-white shadow-sm"
          : "bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50 hover:text-slate-900",
        className
      )}
      {...props}
    >
      <span>{label}</span>
      {count !== undefined && (
        <span
          className={cn(
            "px-1.5 py-0.5 rounded-full text-[10px] font-semibold leading-none",
            active ? "bg-white/20 text-white" : "bg-slate-100 text-slate-600"
          )}
        >
          {count}
        </span>
      )}
    </button>
  );
}

export default StatPill;
