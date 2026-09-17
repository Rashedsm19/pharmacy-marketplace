import { cn } from "@/lib/utils";

interface ProgressProps {
  value: number;
  max?: number;
  tone?: "brand" | "gold" | "warning" | "critical";
  className?: string;
}

const tones = {
  brand: "bg-brand-600",
  gold: "bg-gold-500",
  warning: "bg-amber-500",
  critical: "bg-rose-600",
};

export function Progress({ value, max = 100, tone, className }: ProgressProps) {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  const auto = tone ?? (pct >= 100 ? "critical" : pct >= 80 ? "warning" : "brand");
  return (
    <div className={cn("h-2 w-full overflow-hidden rounded-full bg-[#eadfcc]", className)} role="progressbar" aria-valuenow={value} aria-valuemax={max}>
      <div className={cn("h-full rounded-full transition-all", tones[auto])} style={{ width: `${pct}%` }} />
    </div>
  );
}
