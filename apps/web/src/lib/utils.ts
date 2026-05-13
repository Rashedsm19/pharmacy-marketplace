import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(amount: number): string {
  return `${amount.toLocaleString("ar-SA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ر.س`;
}

export function getExpiryZone(daysUntilExpiry: number): "green" | "yellow" | "orange" | "red" {
  if (daysUntilExpiry > 180) return "green";
  if (daysUntilExpiry > 90) return "yellow";
  if (daysUntilExpiry > 30) return "orange";
  return "red";
}

export const expiryZoneColors = {
  green: "bg-green-100 text-green-800 border-green-200",
  yellow: "bg-yellow-100 text-yellow-800 border-yellow-200",
  orange: "bg-orange-100 text-orange-800 border-orange-200",
  red: "bg-red-100 text-red-800 border-red-200",
} as const;

export const expiryZoneLabels = {
  ar: {
    green: "صالح (180+ يوم)",
    yellow: "تنبيه (90-180 يوم)",
    orange: "تحذير (30-90 يوم)",
    red: "حرج (أقل من 30 يوم)",
  },
  en: {
    green: "Healthy (180+ days)",
    yellow: "Notice (90-180 days)",
    orange: "Warning (30-90 days)",
    red: "Critical (<30 days)",
  },
} as const;

export function formatDate(dateStr: string, locale = "ar-SA"): string {
  return new Date(dateStr).toLocaleDateString(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function getPaginationRange(page: number, totalPages: number, delta = 2): (number | "...")[] {
  const range: (number | "...")[] = [];
  for (let i = Math.max(2, page - delta); i <= Math.min(totalPages - 1, page + delta); i++) {
    range.push(i);
  }
  if (page - delta > 2) range.unshift("...");
  if (page + delta < totalPages - 1) range.push("...");
  range.unshift(1);
  if (totalPages > 1) range.push(totalPages);
  return [...new Set(range)];
}
