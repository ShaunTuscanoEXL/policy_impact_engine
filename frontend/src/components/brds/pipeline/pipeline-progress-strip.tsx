"use client";

import { CheckCircle2, Lock } from "lucide-react";
import { cn } from "@/lib/utils";
import type { StageAccent, StageStatus } from "./pipeline-stage-card";

export interface ProgressStrip {
  stepNumber: number;
  title: string;
  status: StageStatus;
  accent: StageAccent;
  /** Anchor id on the page to scroll to when the strip is clicked. */
  anchorId: string;
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
      {/* Counter line */}
      <div className="flex items-baseline justify-between">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Pipeline progress
        </p>
        <p className="font-mono text-xs text-muted-foreground tabular-nums">
          <span className="text-base font-bold text-foreground">
            {completedCount}
          </span>
          <span className="mx-0.5 opacity-60">/</span>
          {totalCount} stages complete
          <span className="ml-2 inline-block rounded-full bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700 dark:text-emerald-300">
            {Math.round(overallPct)}%
          </span>
        </p>
      </div>

      {/* The pill row */}
      <ol className="flex items-stretch gap-1.5 overflow-x-auto pb-1">
        {steps.map((s, idx) => {
          const isCurrent = s.stepNumber === current;
          const isCompleted = s.status === "completed";
          const isPending =
            s.status === "pending" || s.status === "blocked";
          return (
            <li key={s.stepNumber} className="flex-1 min-w-0">
              <button
                type="button"
                onClick={() => handleJump(s.anchorId)}
                className={cn(
                  "group relative w-full overflow-hidden rounded-lg px-2 py-2 text-left transition-all",
                  isCurrent &&
                    "bg-card shadow-sm ring-2 ring-inset ring-foreground/10",
                  isCompleted && !isCurrent && "bg-emerald-500/[0.06]",
                  isPending && "bg-muted/30 opacity-60",
                )}
                title={s.title}
              >
                {/* Filled bar at top */}
                <div
                  className={cn(
                    "absolute inset-x-0 top-0 h-0.5",
                    isCompleted
                      ? "bg-emerald-500"
                      : isCurrent
                        ? ACCENT_BG[s.accent]
                        : "bg-border/40",
                  )}
                />
                <div className="flex items-center gap-1.5">
                  {/* Step number / icon */}
                  <span
                    className={cn(
                      "flex size-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold tabular-nums",
                      isCompleted
                        ? "bg-emerald-500 text-white"
                        : isCurrent
                          ? cn("text-white", ACCENT_BG[s.accent])
                          : "bg-muted/60 text-muted-foreground/70",
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
                      isCurrent ? "text-foreground" : "text-muted-foreground",
                    )}
                  >
                    {s.title}
                  </span>
                </div>
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
