"use client";

import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import type { SimulationResult } from "@/lib/types";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

const COLORS = ["#6366f1", "#f59e0b", "#10b981", "#ef4444"];

interface ComparisonChartsProps {
  results: {
    name: string;
    result: SimulationResult;
  }[];
}

export function ComparisonCharts({ results }: ComparisonChartsProps) {
  const chartData = [
    {
      metric: "Affected %",
      ...Object.fromEntries(
        results.map((r) => [
          r.name,
          r.result.summary_stats.affected_percentage,
        ])
      ),
    },
    {
      metric: "Approved\u2192Rejected",
      ...Object.fromEntries(
        results.map((r) => [
          r.name,
          r.result.summary_stats.decision_changes.approved_to_rejected,
        ])
      ),
    },
    {
      metric: "Rejected\u2192Approved",
      ...Object.fromEntries(
        results.map((r) => [
          r.name,
          r.result.summary_stats.decision_changes.rejected_to_approved,
        ])
      ),
    },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Comparison Bar Chart</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={400}>
          <BarChart
            data={chartData}
            margin={{ top: 10, right: 30, left: 10, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis
              dataKey="metric"
              tick={{ fontSize: 12 }}
              className="fill-muted-foreground"
            />
            <YAxis
              tick={{ fontSize: 12 }}
              className="fill-muted-foreground"
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "hsl(var(--background))",
                border: "1px solid hsl(var(--border))",
                borderRadius: "8px",
                fontSize: "12px",
              }}
            />
            <Legend />
            {results.map((r, i) => (
              <Bar
                key={r.name}
                dataKey={r.name}
                fill={COLORS[i % COLORS.length]}
                radius={[4, 4, 0, 0]}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
