"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PieChart, TrendingUp, TrendingDown, Minus } from "lucide-react";
import type { ImpactRunSummary } from "@/lib/types";

interface SegmentTableProps {
  summary: ImpactRunSummary;
}

/** Per-risk-segment table — shows base vs candidate approval rate +
 * delta + qualitative impact rating. Inspired by master's SegmentTable
 * (their tabs were per-segmentation-axis; we have just risk_segment
 * today, so we render a flat table). */
export function SegmentTable({ summary }: SegmentTableProps) {
  const segments = Object.entries(summary.by_segment ?? {})
    .map(([name, info]) => ({ name, ...info }))
    .sort((a, b) => b.loans - a.loans);

  return (
    <Card className="card-elevated border-border/40">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <PieChart className="size-5 text-amber-500" />
          By Risk Segment
        </CardTitle>
      </CardHeader>
      <CardContent>
        {segments.length === 0 ? (
          <p className="py-8 text-center text-sm italic text-muted-foreground">
            No segment data in this run.
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-amber-500/20">
                  Segment
                </TableHead>
                <TableHead className="text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-amber-500/20">
                  Loans
                </TableHead>
                <TableHead className="text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-amber-500/20">
                  Base Approval
                </TableHead>
                <TableHead className="text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-amber-500/20">
                  Cand. Approval
                </TableHead>
                <TableHead className="text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-amber-500/20">
                  Δ
                </TableHead>
                <TableHead className="text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-amber-500/20">
                  Impact
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {segments.map((s) => {
                const delta = s.approval_rate_change;
                const TrendIcon =
                  delta > 0 ? TrendingUp : delta < 0 ? TrendingDown : Minus;
                const trendColor =
                  delta > 0
                    ? "text-green-600"
                    : delta < 0
                      ? "text-red-600"
                      : "text-muted-foreground";
                const absDelta = Math.abs(delta);
                const impactLabel =
                  absDelta >= 0.10 ? "High" : absDelta >= 0.03 ? "Medium" : absDelta > 0 ? "Low" : "None";
                const impactColor =
                  absDelta >= 0.10
                    ? "text-red-600"
                    : absDelta >= 0.03
                      ? "text-amber-600"
                      : absDelta > 0
                        ? "text-blue-600"
                        : "text-muted-foreground";
                return (
                  <TableRow
                    key={s.name}
                    className="transition-colors duration-150 hover:bg-accent/50"
                  >
                    <TableCell className="font-medium">{s.name}</TableCell>
                    <TableCell className="text-right">
                      {s.loans.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right">
                      {(s.base_approval_rate * 100).toFixed(1)}%
                    </TableCell>
                    <TableCell className="text-right">
                      {(s.candidate_approval_rate * 100).toFixed(1)}%
                    </TableCell>
                    <TableCell className={`text-right ${trendColor}`}>
                      <span className="inline-flex items-center gap-1">
                        <TrendIcon className="size-3.5" />
                        {(delta * 100).toFixed(2)}%
                      </span>
                    </TableCell>
                    <TableCell className={`text-right font-medium ${impactColor}`}>
                      {impactLabel}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
