"use client";

import { useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Cell,
  LabelList,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Repeat } from "lucide-react";
import type { ImpactRunSummary } from "@/lib/types";

interface FlipsChartProps {
  summary: ImpactRunSummary;
}

/** Pretty-print a flip key like "approved_to_rejected" → "APPROVED → REJECTED" */
function formatFlipLabel(key: string): { label: string; color: string } {
  const parts = key.toUpperCase().split("_TO_");
  if (parts.length !== 2) {
    return { label: key, color: "#94a3b8" };
  }
  const [from, to] = parts;
  // Color = severity of the new state
  const color =
    to === "REJECTED"
      ? "#ef4444"      // red — became worse
      : to === "FLAGGED"
        ? "#f59e0b"    // amber
        : to === "APPROVED"
          ? "#10b981"  // green — became better
          : "#94a3b8";
  return { label: `${from} → ${to}`, color };
}

export function FlipsChart({ summary }: FlipsChartProps) {
  const data = useMemo(() => {
    const flips = summary.decision_flips ?? {};
    return Object.entries(flips)
      .map(([key, count]) => {
        const { label, color } = formatFlipLabel(key);
        return { key, label, count, color };
      })
      .sort((a, b) => b.count - a.count);
  }, [summary]);

  return (
    <Card className="card-elevated border-border/40">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Repeat className="size-5 text-rose-500" />
          Decision Flips
        </CardTitle>
      </CardHeader>
      <CardContent>
        {data.length === 0 ? (
          <p className="py-8 text-center text-sm italic text-muted-foreground">
            No decisions changed between these two versions.
          </p>
        ) : (
          <div className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={data}
                margin={{ top: 12, right: 30, left: 12, bottom: 5 }}
                layout="vertical"
              >
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.04)" />
                <XAxis type="number" className="text-sm" />
                <YAxis
                  dataKey="label"
                  type="category"
                  width={170}
                  className="text-xs"
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "var(--card)",
                    border: "1px solid var(--border)",
                    borderRadius: "8px",
                    color: "var(--foreground)",
                    fontSize: "12px",
                  }}
                  formatter={(value) => Number(value ?? 0).toLocaleString()}
                  labelFormatter={(label) => `Transition: ${String(label)}`}
                />
                <Bar dataKey="count" radius={[0, 4, 4, 0]} isAnimationActive={false}>
                  {data.map((d) => (
                    <Cell key={d.key} fill={d.color} />
                  ))}
                  <LabelList
                    dataKey="count"
                    position="right"
                    fontSize={11}
                    formatter={(v) => Number(v ?? 0).toLocaleString()}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
