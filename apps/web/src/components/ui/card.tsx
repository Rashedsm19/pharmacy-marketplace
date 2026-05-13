"use client";

import { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

type Variant = "default" | "elevated" | "ghost" | "outline";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: Variant;
}

const variants: Record<Variant, string> = {
  default:
    "bg-white ring-1 ring-slate-200/70 shadow-soft rounded-2xl",
  elevated:
    "bg-white ring-1 ring-slate-200/70 shadow-lift rounded-2xl",
  ghost:
    "bg-transparent rounded-2xl",
  outline:
    "bg-white ring-1 ring-slate-200 rounded-2xl",
};

export function Card({ className, variant = "default", ...props }: CardProps) {
  return <div className={cn(variants[variant], className)} {...props} />;
}

interface CardHeaderProps extends HTMLAttributes<HTMLDivElement> {
  title?: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
}

export function CardHeader({
  className,
  title,
  subtitle,
  action,
  children,
  ...props
}: CardHeaderProps) {
  if (title || subtitle || action) {
    return (
      <div
        className={cn(
          "flex items-start justify-between gap-3 px-5 sm:px-6 pt-5 pb-3",
          className
        )}
        {...props}
      >
        <div className="min-w-0">
          {title && (
            <h2 className="font-semibold text-slate-900 text-base leading-tight">
              {title}
            </h2>
          )}
          {subtitle && (
            <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>
          )}
        </div>
        {action && <div className="flex-shrink-0">{action}</div>}
        {children}
      </div>
    );
  }
  return (
    <div
      className={cn("px-5 sm:px-6 pt-5 pb-3", className)}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardBody({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-5 sm:px-6 py-5", className)} {...props} />;
}

export function CardFooter({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "px-5 sm:px-6 py-4 border-t border-slate-100",
        className
      )}
      {...props}
    />
  );
}

export default Card;
