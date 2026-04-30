"use client";

import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import {
  FileText,
  Layers,
  GitMerge,
  GitBranch,
  Activity,
  FlaskConical,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { DashboardPipelineCounters } from "@/lib/types";

interface PipelineFunnelProps {
  counters: DashboardPipelineCounters;
}

interface Stage {
  key: keyof DashboardPipelineCounters;
  label: string;
  href: string;
  icon: typeof FileText;
  iconBg: string;
  iconColor: string;
  ringColor: string;
}

const STAGES: Stage[] = [
  {
    key: "brds_uploaded",
    label: "BRDs",
    href: "/brds",
    icon: FileText,
    iconBg: "bg-blue-500/10",
    iconColor: "text-blue-600 dark:text-blue-400",
    ringColor: "ring-blue-500/20",
  },
  {
    key: "rules_extracted",
    label: "Rules Extracted",
    href: "/brds",
    icon: Layers,
    iconBg: "bg-cyan-500/10",
    iconColor: "text-cyan-600 dark:text-cyan-400",
    ringColor: "ring-cyan-500/20",
  },
  {
    key: "merge_proposals",
    label: "Merge Proposals",
    href: "/merge-workbench",
    icon: GitMerge,
    iconBg: "bg-violet-500/10",
    iconColor: "text-violet-600 dark:text-violet-400",
    ringColor: "ring-violet-500/20",
  },
  {
    key: "live_versions",
    label: "Live Versions",
    href: "/live-repo",
    icon: GitBranch,
    iconBg: "bg-amber-500/10",
    iconColor: "text-amber-600 dark:text-amber-400",
    ringColor: "ring-amber-500/20",
  },
  {
    key: "impact_runs",
    label: "Impact Runs",
    href: "/impact-runs",
    icon: Activity,
    iconBg: "bg-rose-500/10",
    iconColor: "text-rose-600 dark:text-rose-400",
    ringColor: "ring-rose-500/20",
  },
  {
    key: "test_executions",
    label: "Suite Runs",
    href: "/test-suites",
    icon: FlaskConical,
    iconBg: "bg-fuchsia-500/10",
    iconColor: "text-fuchsia-600 dark:text-fuchsia-400",
    ringColor: "ring-fuchsia-500/20",
  },
];

/**
 * Horizontal pipeline visualization showing the BRD → Impact funnel
 * with live counters at each stage. Each stage is clickable. The
 * dashboard's most powerful "what does this product DO?" element.
 */
export function PipelineFunnel({ counters }: PipelineFunnelProps) {
  const max = Math.max(...STAGES.map((s) => counters[s.key]), 1);

  return (
    <Card className="card-elevated border-border/40 overflow-hidden">
      <CardContent className="p-5">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold tracking-tight">Policy Lifecycle</h3>
            <p className="text-xs text-muted-foreground">
              From source documents to validated impact in production
            </p>
          </div>
        </div>
        <div className="flex items-stretch gap-2 overflow-x-auto pb-1">
          {STAGES.map((stage, idx) => {
            const value = counters[stage.key];
            const widthPct = Math.max(8, Math.round((value / max) * 100));
            return (
              <div key={stage.key} className="flex flex-1 items-center gap-2">
                <Link
                  href={stage.href}
                  className={cn(
                    "group relative flex-1 rounded-xl border border-border/50 bg-card/40 p-3",
                    "transition-all duration-200 hover:border-foreground/20 hover:bg-card hover:shadow-sm",
                  )}
                >
                  <div className="mb-2 flex items-center gap-2">
                    <div
                      className={cn(
                        "flex size-7 shrink-0 items-center justify-center rounded-lg ring-1 ring-inset",
                        stage.iconBg,
                        stage.ringColor,
                      )}
                    >
                      <stage.icon className={cn("size-3.5", stage.iconColor)} />
                    </div>
                    <span className="truncate text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                      {stage.label}
                    </span>
                  </div>
                  <div className="font-mono text-2xl font-bold tabular-nums text-foreground">
                    {value.toLocaleString()}
                  </div>
                  <div className="mt-2 h-1 overflow-hidden rounded-full bg-muted/50">
                    <div
                      className={cn(
                        "h-full rounded-full bg-gradient-to-r transition-all duration-500",
                        stage.iconColor.replace("text-", "from-"),
                        stage.iconColor.replace("text-", "to-"),
                      )}
                      style={{ width: `${widthPct}%` }}
                    />
                  </div>
                </Link>
                {idx < STAGES.length - 1 && (
                  <ChevronRight className="size-4 shrink-0 text-muted-foreground/40" />
                )}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
