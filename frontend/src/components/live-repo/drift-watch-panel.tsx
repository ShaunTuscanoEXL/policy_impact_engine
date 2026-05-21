"use client";

/**
 * DriftWatchPanel — Slice 10. Calls the /live-repo/{id}/drift endpoint
 * and renders a side-by-side comparison of:
 *
 *   • Predicted decision distribution (from the impact run that
 *     produced the production version)
 *   • Observed distribution (re-evaluated against the current loan
 *     corpus on demand)
 *
 * Plus per-segment approval-rate deltas + a hero callout when the
 * top-drifting segment exceeds a configurable threshold.
 *
 * Renders a "no data yet" state when no production version exists,
 * and a "baseline missing" state when the production version was
 * promoted without an impact run.
 */
import { useCallback, useEffect, useState } from "react";
import api from "@/lib/api";
import type { DriftReport } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Activity,
  Loader2,
  RefreshCw,
  TrendingDown,
  TrendingUp,
  AlertTriangle,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  repoId: string;
  /** Threshold above which the panel shows a red "drift detected"
   *  callout. 0.05 = 5 percentage points. */
  alertThresholdPct?: number;
  /** Cap loans evaluated — useful in dev. Production should leave null. */
  loanLimit?: number;
}

function formatPct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

function formatPctDelta(delta: number): string {
  const pts = delta * 100;
  const sign = pts > 0 ? "+" : pts < 0 ? "−" : "±";
  return `${sign}${Math.abs(pts).toFixed(1)} pts`;
}

export function DriftWatchPanel({
  repoId,
  alertThresholdPct = 0.05,
  loanLimit,
}: Props) {
  const [report, setReport] = useState<DriftReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchReport = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, any> = {};
      if (loanLimit) params.loan_limit = loanLimit;
      const { data } = await api.get<DriftReport>(
        `/live-repo/${repoId}/drift`,
        { params },
      );
      setReport(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to compute drift.");
      setReport(null);
    } finally {
      setLoading(false);
    }
  }, [repoId, loanLimit]);

  useEffect(() => {
    fetchReport();
  }, [fetchReport]);

  const headerCta = (
    <Button
      variant="ghost"
      size="sm"
      disabled={loading}
      onClick={fetchReport}
      className="gap-1.5"
    >
      {loading ? (
        <Loader2 className="size-3.5 animate-spin" />
      ) : (
        <RefreshCw className="size-3.5" />
      )}
      Recompute
    </Button>
  );

  return (
    <Card className="card-elevated border-border/50">
      <CardHeader className="pb-2 flex-row items-center justify-between space-y-0">
        <CardTitle className="flex items-center gap-2 text-base">
          <span className="rounded-md bg-blue-500/10 p-1.5 ring-1 ring-inset ring-blue-500/20">
            <Activity className="size-4 text-blue-600 dark:text-blue-400" />
          </span>
          Production drift watch
          {report?.production_version_number != null && (
            <Badge variant="outline" className="ml-1 text-[10px]">
              v{report.production_version_number}
            </Badge>
          )}
        </CardTitle>
        {headerCta}
      </CardHeader>
      <CardContent className="space-y-4">
        {loading && !report ? (
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            <Loader2 className="size-5 animate-spin" />
          </div>
        ) : error ? (
          <div className="rounded-lg bg-amber-500/10 p-3 text-sm text-amber-700 ring-1 ring-inset ring-amber-500/30 dark:text-amber-300">
            {error}
          </div>
        ) : !report ? (
          <p className="py-6 text-center text-sm italic text-muted-foreground">
            No drift data yet.
          </p>
        ) : (
          <>
            {report.warnings.length > 0 && (
              <div className="space-y-1">
                {report.warnings.map((w, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-2 rounded-md bg-amber-500/10 p-2 text-xs text-amber-700 ring-1 ring-inset ring-amber-500/30 dark:text-amber-300"
                  >
                    <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
                    <span>{w}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Hero callout when drift exceeds the threshold */}
            {report.drift.max_abs_delta_pct >= alertThresholdPct && (
              <div className="flex items-start gap-2 rounded-lg bg-rose-500/10 p-3 text-sm text-rose-700 ring-1 ring-inset ring-rose-500/30 dark:text-rose-300">
                <AlertTriangle className="mt-0.5 size-4 shrink-0" />
                <div className="space-y-0.5">
                  <p className="font-medium">
                    Drift detected — production is{" "}
                    {(report.drift.max_abs_delta_pct * 100).toFixed(1)} pts off
                    the predicted baseline.
                  </p>
                  {report.drift.top_drifting_segment && (
                    <p className="text-xs opacity-90">
                      Concentrated in{" "}
                      <span className="font-mono font-semibold">
                        {report.drift.top_drifting_segment.replaceAll("_", " ")}
                      </span>
                      .
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Decision-distribution comparison */}
            <div className="overflow-hidden rounded-lg border border-border/40">
              <div className="grid grid-cols-12 gap-2 border-b border-border/40 bg-muted/30 px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                <div className="col-span-3">Decision</div>
                <div className="col-span-3 text-right">Predicted</div>
                <div className="col-span-3 text-right">Observed</div>
                <div className="col-span-3 text-right">Δ</div>
              </div>
              {Object.entries(report.drift.decision_distribution).map(
                ([label, info]) => {
                  const TrendIcon =
                    info.delta_pct < 0
                      ? TrendingDown
                      : info.delta_pct > 0
                        ? TrendingUp
                        : Activity;
                  const tone =
                    info.delta_pct < -0.005
                      ? "text-rose-700 dark:text-rose-300"
                      : info.delta_pct > 0.005
                        ? "text-emerald-700 dark:text-emerald-300"
                        : "text-muted-foreground";
                  return (
                    <div
                      key={label}
                      className="grid grid-cols-12 gap-2 border-b border-border/30 px-3 py-2 text-xs last:border-0 hover:bg-muted/20"
                    >
                      <div className="col-span-3 font-medium">{label}</div>
                      <div className="col-span-3 text-right font-mono text-muted-foreground">
                        {formatPct(info.predicted_pct)}
                      </div>
                      <div className="col-span-3 text-right font-mono">
                        {formatPct(info.observed_pct)}
                      </div>
                      <div
                        className={cn(
                          "col-span-3 flex items-center justify-end gap-1 font-mono",
                          tone,
                        )}
                      >
                        <TrendIcon className="size-3" />
                        {formatPctDelta(info.delta_pct)}
                      </div>
                    </div>
                  );
                },
              )}
            </div>

            {/* Per-segment drift */}
            {Object.keys(report.drift.by_segment).length > 0 && (
              <div className="overflow-hidden rounded-lg border border-border/40">
                <div className="grid grid-cols-12 gap-2 border-b border-border/40 bg-muted/30 px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  <div className="col-span-3">Segment</div>
                  <div className="col-span-2 text-right">Loans</div>
                  <div className="col-span-3 text-right">Approval (pred.)</div>
                  <div className="col-span-2 text-right">Observed</div>
                  <div className="col-span-2 text-right">Δ</div>
                </div>
                {Object.entries(report.drift.by_segment)
                  .sort(
                    (a, b) =>
                      Math.abs(b[1].approval_rate_delta) -
                      Math.abs(a[1].approval_rate_delta),
                  )
                  .map(([seg, info]) => {
                    const tone =
                      info.approval_rate_delta < -0.005
                        ? "text-rose-700 dark:text-rose-300"
                        : info.approval_rate_delta > 0.005
                          ? "text-emerald-700 dark:text-emerald-300"
                          : "text-muted-foreground";
                    return (
                      <div
                        key={seg}
                        className="grid grid-cols-12 gap-2 border-b border-border/30 px-3 py-2 text-xs last:border-0 hover:bg-muted/20"
                      >
                        <div className="col-span-3 font-medium">
                          {seg.replaceAll("_", " ")}
                        </div>
                        <div className="col-span-2 text-right font-mono text-muted-foreground">
                          {info.loans.toLocaleString()}
                        </div>
                        <div className="col-span-3 text-right font-mono text-muted-foreground">
                          {formatPct(info.predicted_approval_rate)}
                        </div>
                        <div className="col-span-2 text-right font-mono">
                          {formatPct(info.observed_approval_rate)}
                        </div>
                        <div className={cn("col-span-2 text-right font-mono font-semibold", tone)}>
                          {formatPctDelta(info.approval_rate_delta)}
                        </div>
                      </div>
                    );
                  })}
              </div>
            )}

            <div className="flex flex-wrap items-center justify-between gap-2 text-[10px] italic text-muted-foreground">
              <span>
                Computed{" "}
                {new Date(report.computed_at).toLocaleString()} ·{" "}
                {report.observed.loan_count.toLocaleString()} loans evaluated
              </span>
              {report.predicted_source && (
                <span>
                  Baseline: impact run{" "}
                  <code>{report.predicted_source.impact_run_id.slice(0, 8)}</code>
                  {report.predicted_source.completed_at
                    ? ` (${new Date(report.predicted_source.completed_at).toLocaleDateString()})`
                    : ""}
                </span>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
