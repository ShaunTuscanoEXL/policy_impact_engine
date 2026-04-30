"use client";

import Link from "next/link";
import { CheckCircle2, Lock, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";
import type { StageAccent, StageStatus } from "./pipeline-stage-card";

export interface ProgressStrip {
  stepNumber: number;
  title: string;
  status: StageStatus;
  accent: StageAccent;
  /** Anchor id on the page to scroll to when the strip is clicked. */
  anchorId: string;
  /** Optional deep-link to the corresponding detail page (e.g.
   *  /rules/{id}?from_brd=…) — when set, clicking the pill navigates
   *  away. When omitted, pill smooth-scrolls to the anchor on this page. */
  deepLink?: string;
}

interface PipelineProgressStripProps {
  steps: ProgressStrip[];
  /** 1-indexed current/active step. */
  current: number;
}

const ACCENT_BG: Record<StageAccent, string> = {
  blue: "bg-blue-500",
  cyan: "bg-cyan-500",
  violet: "bg-violet-500",
  amber: "bg-amber-500",
  rose: "bg-rose-500",
  fuchsia: "bg-fuchsia-500",
  emerald: "bg-emerald-500",
  slate: "bg-slate-500",
};

/**
 * Horizontal strip of step pills, one per stage. Visually summarizes
 * "where you are" in the BRD pipeline at a glance and lets the operator
 * jump (smooth-scroll) to any stage card by clicking its pill.
 */
export function PipelineProgressStrip({
  steps,
  current,
}: PipelineProgressStripProps) {
  const completedCount = steps.filter((s) => s.status === "completed").length;
  const totalCount = steps.length;
  const overallPct = (completedCount / totalCount) * 100;

  const handleJump = (anchorId: string) => {
    if (typeof document === "undefined") return;
    const el = document.getElementById(anchorId);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  };

  return (
    <div className="space-y-3">
      {/* The pill row — each pill is either a Link (deep-link to the
          detail page when one exists) or a button (smooth-scroll to the
          anchor on this page when no detail page applies).

          Visual hierarchy: completed pills get a subtle emerald tint,
          the single active pill is the visual anchor (filled accent
          background + crisp ring + accent number badge), and pending
          pills fade back so the eye is drawn to the active one. */}
      <ol className="flex items-stretch gap-1 overflow-x-auto pb-1">
        {steps.map((s, idx) => {
          const isCurrent = s.stepNumber === current;
          const isCompleted = s.status === "completed";
          const isPending = s.status === "pending" || s.status === "blocked";

          const innerContent = (
            <>
              {/* Filled bar at top — always rendered so the pills
                  align visually; opacity drops for pending. */}
              <div
                className={cn(
                  "absolute inset-x-0 top-0 h-0.5",
                  isCompleted
                    ? "bg-emerald-500"
                    : isCurrent
                      ? ACCENT_BG[s.accent]
                      : "bg-border/30",
                )}
              />
              <div className="flex items-center gap-1.5">
                {/* Step number / icon */}
                <span
                  className={cn(
                    "flex size-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold tabular-nums shadow-sm transition-transform",
                    isCompleted
                      ? "bg-emerald-500 text-white"
                      : isCurrent
                        ? cn(
                            "text-white scale-110",
                            ACCENT_BG[s.accent],
                            "ring-2 ring-background",
                          )
                        : "bg-muted/60 text-muted-foreground/70 shadow-none",
                  )}
                >
                  {isCompleted ? (
                    <CheckCircle2 className="size-3" />
                  ) : s.status === "blocked" ? (
                    <Lock className="size-2.5" />
                  ) : (
                    s.stepNumber
                  )}
                </span>
                <span
                  className={cn(
                    "truncate text-[10px] font-semibold uppercase tracking-wider",
                    isCurrent
                      ? "text-foreground"
                      : isCompleted
                        ? "text-emerald-700 dark:text-emerald-300"
                        : "text-muted-foreground/70",
                  )}
                >
                  {s.title}
                </span>
                {s.deepLink && !isCurrent && (
                  <ExternalLink className="ml-auto size-2.5 shrink-0 text-muted-foreground/40 transition-opacity group-hover:text-foreground" />
                )}
              </div>
            </>
          );

          const className = cn(
            "group relative block w-full overflow-hidden rounded-lg px-2.5 py-2 text-left transition-all",
            isCurrent &&
              "bg-card ring-2 ring-inset shadow-md scale-[1.02]",
            isCompleted &&
              !isCurrent &&
              "bg-emerald-500/[0.05] hover:bg-emerald-500/[0.10] hover:shadow-sm",
            isPending && "bg-muted/20 opacity-50 hover:opacity-75",
          );

          // Active pill needs the matching accent ring color
          const currentRingStyle = isCurrent
            ? { boxShadow: undefined }
            : undefined;
          const currentRingClass = isCurrent
            ? cn("ring-foreground/20")
            : "";

          return (
            <li key={s.stepNumber} className="flex-1 min-w-0">
              {s.deepLink ? (
                <Link
                  href={s.deepLink}
                  className={cn(className, currentRingClass)}
                  style={currentRingStyle}
                  title={s.title}
                >
                  {innerContent}
                </Link>
              ) : (
                <button
                  type="button"
                  onClick={() => handleJump(s.anchorId)}
                  className={cn(className, currentRingClass)}
                  style={currentRingStyle}
                  title={s.title}
                >
                  {innerContent}
                </button>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
