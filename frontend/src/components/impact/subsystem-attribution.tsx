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
import { Layers } from "lucide-react";
import type { ImpactRunSummary, Subsystem } from "@/lib/types";

interface SubsystemAttributionProps {
  summary: ImpactRunSummary;
}

const SUBSYSTEM_COLOR: Record<string, string> = {
  REGULATORY_FLOOR: "#7c3aed",
  BUREAU_GATE: "#ef4444",
  INCOME_GATE: "#f97316",
  DTI_GATE: "#eab308",
  EMPLOYMENT_GATE: "#84cc16",
  BANKING_BEHAVIOR: "#10b981",
  FRAUD_SIGNAL: "#06b6d4",
  EXPOSURE_LIMIT: "#3b82f6",
  AMOUNT_CAP: "#6366f1",
  PRICING_TIER: "#8b5cf6",
  RATE_MODIFIER: "#a855f7",
  SCORING_MODEL: "#ec4899",
  UNCLASSIFIED: "#94a3b8",
};

function colorFor(subsystem: string): string {
  return SUBSYSTEM_COLOR[subsystem] ?? "#64748b";
}

export function SubsystemAttribution({ summary }: SubsystemAttributionProps) {
  const data = useMemo(() => {
    return Object.entries(summary.by_subsystem ?? {})
      .map(([name, info]) => ({
        name,
        flips: info.flips_caused,
        color: colorFor(name as Subsystem),
      }))
      .sort((a, b) => b.flips - a.flips);
  }, [summary]);

  return (
    <Card className="card-elevated border-border/40">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Layers className="size-5 text-violet-500" />
          Flips Attributed by Subsystem
        </CardTitle>
      </CardHeader>
      <CardContent>
        {data.length === 0 ? (
          <p className="py-8 text-center text-sm italic text-muted-foreground">
            No subsystem caused any decision flip.
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
                  dataKey="name"
                  type="category"
                  width={150}
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
                />
                <Bar dataKey="flips" radius={[0, 4, 4, 0]} isAnimationActive={false}>
                  {data.map((d) => (
                    <Cell key={d.name} fill={d.color} />
                  ))}
                  <LabelList
                    dataKey="flips"
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
