"use client";

import { ReactNode } from "react";
import { LucideIcon, TrendingUp, TrendingDown } from "lucide-react";
import { cn } from "@/lib/utils";

type Tone = "brand" | "gold" | "safe" | "notice" | "warning" | "critical" | "slate";

interface KpiCardProps {
  icon?: LucideIcon;
  label: string;
  value: ReactNode;
  hint?: string;
  trend?: { value: string; direction: "up" | "down" | "flat" };
  tone?: Tone;
  className?: string;
}

const toneClasses: Record<Tone, { halo: string; icon: string; ring: string }> = {
  brand: {
    halo: "bg-brand-50",
    icon: "text-brand-600",
    ring: "ring-brand-100",
  },
  gold: {
    halo: "bg-gold-50",
    icon: "text-gold-600",
    ring: "ring-gold-100",
  },
  safe: {
    halo: "bg-emerald-50",
    icon: "text-emerald-600",
    ring: "ring-emerald-100",
  },
  notice: {
    halo: "bg-yellow-50",
    icon: "text-yellow-600",
    ring: "ring-yellow-100",
  },
  warning: {
    halo: "bg-orange-50",
    icon: "text-orange-600",
    ring: "ring-orange-100",
  },
  critical: {
    halo: "bg-rose-50",
    icon: "text-rose-600",
    ring: "ring-rose-100",
  },
  slate: {
    halo: "bg-[#f4eadf]",
    icon: "text-[#6d746d]",
    ring: "ring-[#e2d4bf]",
  },
};

export function KpiCard({
  icon: Icon,
  label,
  value,
  hint,
  trend,
  tone = "brand",
  className,
}: KpiCardProps) {
  const t = toneClasses[tone];
  return (
    <div
      className={cn(
        "group relative bg-white/90 ring-1 ring-[#e1d3c0] shadow-soft rounded-2xl p-5 transition-all duration-200 hover:shadow-card hover:ring-[#cdbda8]",
        className
      )}
    >
      <div className="flex items-start gap-4">
        {Icon && (
          <div
            className={cn(
              "h-11 w-11 rounded-xl flex items-center justify-center flex-shrink-0 ring-1",
              t.halo,
              t.ring
            )}
          >
            <Icon className={cn("h-5 w-5", t.icon)} />
          </div>
        )}
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium text-[#6d746d] uppercase tracking-normal truncate">
            {label}
          </p>
          <p className="kpi-value mt-1 text-2xl sm:text-[1.75rem] font-semibold text-[#1f2a24] leading-tight">
            {value}
          </p>
          {(hint || trend) && (
            <div className="mt-1.5 flex items-center gap-2 text-xs">
              {trend && (
                <span
                  className={cn(
                    "inline-flex items-center gap-0.5 font-medium",
                    trend.direction === "up" && "text-emerald-600",
                    trend.direction === "down" && "text-rose-600",
                    trend.direction === "flat" && "text-[#6d746d]"
                  )}
                >
                  {trend.direction === "up" && <TrendingUp className="h-3 w-3" />}
                  {trend.direction === "down" && (
                    <TrendingDown className="h-3 w-3" />
                  )}
                  {trend.value}
                </span>
              )}
              {hint && <span className="text-[#6d746d]">{hint}</span>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default KpiCard;
