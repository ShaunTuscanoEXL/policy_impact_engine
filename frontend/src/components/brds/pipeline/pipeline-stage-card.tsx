"use client";

import { useState, type ReactNode } from "react";
import {
  CheckCircle2,
  Circle,
  Loader2,
  Lock,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
} from "lucide-react";
import { cn } from "@/lib/utils";

export type StageStatus = "completed" | "active" | "pending" | "blocked";

export type StageAccent =
  | "blue"
  | "cyan"
  | "violet"
  | "amber"
  | "rose"
  | "fuchsia"
  | "emerald"
  | "slate";

interface PipelineStageCardProps {
  /** 1-indexed stage number rendered in the corner badge. */
  stepNumber: number;
  /** Stage name ("Extract Rules"). */
  title: string;
  /** Subtitle / one-line description shown beside the title. */
  subtitle?: string;
  /** Status — drives the icon, color treatment, and default expansion. */
  status: StageStatus;
  /** Color family for the active state highlight + step badge. */
  accent: StageAccent;
  /** Right-side metric chip ("13 rules" / "v2 applied" / "100% pass"). */
  metric?: ReactNode;
  /** Body content — preview, form, results, etc. */
  children?: ReactNode;
  /** Action area pinned to the bottom of an active card. */
  cta?: ReactNode;
  /** Used for the URL anchor + auto-scroll target. */
  anchorId?: string;
  /** Force expand on mount even if status would normally collapse it. */
  defaultExpanded?: boolean;
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

const ACCENT_TEXT: Record<StageAccent, string> = {
  blue: "text-blue-600 dark:text-blue-400",
  cyan: "text-cyan-600 dark:text-cyan-400",
  violet: "text-violet-600 dark:text-violet-400",
  amber: "text-amber-600 dark:text-amber-400",
  rose: "text-rose-600 dark:text-rose-400",
  fuchsia: "text-fuchsia-600 dark:text-fuchsia-400",
  emerald: "text-emerald-600 dark:text-emerald-400",
  slate: "text-slate-600 dark:text-slate-400",
};

const ACCENT_RING: Record<StageAccent, string> = {
  blue: "ring-blue-500/30",
  cyan: "ring-cyan-500/30",
  violet: "ring-violet-500/30",
  amber: "ring-amber-500/30",
  rose: "ring-rose-500/30",
  fuchsia: "ring-fuchsia-500/30",
  emerald: "ring-emerald-500/30",
  slate: "ring-slate-500/30",
};

const ACCENT_TINT_BG: Record<StageAccent, string> = {
  blue: "bg-blue-500/[0.04]",
  cyan: "bg-cyan-500/[0.04]",
  violet: "bg-violet-500/[0.04]",
  amber: "bg-amber-500/[0.04]",
  rose: "bg-rose-500/[0.04]",
  fuchsia: "bg-fuchsia-500/[0.04]",
  emerald: "bg-emerald-500/[0.04]",
  slate: "bg-slate-500/[0.04]",
};

function StageStatusIcon({
  status,
  accent,
}: {
  status: StageStatus;
  accent: StageAccent;
}) {
  if (status === "completed") {
    return <CheckCircle2 className="size-5 text-emerald-500" />;
  }
  if (status === "active") {
    return (
      <div className="relative">
        <div
          className={cn(
            "absolute inset-0 size-5 animate-ping rounded-full opacity-30",
            ACCENT_BG[accent],
          )}
        />
        <div
          className={cn(
            "relative flex size-5 items-center justify-center rounded-full",
            ACCENT_BG[accent],
          )}
        >
          <Loader2 className="size-3 animate-spin text-white" />
        </div>
      </div>
    );
  }
  if (status === "blocked") {
    return <Lock className="size-5 text-muted-foreground/50" />;
  }
  return <Circle className="size-5 text-muted-foreground/30" />;
}

/**
 * One stage in the BRD pipeline. Renders a number badge, status icon,
 * title + subtitle, optional metric chip, and an expandable body. Active
 * stages auto-expand and visually highlight; completed stages collapse
 * to a compact summary by default but can be re-opened.
 */
export function PipelineStageCard({
  stepNumber,
  title,
  subtitle,
  status,
  accent,
  metric,
  children,
  cta,
  anchorId,
  defaultExpanded,
}: PipelineStageCardProps) {
  // Active stages always expanded; completed default-collapsed; pending
  // stays collapsed (no body to show).
  const initiallyOpen =
    defaultExpanded ?? (status === "active" || status === "blocked");
  const [open, setOpen] = useState(initiallyOpen);
  const hasBody = !!children || !!cta;

  return (
    <section
      id={anchorId}
      className={cn(
        "group relative overflow-hidden rounded-2xl border transition-all",
        status === "active"
          ? cn(
              "border-2 shadow-lg",
              ACCENT_RING[accent].replace("ring-", "border-"),
              ACCENT_TINT_BG[accent],
            )
          : status === "completed"
            ? "border-border/50 bg-card/60"
            : "border-dashed border-border/40 bg-muted/20",
      )}
    >
      {/* Top accent strip for active stages */}
      {status === "active" && (
        <div className={cn("h-1 w-full", ACCENT_BG[accent])} />
      )}

      {/* Header */}
      <button
        type="button"
        onClick={() => hasBody && setOpen((o) => !o)}
        disabled={!hasBody}
        className={cn(
          "flex w-full items-start gap-4 px-5 py-4 text-left transition-colors",
          hasBody && "hover:bg-accent/30",
          !hasBody && "cursor-default",
        )}
      >
        {/* Step number badge */}
        <div
          className={cn(
            "flex size-9 shrink-0 items-center justify-center rounded-xl font-mono text-sm font-bold ring-1 ring-inset",
            status === "completed"
              ? "bg-emerald-500/10 text-emerald-700 ring-emerald-500/30 dark:text-emerald-300"
              : status === "active"
                ? cn(
                    "text-white shadow-md",
                    ACCENT_BG[accent],
                    ACCENT_RING[accent],
                  )
                : "bg-muted/40 text-muted-foreground/60 ring-border/60",
          )}
        >
          {status === "completed" ? (
            <CheckCircle2 className="size-4" />
          ) : (
            stepNumber
          )}
        </div>

        {/* Title block */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3
              className={cn(
                "text-sm font-semibold tracking-tight",
                status === "completed" && "text-foreground",
                status === "active" && ACCENT_TEXT[accent],
                (status === "pending" || status === "blocked") &&
                  "text-muted-foreground",
              )}
            >
              {title}
            </h3>
            <StageStatusIcon status={status} accent={accent} />
          </div>
          {subtitle && (
            <p className="mt-0.5 text-xs text-muted-foreground">{subtitle}</p>
          )}
        </div>

        {/* Right side: metric + chevron */}
        <div className="flex shrink-0 items-center gap-2">
          {metric && (
            <div className="text-xs font-medium text-muted-foreground">
              {metric}
            </div>
          )}
          {hasBody && (
            <span className="text-muted-foreground/40">
              {open ? (
                <ChevronUp className="size-4" />
              ) : (
                <ChevronDown className="size-4" />
              )}
            </span>
          )}
        </div>
      </button>

      {/* Body */}
      {hasBody && open && (
        <div className="border-t border-border/40 px-5 py-4 space-y-3">
          {children}
          {cta && (
            <div className="flex flex-wrap items-center gap-2 pt-1">
              {cta}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

/**
 * Convenience pill for the metric slot — colored by status. Bumped to
 * a slightly larger/ringed treatment so it reads at a glance from the
 * right side of the stage header even when many stages are collapsed.
 */
export function StageMetric({
  label,
  tone = "default",
}: {
  label: string;
  tone?: "default" | "success" | "warning" | "danger" | "info";
}) {
  const toneClass: Record<string, string> = {
    default: "bg-muted/60 text-muted-foreground ring-border/60",
    success:
      "bg-emerald-500/15 text-emerald-700 ring-emerald-500/30 dark:text-emerald-300",
    warning:
      "bg-amber-500/15 text-amber-700 ring-amber-500/30 dark:text-amber-300",
    danger:
      "bg-rose-500/15 text-rose-700 ring-rose-500/30 dark:text-rose-300",
    info: "bg-blue-500/15 text-blue-700 ring-blue-500/30 dark:text-blue-300",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-mono font-semibold tabular-nums ring-1 ring-inset",
        toneClass[tone],
      )}
    >
      {tone === "warning" && <AlertTriangle className="size-3.5" />}
      {label}
    </span>
  );
}
