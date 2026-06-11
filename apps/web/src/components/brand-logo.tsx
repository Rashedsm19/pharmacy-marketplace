import Image from "next/image";
import { cn } from "@/lib/utils";

type BrandLogoSize = "sm" | "md" | "lg";

interface BrandLogoProps {
  compact?: boolean;
  size?: BrandLogoSize;
  className?: string;
}

const sizes: Record<
  BrandLogoSize,
  {
    root: string;
    mark: string;
    title: string;
    subtitle: string;
    imageSizes: string;
  }
> = {
  sm: {
    root: "gap-2.5",
    mark: "h-9 w-9 rounded-2xl",
    title: "text-sm",
    subtitle: "text-[10px]",
    imageSizes: "36px",
  },
  md: {
    root: "gap-3",
    mark: "h-12 w-12 rounded-2xl",
    title: "text-base",
    subtitle: "text-[11px]",
    imageSizes: "48px",
  },
  lg: {
    root: "gap-3.5",
    mark: "h-16 w-16 rounded-2xl",
    title: "text-xl",
    subtitle: "text-xs",
    imageSizes: "64px",
  },
};

export default function BrandLogo({ compact = false, size = "md", className }: BrandLogoProps) {
  const current = sizes[size];

  return (
    <div className={cn("flex items-center min-w-0", current.root, className)}>
      <div
        className={cn(
          "relative flex shrink-0 items-center justify-center overflow-hidden bg-white shadow-sm ring-1 ring-[#e2d4bf]",
          current.mark
        )}
      >
        <Image
          src="/medsave-logo.png"
          alt="MedSave"
          width={512}
          height={512}
          sizes={current.imageSizes}
          className="h-full w-full object-contain"
          priority={size === "lg"}
        />
      </div>
      {!compact && (
        <div className="min-w-0 text-right">
          <p className={cn("font-semibold text-[#1f2a24] leading-tight truncate", current.title)}>
            MedSave
          </p>
          <p className={cn("font-medium text-[#6d746d] leading-tight truncate", current.subtitle)}>
            منصة تداول مخزون الصيدليات
          </p>
        </div>
      )}
    </div>
  );
}
