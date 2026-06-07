import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Lightweight CSS tooltip: shows a label on hover or keyboard focus of its child.
 * Avoids pulling in a popover dependency for simple icon-button hints.
 */
export function Tooltip({
  label,
  side = "bottom",
  children,
}: {
  label: string;
  side?: "top" | "bottom";
  children: React.ReactNode;
}) {
  return (
    <span className="group relative inline-flex">
      {children}
      <span
        role="tooltip"
        className={cn(
          "pointer-events-none absolute left-1/2 z-50 -translate-x-1/2 whitespace-nowrap rounded-md border bg-popover px-2 py-1 text-xs text-popover-foreground opacity-0 shadow-md transition-opacity group-hover:opacity-100 group-focus-within:opacity-100",
          side === "bottom" ? "top-full mt-1.5" : "bottom-full mb-1.5"
        )}
      >
        {label}
      </span>
    </span>
  );
}
