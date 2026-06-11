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
    mark: "h-9 w-9 rounded-xl",
    title: "text-sm",
    subtitle: "text-[10px]",
    imageSizes: "36px",
  },
  md: {
    root: "gap-3",
    mark: "h-11 w-11 rounded-2xl",
    title: "text-base",
    subtitle: "text-[11px]",
    imageSizes: "44px",
  },
  lg: {
    root: "gap-3.5",
    mark: "h-14 w-14 rounded-2xl",
    title: "text-xl",
    subtitle: "text-xs",
    imageSizes: "56px",
  },
};

export default function BrandLogo({ compact = false, size = "md", className }: BrandLogoProps) {
  const current = sizes[size];

  return (
    <div className={cn("flex items-center min-w-0", current.root, className)}>
      <div
        className={cn(
          "relative flex shrink-0 items-center justify-center overflow-hidden bg-white shadow-sm ring-1 ring-slate-200/80",
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
          <p className={cn("font-bold text-slate-900 leading-tight truncate", current.title)}>
            MedSave
          </p>
          <p className={cn("font-medium text-slate-500 leading-tight truncate", current.subtitle)}>
            سوق الصيدليات
          </p>
        </div>
      )}
    </div>
  );
}
