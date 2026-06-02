"use client";

import { useMemo } from "react";
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
import {
  CheckCircle,
  XCircle,
  AlertCircle,
  FlaskConical,
  Minus,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { SuiteExecutionResponse } from "@/lib/types";

interface SuiteExecutionPanelProps {
  report: SuiteExecutionResponse;
  executedAt: string | null;
  /** Slice 1 — surface attribution under the header so reviewers know
   *  who validated this version and the documented reason. */
  executedBy?: string | null;
  executionRationale?: string | null;
}

const CATEGORY_TONE: Record<string, { bg: string; text: string; label: string }> = {
  POSITIVE: { bg: "bg-emerald-500/10 ring-emerald-500/20", text: "text-emerald-700 dark:text-emerald-300", label: "Positive" },
  NEGATIVE: { bg: "bg-red-500/10 ring-red-500/20", text: "text-red-700 dark:text-red-300", label: "Negative" },
  BOUNDARY: { bg: "bg-amber-500/10 ring-amber-500/20", text: "text-amber-700 dark:text-amber-300", label: "Boundary" },
  EDGE: { bg: "bg-violet-500/10 ring-violet-500/20", text: "text-violet-700 dark:text-violet-300", label: "Edge" },
  INTERACTION: { bg: "bg-blue-500/10 ring-blue-500/20", text: "text-blue-700 dark:text-blue-300", label: "Interaction" },
};

function categoryTone(c: string) {
  return (
    CATEGORY_TONE[c] ?? {
      bg: "bg-slate-500/10 ring-slate-500/20",
      text: "text-slate-700 dark:text-slate-300",
      label: c,
    }
  );
}

function formatDistribution(actual: Record<string, number>) {
  const entries = Object.entries(actual)
    .filter(([, n]) => n > 0)
    .sort(([, a], [, b]) => b - a);
  if (entries.length === 0) return "—";
  return entries.map(([k, n]) => `${k}: ${n}`).join(" · ");
}

export function SuiteExecutionPanel({
  report,
  executedAt,
  executedBy,
  executionRationale,
}: SuiteExecutionPanelProps) {
  const { passed, failed, untested } = useMemo(() => {
    let p = 0;
    let f = 0;
    let u = 0;
    for (const r of report.results ?? []) {
      if (r.matched_loan_count === 0) {
        u += 1;
      } else if (r.deviates_from_expected === 0) {
        p += 1;
      } else {
        f += 1;
      }
    }
    return { passed: p, failed: f, untested: u };
  }, [report]);

  const totalEvaluated = report.summary?.matches_expected ?? 0;
  const totalDeviated = report.summary?.deviates_from_expected ?? 0;
  const totalLoans = totalEvaluated + totalDeviated;
  const passRate = totalLoans > 0 ? (totalEvaluated / totalLoans) * 100 : 0;

  return (
    <Card className="card-elevated overflow-hidden border-border/50">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base">
            <span className="rounded-md bg-fuchsia-500/10 p-1.5 ring-1 ring-inset ring-fuchsia-500/20">
              <FlaskConical className="size-4 text-fuchsia-600 dark:text-fuchsia-400" />
            </span>
            Scenario Test Execution
          </CardTitle>
          <div className="flex flex-col items-end gap-0.5">
            <div className="flex items-center gap-2">
              {report.version_number != null && (
                <Badge variant="outline" className="text-[11px]">
                  vs v{report.version_number}
                </Badge>
              )}
              {executedAt && (
                <span className="text-[11px] text-muted-foreground">
                  {new Date(executedAt).toLocaleString()}
                </span>
              )}
            </div>
            {executedBy && (
              <span
                className="text-[10px] text-muted-foreground"
                title={executionRationale || undefined}
              >
                Run by <span className="font-medium">{executedBy}</span>
                {executionRationale ? ` · "${executionRationale}"` : ""}
              </span>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-5 pt-2">
        {/* Hero summary row */}
        <div className="grid gap-3 sm:grid-cols-4">
          <div className="rounded-lg border border-border/40 bg-emerald-500/5 p-3">
            <div className="flex items-center gap-2 text-xs font-medium text-emerald-700 dark:text-emerald-400">
              <CheckCircle className="size-3.5" />
              Passing test cases
            </div>
            <div className="mt-1 font-mono text-2xl font-bold text-emerald-700 dark:text-emerald-300">
              {passed}
            </div>
          </div>
          <div className="rounded-lg border border-border/40 bg-red-500/5 p-3">
            <div className="flex items-center gap-2 text-xs font-medium text-red-700 dark:text-red-400">
              <XCircle className="size-3.5" />
              Failing test cases
            </div>
            <div className="mt-1 font-mono text-2xl font-bold text-red-700 dark:text-red-300">
              {failed}
            </div>
          </div>
          <div className="rounded-lg border border-border/40 bg-slate-500/5 p-3">
            <div className="flex items-center gap-2 text-xs font-medium text-slate-700 dark:text-slate-300">
              <Minus className="size-3.5" />
              No matched loans
            </div>
            <div className="mt-1 font-mono text-2xl font-bold text-slate-700 dark:text-slate-300">
              {untested}
            </div>
          </div>
          <div className="rounded-lg border border-border/40 bg-blue-500/5 p-3">
            <div className="flex items-center gap-2 text-xs font-medium text-blue-700 dark:text-blue-400">
              <FlaskConical className="size-3.5" />
              Loan-outcome match rate
            </div>
            <div className="mt-1 font-mono text-2xl font-bold text-blue-700 dark:text-blue-300">
              {passRate.toFixed(1)}%
            </div>
            <div className="mt-0.5 text-[10px] text-muted-foreground">
              {totalEvaluated.toLocaleString()} / {totalLoans.toLocaleString()} loans
            </div>
          </div>
        </div>

        {/* Per-category summary chips */}
        {report.summary?.by_category &&
          Object.keys(report.summary.by_category).length > 0 && (
            <div className="flex flex-wrap gap-2">
              {Object.entries(report.summary.by_category).map(([cat, info]) => {
                const t = categoryTone(cat);
                const total = info.matches + info.deviates;
                const okPct = total > 0 ? (info.matches / total) * 100 : 0;
                return (
                  <span
                    key={cat}
                    className={cn(
                      "inline-flex items-baseline gap-1.5 rounded-md px-2.5 py-1 text-xs ring-1 ring-inset",
                      t.bg,
                      t.text
                    )}
                  >
                    <span className="font-semibold">{t.label}</span>
                    <span className="font-mono">
                      {info.matches.toLocaleString()}/{total.toLocaleString()}
                    </span>
                    <span className="text-[10px] opacity-70">
                      ({okPct.toFixed(0)}%)
                    </span>
                  </span>
                );
              })}
            </div>
          )}

        {/* Per-test-case results table */}
        <div className="overflow-hidden rounded-lg border border-border/40">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/30 hover:bg-muted/30">
                <TableHead className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Status
                </TableHead>
                <TableHead className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Test Case
                </TableHead>
                <TableHead className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Category
                </TableHead>
                <TableHead className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Expected
                </TableHead>
                <TableHead className="text-right text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Loans
                </TableHead>
                <TableHead className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Actual Distribution
                </TableHead>
                <TableHead className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Notes
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(report.results ?? []).map((r) => {
                const cat = categoryTone(r.category);
                const noLoans = r.matched_loan_count === 0;
                const passed = !noLoans && r.deviates_from_expected === 0;
                const allShadowed =
                  passed &&
                  (r.shadowed ?? 0) > 0 &&
                  r.matches_expected === 0;
                const someShadowed =
                  passed && (r.shadowed ?? 0) > 0 && !allShadowed;
                const StatusIcon = noLoans
                  ? AlertCircle
                  : passed
                    ? CheckCircle
                    : XCircle;
                const statusColor = noLoans
                  ? "text-slate-500"
                  : allShadowed
                    ? "text-amber-600 dark:text-amber-400"
                    : passed
                      ? "text-emerald-600 dark:text-emerald-400"
                      : "text-red-600 dark:text-red-400";
                const statusLabel = noLoans
                  ? "Untested"
                  : allShadowed
                    ? "Shadowed"
                    : passed
                      ? "Pass"
                      : "Fail";
                const statusBg = noLoans
                  ? "bg-slate-500/10 ring-slate-500/20"
                  : allShadowed
                    ? "bg-amber-500/10 ring-amber-500/30"
                    : passed
                      ? "bg-emerald-500/10 ring-emerald-500/30"
                      : "bg-red-500/10 ring-red-500/30";
                return (
                  <TableRow
                    key={r.test_case_id}
                    className="transition-colors hover:bg-accent/30"
                  >
                    <TableCell>
                      <span
                        className={cn(
                          "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ring-1 ring-inset",
                          statusBg,
                          statusColor
                        )}
                      >
                        <StatusIcon className="size-3" />
                        {statusLabel}
                      </span>
                    </TableCell>
                    <TableCell className="font-mono text-xs font-medium">
                      {r.test_case_id}
                    </TableCell>
                    <TableCell>
                      <span
                        className={cn(
                          "inline-flex rounded-md px-1.5 py-0.5 text-[10px] font-semibold ring-1 ring-inset",
                          cat.bg,
                          cat.text
                        )}
                      >
                        {cat.label}
                      </span>
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {r.expected_decision}
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs">
                      {r.matched_loan_count.toLocaleString()}
                    </TableCell>
                    <TableCell className="font-mono text-[11px] text-muted-foreground">
                      <div>{formatDistribution(r.actual_distribution)}</div>
                      {r.engine_decision_distribution &&
                        Object.keys(r.engine_decision_distribution).length > 0 && (
                          <div className="mt-0.5 text-[10px] opacity-60">
                            engine: {formatDistribution(r.engine_decision_distribution)}
                          </div>
                        )}
                    </TableCell>
                    <TableCell className="text-xs">
                      {r.deviates_from_expected > 0 ? (
                        <span className="text-red-600 dark:text-red-400">
                          {r.deviates_from_expected.toLocaleString()} deviated
                          {r.first_deviation_reason && (
                            <span className="ml-1 text-[10px] text-muted-foreground">
                              ({r.first_deviation_reason})
                            </span>
                          )}
                        </span>
                      ) : noLoans ? (
                        <span className="text-muted-foreground italic">
                          No matching loans in corpus
                        </span>
                      ) : allShadowed ? (
                        <span
                          className="text-amber-700 dark:text-amber-300"
                          title="The source rule didn't fire on these loans, but a higher-priority REJECT short-circuited the engine first — the policy outcome is still correct."
                        >
                          all {r.matched_loan_count.toLocaleString()} shadowed by an earlier REJECT rule
                        </span>
                      ) : someShadowed ? (
                        <span className="text-emerald-600 dark:text-emerald-400">
                          {r.matches_expected.toLocaleString()} fired ·{" "}
                          <span className="text-amber-700 dark:text-amber-300">
                            {r.shadowed?.toLocaleString()} shadowed
                          </span>
                        </span>
                      ) : (
                        <span className="text-emerald-600 dark:text-emerald-400">
                          all matched expected
                        </span>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
