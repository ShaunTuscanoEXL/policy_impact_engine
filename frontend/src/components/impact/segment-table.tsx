"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PieChart, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ImpactRunSummary } from "@/lib/types";

interface SegmentTableProps {
  summary: ImpactRunSummary;
}

const SEGMENT_TONE: Record<string, { bg: string; text: string }> = {
  SUPER_PRIME: {
    bg: "bg-emerald-500/10 ring-emerald-500/20",
    text: "text-emerald-700 dark:text-emerald-300",
  },
  PRIME: {
    bg: "bg-blue-500/10 ring-blue-500/20",
    text: "text-blue-700 dark:text-blue-300",
  },
  NEAR_PRIME: {
    bg: "bg-amber-500/10 ring-amber-500/20",
    text: "text-amber-700 dark:text-amber-300",
  },
  SUBPRIME: {
    bg: "bg-red-500/10 ring-red-500/20",
    text: "text-red-700 dark:text-red-300",
  },
  LOW_RISK: {
    bg: "bg-emerald-500/10 ring-emerald-500/20",
    text: "text-emerald-700 dark:text-emerald-300",
  },
  MEDIUM_RISK: {
    bg: "bg-amber-500/10 ring-amber-500/20",
    text: "text-amber-700 dark:text-amber-300",
  },
  HIGH_RISK: {
    bg: "bg-red-500/10 ring-red-500/20",
    text: "text-red-700 dark:text-red-300",
  },
};

function toneFor(name: string) {
  return (
    SEGMENT_TONE[name] ?? {
      bg: "bg-slate-500/10 ring-slate-500/20",
      text: "text-slate-700 dark:text-slate-300",
    }
  );
}

function RateBar({
  rate,
  color,
}: {
  rate: number;
  color: "slate" | "blue";
}) {
  const pct = Math.max(0, Math.min(1, rate)) * 100;
  return (
    <div className="flex items-center gap-2">
      <span className="font-mono text-xs">{(rate * 100).toFixed(1)}%</span>
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-border/40">
        <div
          className={cn(
            "h-full rounded-full",
            color === "blue" ? "bg-blue-500" : "bg-slate-400"
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function SegmentTable({ summary }: SegmentTableProps) {
  const segments = Object.entries(summary.by_segment ?? {})
    .map(([name, info]) => ({ name, ...info }))
    .sort((a, b) => b.loans - a.loans);

  const totalLoans = segments.reduce((a, s) => a + s.loans, 0);

  return (
    <Card className="card-elevated overflow-hidden border-border/50">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base">
            <span className="rounded-md bg-amber-500/10 p-1.5 ring-1 ring-inset ring-amber-500/20">
              <PieChart className="size-4 text-amber-600 dark:text-amber-400" />
            </span>
            By Risk Segment
          </CardTitle>
          {totalLoans > 0 && (
            <Badge variant="outline" className="text-[11px]">
              {totalLoans.toLocaleString()} total loans
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="pt-2">
        {segments.length === 0 ? (
          <p className="py-8 text-center text-sm italic text-muted-foreground">
            No segment data in this run.
          </p>
        ) : (
          <div className="overflow-hidden rounded-lg border border-border/40">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/30 hover:bg-muted/30">
                  <TableHead className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Segment
                  </TableHead>
                  <TableHead className="text-right text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Share
                  </TableHead>
                  <TableHead className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Base Approval
                  </TableHead>
                  <TableHead className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Cand. Approval
                  </TableHead>
                  <TableHead className="text-right text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Δ
                  </TableHead>
                  <TableHead className="text-right text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Impact
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {segments.map((s) => {
                  const tone = toneFor(s.name);
                  const delta = s.approval_rate_change;
                  const TrendIcon =
                    delta > 0 ? TrendingUp : delta < 0 ? TrendingDown : Minus;
                  const trendColor =
                    delta > 0
                      ? "text-emerald-600 dark:text-emerald-400"
                      : delta < 0
                        ? "text-red-600 dark:text-red-400"
                        : "text-muted-foreground";
                  const absDelta = Math.abs(delta);
                  const impactLabel =
                    absDelta >= 0.10
                      ? "High"
                      : absDelta >= 0.03
                        ? "Medium"
                        : absDelta > 0
                          ? "Low"
                          : "None";
                  const impactColor =
                    absDelta >= 0.10
                      ? "bg-red-500/10 text-red-700 ring-red-500/30 dark:text-red-400"
                      : absDelta >= 0.03
                        ? "bg-amber-500/10 text-amber-700 ring-amber-500/30 dark:text-amber-400"
                        : absDelta > 0
                          ? "bg-blue-500/10 text-blue-700 ring-blue-500/30 dark:text-blue-400"
                          : "bg-slate-500/10 text-slate-600 ring-slate-500/20 dark:text-slate-400";

                  const sharePct = totalLoans > 0 ? (s.loans / totalLoans) * 100 : 0;
                  return (
                    <TableRow
                      key={s.name}
                      className="transition-colors duration-150 hover:bg-accent/40"
                    >
                      <TableCell>
                        <span
                          className={cn(
                            "inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-semibold ring-1 ring-inset",
                            tone.bg,
                            tone.text
                          )}
                        >
                          {s.name.replace(/_/g, " ")}
                        </span>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="inline-flex items-baseline gap-1.5 font-mono text-xs">
                          <span className="font-medium">
                            {s.loans.toLocaleString()}
                          </span>
                          <span className="text-[10px] text-muted-foreground">
                            ({sharePct.toFixed(1)}%)
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <RateBar rate={s.base_approval_rate} color="slate" />
                      </TableCell>
                      <TableCell>
                        <RateBar
                          rate={s.candidate_approval_rate}
                          color="blue"
                        />
                      </TableCell>
                      <TableCell className="text-right">
                        <span
                          className={cn(
                            "inline-flex items-center gap-1 font-mono text-xs font-semibold",
                            trendColor
                          )}
                        >
                          <TrendIcon className="size-3.5" />
                          {delta === 0 ? "0.00" : `${(delta * 100).toFixed(2)}`}%
                        </span>
                      </TableCell>
                      <TableCell className="text-right">
                        <span
                          className={cn(
                            "inline-flex items-center rounded-md px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ring-1 ring-inset",
                            impactColor
                          )}
                        >
                          {impactLabel}
                        </span>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
