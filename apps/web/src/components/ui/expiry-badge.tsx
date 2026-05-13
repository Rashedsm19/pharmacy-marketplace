import { cn, getExpiryZone, expiryZoneColors } from "@/lib/utils";

interface ExpiryBadgeProps {
  daysUntilExpiry: number;
  className?: string;
}

const zoneLabels: Record<string, string> = {
  green: "صالح",
  yellow: "تنبيه",
  orange: "تحذير",
  red: "حرج",
};

export function ExpiryBadge({ daysUntilExpiry, className }: ExpiryBadgeProps) {
  const zone = getExpiryZone(daysUntilExpiry);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium border",
        expiryZoneColors[zone],
        className
      )}
    >
      {zoneLabels[zone]} — {daysUntilExpiry} يوم
    </span>
  );
}
