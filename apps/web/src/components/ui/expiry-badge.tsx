import { cn, getExpiryZone, expiryZoneColors } from "@/lib/utils";

interface ExpiryBadgeProps {
  daysUntilExpiry: number;
  className?: string;
  showDays?: boolean;
}

const zoneLabels: Record<string, string> = {
  green: "صالح",
  yellow: "تنبيه",
  orange: "تحذير",
  red: "حرج",
};

const zoneDots: Record<string, string> = {
  green: "bg-emerald-500",
  yellow: "bg-yellow-500",
  orange: "bg-orange-500",
  red: "bg-rose-500",
};

export function ExpiryBadge({
  daysUntilExpiry,
  className,
  showDays = true,
}: ExpiryBadgeProps) {
  const zone = getExpiryZone(daysUntilExpiry);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium",
        expiryZoneColors[zone],
        className
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", zoneDots[zone])} />
      <span>{zoneLabels[zone]}</span>
      {showDays && <span className="tabular-nums">— {daysUntilExpiry} يوم</span>}
    </span>
  );
}
