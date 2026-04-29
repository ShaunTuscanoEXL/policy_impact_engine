"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  CartesianGrid,
  LabelList,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { GitBranch } from "lucide-react";
import type { ImpactRunSummary } from "@/lib/types";

interface DistributionChartProps {
  summary: ImpactRunSummary;
}

const DECISION_ORDER = ["APPROVED", "FLAGGED", "REJECTED"] as const;

/** Side-by-side bar chart of decision distribution at base vs candidate
 * version. Inspired by master's DecisionFlowChart, expanded to include
 * the FLAGGED state we have on top of APPROVED/REJECTED. */
export function DistributionChart({ summary }: DistributionChartProps) {
  const base = summary.decision_distribution.base ?? {};
  const cand = summary.decision_distribution.candidate ?? {};

  const data = DECISION_ORDER.map((d) => ({
    name: d,
    Baseline: base[d] ?? 0,
    Candidate: cand[d] ?? 0,
  }));

  return (
    <Card className="card-elevated border-border/40">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <GitBranch className="size-5 text-blue-500" />
          Decision Distribution
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[280px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={data}
              margin={{ top: 12, right: 30, left: 12, bottom: 5 }}
              barCategoryGap="20%"
            >
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.04)" />
              <XAxis dataKey="name" className="text-sm" />
              <YAxis className="text-sm" />
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
              <Legend />
              <Bar
                dataKey="Baseline"
                fill="#94a3b8"
                radius={[4, 4, 0, 0]}
                isAnimationActive={false}
              >
                <LabelList dataKey="Baseline" position="top" fontSize={11} />
              </Bar>
              <Bar
                dataKey="Candidate"
                fill="#60a5fa"
                radius={[4, 4, 0, 0]}
                isAnimationActive={false}
              >
                <LabelList dataKey="Candidate" position="top" fontSize={11} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
