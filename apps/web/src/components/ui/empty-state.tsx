"use client";

import { ReactNode } from "react";
import { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center text-center py-12 px-4",
        className
      )}
    >
      {Icon && (
        <div className="h-14 w-14 rounded-2xl bg-[#f4eadf] ring-1 ring-[#e2d4bf] flex items-center justify-center mb-3">
          <Icon className="h-7 w-7 text-[#a88d60]" />
        </div>
      )}
      <h3 className="text-base font-semibold text-[#1f2a24]">{title}</h3>
      {description && (
        <p className="text-sm text-[#6d746d] mt-1 max-w-sm">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export default EmptyState;
