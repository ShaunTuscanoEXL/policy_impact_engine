"use client";

import {
  Layers,
  GitMerge,
  GitBranch,
  FlaskConical,
  Activity,
  Check,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface DownstreamFlowChipsProps {
  hasRules: boolean;
  hasMergeProposal: boolean;
  isMergedIntoRepo: boolean;
  hasTestSuite: boolean;
  hasExecutedTestSuite: boolean;
  /** Compact (default) shows just dots; "labeled" shows tiny labels too. */
  variant?: "compact" | "labeled";
}

interface Stage {
  key: string;
  label: string;
  done: boolean;
  icon: typeof Check;
  doneColor: string;
}

/**
 * Five-dot progression strip showing where in the BRD → Impact funnel
 * a given BRD has gotten. Dots fill left-to-right as the BRD moves
 * downstream. Renders inline in the BRD list table.
 */
export function DownstreamFlowChips({
  hasRules,
  hasMergeProposal,
  isMergedIntoRepo,
  hasTestSuite,
  hasExecutedTestSuite,
  variant = "compact",
}: DownstreamFlowChipsProps) {
  const stages: Stage[] = [
    {
      key: "rules",
      label: "Rules",
      done: hasRules,
      icon: Layers,
      doneColor: "bg-cyan-500/15 text-cyan-600 ring-cyan-500/30 dark:text-cyan-400",
    },
    {
      key: "proposal",
      label: "Proposal",
      done: hasMergeProposal,
      icon: GitMerge,
      doneColor:
        "bg-violet-500/15 text-violet-600 ring-violet-500/30 dark:text-violet-400",
    },
    {
      key: "merged",
      label: "Merged",
      done: isMergedIntoRepo,
      icon: GitBranch,
      doneColor:
        "bg-amber-500/15 text-amber-600 ring-amber-500/30 dark:text-amber-400",
    },
    {
      key: "suite",
      label: "Suite",
      done: hasTestSuite,
      icon: FlaskConical,
      doneColor:
        "bg-fuchsia-500/15 text-fuchsia-600 ring-fuchsia-500/30 dark:text-fuchsia-400",
    },
    {
      key: "executed",
      label: "Tested",
      done: hasExecutedTestSuite,
      icon: Activity,
      doneColor:
        "bg-rose-500/15 text-rose-600 ring-rose-500/30 dark:text-rose-400",
    },
  ];

  return (
    <div className="flex items-center gap-1" title="Downstream progression">
      {stages.map((s) => {
        const Icon = s.icon;
        return (
          <span
            key={s.key}
            className={cn(
              "inline-flex items-center gap-0.5 rounded-full ring-1 ring-inset transition-colors",
              variant === "compact" ? "px-1 py-0.5" : "px-1.5 py-0.5",
              s.done
                ? s.doneColor
                : "bg-muted/30 text-muted-foreground/40 ring-border/50",
            )}
            title={s.done ? `${s.label} ✓` : s.label}
          >
            <Icon className="size-3" />
            {variant === "labeled" && (
              <span className="text-[9px] font-semibold uppercase tracking-wider">
                {s.label}
              </span>
            )}
          </span>
        );
      })}
    </div>
  );
}
