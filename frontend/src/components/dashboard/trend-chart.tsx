"use client";

import { useMemo } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import { Card, CardContent } from "@/components/ui/card";
import { TrendingUp, TrendingDown, Minus, AlertTriangle } from "lucide-react";
import type { DashboardTrends } from "@/lib/types";

interface TrendChartProps {
  trends: DashboardTrends;
}

/**
 * Approval-rate trend across the last N completed impact runs. Answers
 * "are we getting more or less restrictive over time?" in one glance.
 *
 * Slice 11 follow-up: now also plots FLAGGED + REJECTED rates so a
 * 0% approval rate doesn't look like a flat baseline — you can see
 * the loans landing in FLAGGED instead. This catches the units-mismatch
 * class of bug where every loan hits a FLAG rule.
 */
export function TrendChart({ trends }: TrendChartProps) {
  const data = useMemo(() => {
    return trends.approval_rate_history.map((p, idx) => ({
      idx: idx + 1,
      run: `Run ${idx + 1}`,
      approval: Number((p.approval_rate * 100).toFixed(2)),
      flagged: Number(((p.flagged_rate ?? 0) * 100).toFixed(2)),
      rejected: Number(((p.rejected_rate ?? 0) * 100).toFixed(2)),
      loans: p.total_loans,
      ts: p.completed_at,
    }));
  }, [trends.approval_rate_history]);

  const direction = useMemo(() => {
    if (data.length < 2) return 0;
    const first = data[0].approval;
    const last = data[data.length - 1].approval;
    return last - first;
  }, [data]);

  const TrendIcon =
    direction > 0.5 ? TrendingUp : direction < -0.5 ? TrendingDown : Minus;
  const trendColor =
    direction > 0.5
      ? "text-emerald-600 dark:text-emerald-400"
      : direction < -0.5
        ? "text-rose-600 dark:text-rose-400"
        : "text-muted-foreground";

  // Smoke alarm: every recent run produced 0 APPROVED. Show a warning
  // banner so the operator can't miss it.
  const allZeroApproval =
    data.length > 0 && data.every((d) => d.approval === 0);

  return (
    <Card className="card-elevated border-border/40 h-full">
      <CardContent className="p-5">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold tracking-tight">
              Decision-Rate Trend
            </h3>
            <p className="text-[11px] text-muted-foreground">
              Candidate decisions across the last {data.length} impact runs
            </p>
          </div>
          {data.length >= 2 && !allZeroApproval && (
            <div className={`flex items-center gap-1 text-xs font-medium ${trendColor}`}>
              <TrendIcon className="size-3.5" />
              <span className="font-mono">
                {direction > 0 ? "+" : ""}
                {direction.toFixed(2)} pts
              </span>
            </div>
          )}
        </div>

        {allZeroApproval && (
          <div className="mb-3 flex items-start gap-2 rounded-md bg-rose-500/10 p-2 text-xs text-rose-700 ring-1 ring-inset ring-rose-500/30 dark:text-rose-300">
            <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
            <span>
              0% approval across every recent run. The rules are funnelling
              every loan into FLAG/REJECT — likely a misconfigured scoring
              rule (units mismatch) or an over-broad FLAG condition.
            </span>
          </div>
        )}

        {data.length === 0 ? (
          <div className="flex h-40 flex-col items-center justify-center text-center">
            <p className="text-xs text-muted-foreground">
              No completed impact runs yet — the trend will appear here once
              you've compared two versions.
            </p>
          </div>
        ) : (
          <div className="h-44">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={data}
                margin={{ top: 4, right: 8, left: -16, bottom: 0 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="currentColor"
                  className="text-muted-foreground/10"
                />
                <XAxis
                  dataKey="run"
                  tick={{ fontSize: 10 }}
                  stroke="currentColor"
                  className="text-muted-foreground"
                />
                <YAxis
                  unit="%"
                  domain={[0, 100]}
                  tick={{ fontSize: 10 }}
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
                  formatter={(v: any, name: any) => [
                    `${Number(v ?? 0).toFixed(2)}%`,
                    String(name ?? ""),
                  ]}
                  labelFormatter={(label, items) => {
                    const ts = items?.[0]?.payload?.ts;
                    return ts
                      ? new Date(ts).toLocaleString("en-US", {
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })
                      : label;
                  }}
                />
                <Legend
                  wrapperStyle={{ fontSize: 10, paddingTop: 4 }}
                  iconSize={8}
                />
                <Line
                  type="monotone"
                  dataKey="approval"
                  name="Approved"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={{ r: 3, fill: "#10b981" }}
                  activeDot={{ r: 5 }}
                  isAnimationActive={false}
                />
                <Line
                  type="monotone"
                  dataKey="flagged"
                  name="Flagged"
                  stroke="#f59e0b"
                  strokeWidth={2}
                  strokeDasharray="4 2"
                  dot={{ r: 2.5, fill: "#f59e0b" }}
                  activeDot={{ r: 5 }}
                  isAnimationActive={false}
                />
                <Line
                  type="monotone"
                  dataKey="rejected"
                  name="Rejected"
                  stroke="#ef4444"
                  strokeWidth={2}
                  strokeDasharray="2 3"
                  dot={{ r: 2.5, fill: "#ef4444" }}
                  activeDot={{ r: 5 }}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
