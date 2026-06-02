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
  /** Short copy explaining why a pending stage isn't actionable yet
   *  ("Available after Stage 4"). */
  pendingReason?: string;
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

const ACCENT_GLOW: Record<StageAccent, string> = {
  blue: "shadow-[0_0_0_1px_rgb(59_130_246/0.4),0_8px_30px_-8px_rgb(59_130_246/0.35)]",
  cyan: "shadow-[0_0_0_1px_rgb(6_182_212/0.4),0_8px_30px_-8px_rgb(6_182_212/0.35)]",
  violet:
    "shadow-[0_0_0_1px_rgb(139_92_246/0.4),0_8px_30px_-8px_rgb(139_92_246/0.35)]",
  amber: "shadow-[0_0_0_1px_rgb(245_158_11/0.4),0_8px_30px_-8px_rgb(245_158_11/0.35)]",
  rose: "shadow-[0_0_0_1px_rgb(244_63_94/0.4),0_8px_30px_-8px_rgb(244_63_94/0.35)]",
  fuchsia:
    "shadow-[0_0_0_1px_rgb(217_70_239/0.4),0_8px_30px_-8px_rgb(217_70_239/0.35)]",
  emerald:
    "shadow-[0_0_0_1px_rgb(16_185_129/0.4),0_8px_30px_-8px_rgb(16_185_129/0.35)]",
  slate: "shadow-[0_0_0_1px_rgb(100_116_139/0.4),0_8px_30px_-8px_rgb(100_116_139/0.35)]",
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

/**
 * One stage in the BRD pipeline. Renders as a node on the vertical
 * journey rail, with status-aware visual treatment:
 *
 *   - **completed**: compact card, emerald checkmark, click to expand
 *     for retrospective body content
 *   - **active**: glowing card with colored top strip + pulse animation
 *     on the rail node, body always expanded with inline CTAs
 *   - **pending**: dimmed card with lock icon and "available after"
 *     explainer copy
 *
 * The parent renders a continuous left-side rail; this card aligns its
 * 9px node circle to the rail (left: -22px relative).
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
  pendingReason,
}: PipelineStageCardProps) {
  const initiallyOpen =
    defaultExpanded ?? (status === "active" || status === "blocked");
  const [open, setOpen] = useState(initiallyOpen);
  const hasBody = !!children || !!cta;
  const isCompleted = status === "completed";
  const isActive = status === "active";
  const isPending = status === "pending";

  return (
    <section id={anchorId} className="relative">
      {/* Rail node — sits on the left rail, perfectly aligned */}
      <div
        className={cn(
          "absolute left-[-30px] top-5 z-10 flex size-4 items-center justify-center rounded-full ring-4 transition-all",
          isCompleted &&
            "bg-emerald-500 ring-background dark:ring-background",
          isActive &&
            cn(
              "ring-background dark:ring-background",
              ACCENT_BG[accent],
              "shadow-md",
            ),
          isPending && "bg-muted-foreground/30 ring-background",
        )}
      >
        {isActive && (
          <span
            className={cn(
              "absolute inline-flex size-full animate-ping rounded-full opacity-50",
              ACCENT_BG[accent],
            )}
          />
        )}
        {isCompleted && (
          <CheckCircle2 className="size-2.5 text-white relative" />
        )}
        {isActive && (
          <span className="size-1.5 rounded-full bg-white relative" />
        )}
        {isPending && (
          <Lock className="size-2 text-background relative" />
        )}
      </div>

      <article
        className={cn(
          "group overflow-hidden rounded-2xl border transition-all",
          isActive
            ? cn(
                "border-2",
                ACCENT_GLOW[accent].split(" ").pop()
                  ? ACCENT_GLOW[accent]
                  : "shadow-lg",
                ACCENT_TINT_BG[accent],
                "border-current/30",
              )
            : isCompleted
              ? "border-border/50 bg-card hover:border-foreground/30 hover:shadow-sm"
              : "border-dashed border-border/40 bg-muted/[0.15] opacity-75",
        )}
        style={
          isActive
            ? { borderColor: getAccentBorderColor(accent) }
            : undefined
        }
      >
        {/* Top accent strip for active stages */}
        {isActive && (
          <div className={cn("h-1 w-full", ACCENT_BG[accent])} />
        )}

        {/* Header */}
        <button
          type="button"
          onClick={() => hasBody && setOpen((o) => !o)}
          disabled={!hasBody}
          className={cn(
            "flex w-full items-start gap-4 px-5 py-4 text-left transition-colors",
            hasBody && "hover:bg-foreground/[0.02]",
            !hasBody && "cursor-default",
          )}
        >
          {/* Step number badge */}
          <div
            className={cn(
              "flex size-9 shrink-0 items-center justify-center rounded-xl font-mono text-sm font-bold ring-1 ring-inset",
              isCompleted &&
                "bg-emerald-500/10 text-emerald-700 ring-emerald-500/30 dark:text-emerald-300",
              isActive &&
                cn("text-white shadow-md", ACCENT_BG[accent], "ring-white/20"),
              isPending && "bg-muted/40 text-muted-foreground/60 ring-border/60",
            )}
          >
            {isCompleted ? <CheckCircle2 className="size-4" /> : stepNumber}
          </div>

          {/* Title block */}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h3
                className={cn(
                  "text-sm font-semibold tracking-tight",
                  isCompleted && "text-foreground",
                  isActive && ACCENT_TEXT[accent],
                  isPending && "text-muted-foreground",
                )}
              >
                {title}
              </h3>
              {isActive && (
                <span
                  className={cn(
                    "inline-flex h-1.5 w-1.5 animate-pulse rounded-full",
                    ACCENT_BG[accent],
                  )}
                  aria-hidden
                />
              )}
            </div>
            {subtitle && (
              <p className="mt-0.5 text-xs text-muted-foreground">{subtitle}</p>
            )}
            {/* Lock copy only when truly waiting — if a metric chip is
                already conveying queued state (e.g. ACTION REQUIRED),
                the lock + "available after X" copy contradicts it. */}
            {isPending && pendingReason && !metric && (
              <p className="mt-1 inline-flex items-center gap-1 text-[10px] font-medium text-muted-foreground/70">
                <Lock className="size-2.5" />
                {pendingReason}
              </p>
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
              <span
                className={cn(
                  "text-muted-foreground/40 transition-colors",
                  isCompleted && "group-hover:text-foreground",
                )}
                title={open ? "Collapse" : "Expand for details"}
              >
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
              <div className="flex flex-wrap items-center gap-2 pt-1">{cta}</div>
            )}
          </div>
        )}
      </article>
    </section>
  );
}

function getAccentBorderColor(accent: StageAccent): string {
  const map: Record<StageAccent, string> = {
    blue: "rgb(59 130 246 / 0.5)",
    cyan: "rgb(6 182 212 / 0.5)",
    violet: "rgb(139 92 246 / 0.5)",
    amber: "rgb(245 158 11 / 0.5)",
    rose: "rgb(244 63 94 / 0.5)",
    fuchsia: "rgb(217 70 239 / 0.5)",
    emerald: "rgb(16 185 129 / 0.5)",
    slate: "rgb(100 116 139 / 0.5)",
  };
  return map[accent];
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
    danger: "bg-rose-500/15 text-rose-700 ring-rose-500/30 dark:text-rose-300",
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
