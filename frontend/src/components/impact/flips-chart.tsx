"use client";

import { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ArrowRight, Repeat } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ImpactRunSummary } from "@/lib/types";

interface FlipsChartProps {
  summary: ImpactRunSummary;
}

const STATE_STYLES: Record<string, { chip: string; dot: string; bar: string }> = {
  APPROVED: {
    chip: "bg-emerald-500/10 text-emerald-700 ring-emerald-500/30 dark:text-emerald-300",
    dot: "bg-emerald-500",
    bar: "bg-emerald-500",
  },
  FLAGGED: {
    chip: "bg-amber-500/10 text-amber-700 ring-amber-500/30 dark:text-amber-300",
    dot: "bg-amber-500",
    bar: "bg-amber-500",
  },
  REJECTED: {
    chip: "bg-red-500/10 text-red-700 ring-red-500/30 dark:text-red-400",
    dot: "bg-red-500",
    bar: "bg-red-500",
  },
};

function defaultStyle(_state: string) {
  return {
    chip: "bg-slate-500/10 text-slate-700 ring-slate-500/30 dark:text-slate-300",
    dot: "bg-slate-500",
    bar: "bg-slate-500",
  };
}

function styleFor(state: string) {
  return STATE_STYLES[state] ?? defaultStyle(state);
}

interface Transition {
  key: string;
  from: string;
  to: string;
  count: number;
  pct: number;
}

export function FlipsChart({ summary }: FlipsChartProps) {
  const transitions: Transition[] = useMemo(() => {
    const flips = summary.decision_flips ?? {};
    const totalFlips = Object.values(flips).reduce((a, n) => a + n, 0);
    return Object.entries(flips)
      .map(([key, count]) => {
        const parts = key.toUpperCase().split("_TO_");
        return {
          key,
          from: parts[0] ?? key,
          to: parts[1] ?? "—",
          count,
          pct: totalFlips > 0 ? (count / totalFlips) * 100 : 0,
        };
      })
      .sort((a, b) => b.count - a.count);
  }, [summary]);

  const totalFlips = transitions.reduce((a, t) => a + t.count, 0);

  return (
    <Card className="card-elevated overflow-hidden border-border/50">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base">
            <span className="rounded-md bg-rose-500/10 p-1.5 ring-1 ring-inset ring-rose-500/20">
              <Repeat className="size-4 text-rose-600 dark:text-rose-400" />
            </span>
            Decision Flips
          </CardTitle>
          <Badge variant="outline" className="text-[11px]">
            {totalFlips.toLocaleString()} loans changed decision
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="pt-2">
        {transitions.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 py-12 text-center">
            <div className="rounded-full bg-emerald-500/10 p-3 ring-1 ring-inset ring-emerald-500/20">
              <Repeat className="size-5 text-emerald-600 dark:text-emerald-400" />
            </div>
            <p className="text-sm font-medium">No decision flips</p>
            <p className="text-xs text-muted-foreground">
              Both versions produced identical decisions on every loan.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {transitions.map((t) => {
              const fromStyle = styleFor(t.from);
              const toStyle = styleFor(t.to);
              return (
                <div
                  key={t.key}
                  className="group rounded-lg border border-border/50 bg-muted/20 p-4 transition-colors hover:bg-muted/40"
                >
                  <div className="flex items-center justify-between gap-4">
                    <div className="flex flex-1 items-center gap-3">
                      <div
                        className={cn(
                          "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset",
                          fromStyle.chip
                        )}
                      >
                        <span className={cn("size-1.5 rounded-full", fromStyle.dot)} />
                        {t.from}
                      </div>
                      <ArrowRight className="size-4 shrink-0 text-muted-foreground/50 transition-transform group-hover:translate-x-0.5" />
                      <div
                        className={cn(
                          "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset",
                          toStyle.chip
                        )}
                      >
                        <span className={cn("size-1.5 rounded-full", toStyle.dot)} />
                        {t.to}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-mono text-xl font-bold tracking-tight">
                        {t.count.toLocaleString()}
                      </div>
                      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
                        {t.pct.toFixed(1)}% of flips
                      </div>
                    </div>
                  </div>
                  {/* Progress bar showing this transition's share of total flips */}
                  <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-border/40">
                    <div
                      className={cn("h-full rounded-full transition-all", toStyle.bar)}
                      style={{ width: `${Math.max(t.pct, 4)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
