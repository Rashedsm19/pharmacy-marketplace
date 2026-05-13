import { cn } from "@/lib/utils";

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "success" | "warning" | "danger" | "info" | "secondary" | "brand" | "gold";
  size?: "sm" | "md";
}

const variants = {
  default:
    "bg-slate-50 text-slate-700 ring-1 ring-inset ring-slate-200",
  success:
    "bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-200",
  warning:
    "bg-amber-50 text-amber-800 ring-1 ring-inset ring-amber-200",
  danger:
    "bg-rose-50 text-rose-700 ring-1 ring-inset ring-rose-200",
  info:
    "bg-sky-50 text-sky-700 ring-1 ring-inset ring-sky-200",
  secondary:
    "bg-violet-50 text-violet-700 ring-1 ring-inset ring-violet-200",
  brand:
    "bg-brand-50 text-brand-700 ring-1 ring-inset ring-brand-200",
  gold:
    "bg-gold-50 text-gold-700 ring-1 ring-inset ring-gold-200",
};

const sizes = {
  sm: "px-2 py-0.5 text-[11px]",
  md: "px-2.5 py-0.5 text-xs",
};

export function Badge({
  className,
  variant = "default",
  size = "md",
  children,
  ...props
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full font-medium",
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
}
