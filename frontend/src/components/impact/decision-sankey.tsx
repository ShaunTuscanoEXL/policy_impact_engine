"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import type { ImpactSummary } from "@/lib/types";

interface DecisionFlowChartProps {
  summary: ImpactSummary;
}

export function DecisionFlowChart({ summary }: DecisionFlowChartProps) {
  const { decision_changes } = summary;

  const data = [
    {
      name: "Approved",
      Baseline: decision_changes.baseline_approved,
      Simulated: decision_changes.simulated_approved,
    },
    {
      name: "Rejected",
      Baseline: decision_changes.baseline_rejected,
      Simulated: decision_changes.simulated_rejected,
    },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Decision Flow</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={data}
              margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis dataKey="name" className="text-sm" />
              <YAxis className="text-sm" />
              <Tooltip
                contentStyle={{
                  backgroundColor: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "8px",
                }}
              />
              <Legend />
              <Bar
                dataKey="Baseline"
                fill="hsl(215, 70%, 60%)"
                radius={[4, 4, 0, 0]}
              />
              <Bar
                dataKey="Simulated"
                fill="hsl(150, 60%, 50%)"
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-4 flex justify-center gap-8 text-sm text-muted-foreground">
          <div>
            Approved to Rejected:{" "}
            <span className="font-semibold text-red-600">
              {decision_changes.approved_to_rejected}
            </span>
          </div>
          <div>
            Rejected to Approved:{" "}
            <span className="font-semibold text-green-600">
              {decision_changes.rejected_to_approved}
            </span>
          </div>
          <div>
            Unchanged:{" "}
            <span className="font-semibold">
              {decision_changes.unchanged}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
