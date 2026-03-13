"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import type { Simulation } from "@/lib/types";

interface ImpactChartProps {
  simulations: Simulation[];
}

export function ImpactChart({ simulations }: ImpactChartProps) {
  // Generate chart data from simulations (use index as x-axis if no results available)
  const data = simulations
    .filter((s) => s.status === "COMPLETED")
    .slice(0, 10)
    .reverse()
    .map((s, i) => ({
      name: `Sim ${i + 1}`,
      date: new Date(s.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
    }));

  // If no data, show a placeholder
  if (data.length === 0) {
    return (
      <Card className="border-border/50 shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">Impact Trend</CardTitle>
        </CardHeader>
        <CardContent className="flex h-[200px] items-center justify-center">
          <p className="text-sm text-muted-foreground">No completed simulations yet</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-border/50 shadow-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">Recent Simulations</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[200px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data}>
              <defs>
                <linearGradient id="blueGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#0070f3" stopOpacity={0.2} />
                  <stop offset="100%" stopColor="#0070f3" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" className="stroke-foreground/[0.04]" />
              <XAxis dataKey="date" tick={{ fontSize: 12 }} stroke="#a1a1a1" />
              <YAxis hide />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#171717",
                  border: "none",
                  borderRadius: "8px",
                  color: "#ededed",
                  fontSize: "12px",
                }}
              />
              <Area
                type="monotone"
                dataKey="date"
                stroke="#0070f3"
                fill="url(#blueGradient)"
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
