"use client";

import { CheckCircle2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface ProductionBadgeProps {
  /** Show as a small chip (default) or a bigger pill for hero placements. */
  size?: "sm" | "md";
  /** Optional class to extend the chip (e.g. add an extra ring). */
  className?: string;
  /** Optional override label for non-standard contexts ("LIVE", "ACTIVE"). */
  label?: string;
  /** Slice 1 — promotion attribution. When provided, the chip's hover
   *  tooltip shows "Promoted by X on Y · 'rationale'" so reviewers can
   *  see who put this version in production without leaving the page. */
  promotedBy?: string | null;
  promotedAt?: string | null;
  rationale?: string | null;
}

/**
 * Visual marker for "this version is the one currently live in
 * production". Used everywhere a version_number is rendered so the
 * production version is unambiguous at a glance.
 */
export function ProductionBadge({
  size = "sm",
  className,
  label = "PRODUCTION",
  promotedBy,
  promotedAt,
  rationale,
}: ProductionBadgeProps) {
  const titleParts: string[] = ["This version is currently live in production"];
  if (promotedBy || promotedAt) {
    const when = promotedAt ? new Date(promotedAt).toLocaleString() : "";
    const who = promotedBy ? `Promoted by ${promotedBy}` : "Promoted";
    titleParts.push(`${who}${when ? ` on ${when}` : ""}`);
  }
  if (rationale) {
    titleParts.push(`Reason: ${rationale}`);
  }
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full font-bold uppercase tracking-wider ring-1 ring-inset",
        "bg-emerald-500/10 text-emerald-700 ring-emerald-500/30 dark:text-emerald-300 dark:ring-emerald-400/30",
        size === "sm"
          ? "px-1.5 py-0.5 text-[9px]"
          : "px-2.5 py-1 text-[11px] shadow-sm",
        className
      )}
      title={titleParts.join("\n")}
    >
      <CheckCircle2 className={cn(size === "sm" ? "size-2.5" : "size-3.5")} />
      {label}
    </span>
  );
}

/**
 * Pure helper — given a version number and a repo's production version
 * number, returns whether they match. Centralizes the comparison so
 * callers don't drift on null-vs-undefined handling.
 */
export function isProductionVersion(
  versionNumber: number | null | undefined,
  productionVersionNumber: number | null | undefined,
): boolean {
  return (
    versionNumber != null &&
    productionVersionNumber != null &&
    versionNumber === productionVersionNumber
  );
}
