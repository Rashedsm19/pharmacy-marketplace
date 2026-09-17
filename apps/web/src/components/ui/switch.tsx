"use client";

import * as SwitchPrimitive from "@radix-ui/react-switch";
import { cn } from "@/lib/utils";

export function Switch({ className, ...props }: React.ComponentPropsWithoutRef<typeof SwitchPrimitive.Root>) {
  return (
    <SwitchPrimitive.Root
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full bg-[#d9c9b5] transition-colors data-[state=checked]:bg-brand-600 disabled:opacity-60",
        className
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb className="block h-5 w-5 rounded-full bg-white shadow-soft transition-transform translate-x-[-2px] data-[state=checked]:translate-x-[-22px]" />
    </SwitchPrimitive.Root>
  );
}
