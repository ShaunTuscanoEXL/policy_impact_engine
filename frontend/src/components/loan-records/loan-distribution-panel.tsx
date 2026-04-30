"use client";

import { useEffect, useState } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import api from "@/lib/api";
import { BarChart3, Loader2, TrendingUp } from "lucide-react";

function DecisionSkeleton() {
  return (
    <>
      <div className="h-9 w-40 animate-pulse rounded-md bg-muted/40" />
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-muted/40">
        <div className="h-full w-3/4 animate-pulse bg-muted/60" />
      </div>
      <ul className="space-y-1.5 pt-1">
        {[0, 1, 2].map((i) => (
          <li key={i} className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <span className="size-2 rounded-full bg-muted/60" />
              <span className="h-3 w-24 animate-pulse rounded bg-muted/40" />
            </div>
            <span className="h-3 w-16 animate-pulse rounded bg-muted/40" />
          </li>
        ))}
      </ul>
    </>
  );
}
import type { LoanRecordStats } from "@/lib/types";

interface HistogramBin {
  x0: number;
  x1: number;
  count: number;
  /** Optional human-readable label for named bands ("Subprime", "$3k–5k", …). */
  label?: string;
}

interface HistogramResponse {
  field: string;
  bins: HistogramBin[];
  min: number | null;
  max: number | null;
  count: number;
  /** "fico_bands" / "income_brackets" / "dti_bands" / "equi_width" — tells
   *  the renderer whether to lean on bin labels or x0 values. */
  mode?: string;
}

const DECISION_COLORS: Record<string, string> = {
  APPROVED: "hsl(160 70% 45%)",
  APPROVED_WITH_CONDITIONS: "hsl(40 95% 55%)",
  REJECTED: "hsl(0 80% 60%)",
  CONDITIONAL: "hsl(40 95% 55%)",
  PENDING: "hsl(220 15% 60%)",
};

interface LoanDistributionPanelProps {
  /** Stats payload — may be null while still loading. The panel renders
   *  skeleton placeholders rather than disappearing while it waits. */
  stats: LoanRecordStats | null;
  /** Whether the parent is still fetching `stats`. */
  statsLoading?: boolean;
}

/**
 * Three-card row showing the loan corpus's shape: decision split as a
 * colored stacked bar, FICO histogram, and income histogram. Replaces
 * the small text-only cards that used to live inline on the page.
 */
export function LoanDistributionPanel({
  stats,
  statsLoading = false,
}: LoanDistributionPanelProps) {
  const [ficoHist, setFicoHist] = useState<HistogramResponse | null>(null);
  const [incomeHist, setIncomeHist] = useState<HistogramResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const [fico, income] = await Promise.all([
          api.get<HistogramResponse>(
            "/loan-records/histogram?field=bureau_score&mode=auto&sample=8000",
          ),
          api.get<HistogramResponse>(
            "/loan-records/histogram?field=monthly_income&mode=auto&sample=8000",
          ),
        ]);
        if (cancelled) return;
        setFicoHist(fico.data);
        setIncomeHist(income.data);
      } catch {
        // Histograms are best-effort — UI gracefully shows empty state
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const total = (stats?.total_records ?? 0) || 1;
  const decisionEntries = Object.entries(stats?.decision_distribution || {})
    .map(([key, count]) => ({
      key,
      count,
      pct: (count / total) * 100,
      color: DECISION_COLORS[key] ?? "hsl(220 15% 60%)",
    }))
    .sort((a, b) => b.count - a.count);
  const decisionLoading = statsLoading || !stats;

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      {/* Decision distribution as a colored stacked bar */}
      <Card className="card-elevated border-border/40">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm font-semibold">
            <span className="rounded-md bg-emerald-500/10 p-1.5 ring-1 ring-inset ring-emerald-500/20">
              <BarChart3 className="size-3.5 text-emerald-600 dark:text-emerald-400" />
            </span>
            Decision Distribution
            {decisionLoading && (
              <Loader2
                className="size-3 animate-spin text-muted-foreground"
                aria-label="Loading"
              />
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {decisionLoading ? (
            <DecisionSkeleton />
          ) : (
            <>
              <div className="text-3xl font-mono font-bold tabular-nums text-foreground">
                {total.toLocaleString()}
                <span className="ml-1 text-xs font-normal text-muted-foreground">
                  loans
                </span>
              </div>
              <div className="flex h-3 w-full overflow-hidden rounded-full bg-muted/40">
                {decisionEntries.map((d) => (
                  <div
                    key={d.key}
                    className="h-full transition-all"
                    style={{
                      backgroundColor: d.color,
                      width: `${d.pct}%`,
                    }}
                    title={`${d.key}: ${d.count.toLocaleString()} (${d.pct.toFixed(1)}%)`}
                  />
                ))}
              </div>
              <ul className="space-y-1 pt-1">
                {decisionEntries.map((d) => (
                  <li
                    key={d.key}
                    className="flex items-center justify-between text-xs"
                  >
                    <span className="flex items-center gap-1.5">
                      <span
                        className="size-2 rounded-full"
                        style={{ backgroundColor: d.color }}
                      />
                      <span className="font-medium">{d.key}</span>
                    </span>
                    <span className="font-mono tabular-nums text-muted-foreground">
                      {d.count.toLocaleString()} · {d.pct.toFixed(1)}%
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </CardContent>
      </Card>

      {/* FICO histogram */}
      <Card className="card-elevated border-border/40">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm font-semibold">
            <span className="rounded-md bg-blue-500/10 p-1.5 ring-1 ring-inset ring-blue-500/20">
              <TrendingUp className="size-3.5 text-blue-600 dark:text-blue-400" />
            </span>
            FICO Score Distribution
            {loading && (
              <Loader2
                className="size-3 animate-spin text-muted-foreground"
                aria-label="Loading"
              />
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <HistogramRender hist={ficoHist} loading={loading} unit="" hue={220} />
          <div className="mt-2 text-[10px] text-muted-foreground">
            {statsLoading || !stats ? (
              <span className="inline-block h-3 w-32 animate-pulse rounded bg-muted/40" />
            ) : (
              <>
                avg{" "}
                <span className="font-mono font-semibold text-foreground">
                  {Math.round(stats.bureau_score_range?.avg ?? 0)}
                </span>{" "}
                · range {Math.round(stats.bureau_score_range?.min ?? 0)} –{" "}
                {Math.round(stats.bureau_score_range?.max ?? 0)}
              </>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Income histogram */}
      <Card className="card-elevated border-border/40">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm font-semibold">
            <span className="rounded-md bg-amber-500/10 p-1.5 ring-1 ring-inset ring-amber-500/20">
              <TrendingUp className="size-3.5 text-amber-600 dark:text-amber-400" />
            </span>
            Monthly Income Distribution
            {loading && (
              <Loader2
                className="size-3 animate-spin text-muted-foreground"
                aria-label="Loading"
              />
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <HistogramRender hist={incomeHist} loading={loading} unit="$" hue={36} />
          <div className="mt-2 text-[10px] text-muted-foreground">
            {statsLoading || !stats ? (
              <span className="inline-block h-3 w-24 animate-pulse rounded bg-muted/40" />
            ) : (
              <>
                avg{" "}
                <span className="font-mono font-semibold text-foreground">
                  ${Math.round(stats.income_range?.avg ?? 0).toLocaleString()}
                </span>
              </>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function HistogramRender({
  hist,
  loading,
  unit,
  hue = 220,
}: {
  hist: HistogramResponse | null;
  loading: boolean;
  unit: string;
  /** HSL hue for the bar gradient — keeps each chart visually distinct. */
  hue?: number;
}) {
  if (loading) {
    return (
      <div className="flex h-36 items-center justify-center">
        <Loader2 className="size-4 animate-spin text-muted-foreground" />
      </div>
    );
  }
  if (!hist || hist.bins.length === 0) {
    return (
      <p className="py-8 text-center text-xs italic text-muted-foreground">
        No data
      </p>
    );
  }
  const isBanded = hist.mode && hist.mode !== "equi_width";
  const data = hist.bins.map((b) => ({
    // Prefer the API's human label for banded modes; fall back to the
    // numeric range when equi-width.
    range:
      b.label ??
      (unit
        ? `${unit}${Math.round(b.x0 / 1000)}k`
        : `${Math.round(b.x0)}`),
    count: b.count,
    tooltipLabel: b.label
      ? b.label.replace(/\n/g, " ")
      : `${unit}${Math.round(b.x0).toLocaleString()} – ${unit}${Math.round(b.x1).toLocaleString()}`,
    pct: 0, // filled below
  }));
  const total = data.reduce((acc, d) => acc + d.count, 0) || 1;
  data.forEach((d) => {
    d.pct = (d.count / total) * 100;
  });
  const maxCount = Math.max(...data.map((d) => d.count), 1);
  return (
    <div className="h-36">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          margin={{ top: 4, right: 0, left: -28, bottom: isBanded ? 12 : 0 }}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="currentColor"
            className="text-muted-foreground/10"
          />
          <XAxis
            dataKey="range"
            tick={{ fontSize: isBanded ? 9 : 9 }}
            stroke="currentColor"
            className="text-muted-foreground"
            interval={0}
            // Multi-line labels for banded mode (Subprime\n(<580))
            tickFormatter={(v: string) => v}
          />
          <YAxis
            tick={{ fontSize: 9 }}
            stroke="currentColor"
            className="text-muted-foreground"
          />
          <Tooltip
            contentStyle={{
              background: "hsl(var(--popover))",
              border: "1px solid hsl(var(--border))",
              borderRadius: 8,
              fontSize: 12,
            }}
            formatter={(v: any, _name, item: any) => [
              `${Number(v ?? 0).toLocaleString()}  (${(item?.payload?.pct ?? 0).toFixed(1)}%)`,
              "Loans",
            ]}
            labelFormatter={(_, items) =>
              items?.[0]?.payload?.tooltipLabel ?? ""
            }
          />
          <Bar dataKey="count" radius={[3, 3, 0, 0]} isAnimationActive={false}>
            {data.map((d, i) => {
              const t = d.count / maxCount;
              return (
                <Cell
                  key={i}
                  fill={`hsl(${hue} 70% ${Math.round(45 + t * 25)}% / ${0.5 + t * 0.5})`}
                />
              );
            })}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
