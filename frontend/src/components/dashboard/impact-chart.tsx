"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { TrendingUp } from "lucide-react";

interface ChartPoint {
  name: string;
  date: string;
  impact: number;
}

interface ImpactChartProps {
  data: ChartPoint[];
}

export function ImpactChart({ data }: ImpactChartProps) {
  if (data.length === 0) {
    return (
      <Card className="card-elevated border-border/40">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-sm font-semibold text-foreground">
            <TrendingUp className="size-4 text-emerald-500" />
            Impact Trend
          </CardTitle>
        </CardHeader>
        <CardContent className="flex h-[250px] items-center justify-center">
          <p className="text-sm text-muted-foreground">No completed simulations yet</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="card-elevated border-border/40">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <TrendingUp className="size-4 text-emerald-500" />
          Impact Trend
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[250px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data}>
              <defs>
                <linearGradient id="impactGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.2} />
                  <stop offset="100%" stopColor="var(--primary)" stopOpacity={0.01} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} stroke="transparent" />
              <YAxis
                tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                stroke="transparent"
                tickFormatter={(v) => `${v}%`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "var(--card)",
                  border: "1px solid var(--border)",
                  borderRadius: "10px",
                  color: "var(--foreground)",
                  fontSize: "12px",
                  boxShadow: "0 4px 16px rgba(0,0,0,0.08)",
                }}
                formatter={(value) => [`${Number(value).toFixed(1)}%`, "Affected"]}
              />
              <Area
                type="monotone"
                dataKey="impact"
                stroke="var(--primary)"
                fill="url(#impactGradient)"
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
