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
} from "recharts";
import { Card, CardContent } from "@/components/ui/card";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import type { DashboardTrends } from "@/lib/types";

interface TrendChartProps {
  trends: DashboardTrends;
}

/**
 * Approval-rate trend across the last N completed impact runs. Answers
 * "are we getting more or less restrictive over time?" in one glance.
 */
export function TrendChart({ trends }: TrendChartProps) {
  const data = useMemo(() => {
    return trends.approval_rate_history.map((p, idx) => ({
      idx: idx + 1,
      run: `Run ${idx + 1}`,
      approval: Number((p.approval_rate * 100).toFixed(2)),
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

  return (
    <Card className="card-elevated border-border/40 h-full">
      <CardContent className="p-5">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold tracking-tight">
              Approval-Rate Trend
            </h3>
            <p className="text-[11px] text-muted-foreground">
              Candidate approval rate across the last {data.length} impact runs
            </p>
          </div>
          {data.length >= 2 && (
            <div className={`flex items-center gap-1 text-xs font-medium ${trendColor}`}>
              <TrendIcon className="size-3.5" />
              <span className="font-mono">
                {direction > 0 ? "+" : ""}
                {direction.toFixed(2)} pts
              </span>
            </div>
          )}
        </div>
        {data.length === 0 ? (
          <div className="flex h-40 flex-col items-center justify-center text-center">
            <p className="text-xs text-muted-foreground">
              No completed impact runs yet — the trend will appear here once
              you've compared two versions.
            </p>
          </div>
        ) : (
          <div className="h-40">
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
                  domain={["auto", "auto"]}
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
                  formatter={(v: any) => [`${Number(v ?? 0).toFixed(2)}%`, "Approval rate"]}
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
                <Line
                  type="monotone"
                  dataKey="approval"
                  stroke="hsl(220 70% 55%)"
                  strokeWidth={2}
                  dot={{ r: 3, fill: "hsl(220 70% 55%)" }}
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
