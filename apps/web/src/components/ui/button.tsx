"use client";

import { forwardRef, ButtonHTMLAttributes } from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "outline" | "gold";
type Size = "sm" | "md" | "lg" | "icon";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  fullWidth?: boolean;
}

const base =
  "inline-flex items-center justify-center gap-2 font-medium rounded-full transition-all duration-150 disabled:opacity-60 disabled:cursor-not-allowed select-none whitespace-nowrap focus-visible:outline-none";

const variants: Record<Variant, string> = {
  primary:
    "bg-[#1f2a24] text-[#fbf7f0] hover:bg-brand-800 active:bg-brand-900 shadow-sm hover:shadow-card",
  secondary:
    "bg-surface-subtle text-[#1f2a24] hover:bg-surface-muted active:bg-surface-muted ring-1 ring-inset ring-[#d9c9b5]",
  ghost:
    "bg-transparent text-[#4d554e] hover:bg-surface-subtle active:bg-surface-muted",
  outline:
    "bg-white/80 text-[#1f2a24] hover:bg-surface-subtle active:bg-surface-muted ring-1 ring-inset ring-[#cdbda8]",
  danger:
    "bg-rose-600 text-white hover:bg-rose-700 active:bg-rose-800 shadow-sm",
  gold:
    "bg-gold-500 text-[#1f2a24] hover:bg-gold-600 active:bg-gold-700 shadow-sm hover:shadow-card",
};

const sizes: Record<Size, string> = {
  sm: "h-8 px-3 text-xs",
  md: "h-10 px-4 text-sm",
  lg: "h-11 px-5 text-sm",
  icon: "h-10 w-10 p-0",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = "primary",
      size = "md",
      loading = false,
      fullWidth = false,
      disabled,
      children,
      ...props
    },
    ref
  ) => {
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={cn(
          base,
          variants[variant],
          sizes[size],
          fullWidth && "w-full",
          className
        )}
        {...props}
      >
        {loading && <Loader2 className="h-4 w-4 animate-spin" />}
        {children}
      </button>
    );
  }
);

Button.displayName = "Button";

export default Button;
