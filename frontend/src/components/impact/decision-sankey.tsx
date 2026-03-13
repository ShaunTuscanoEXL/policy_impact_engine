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
    <Card className="border-border/50 shadow-sm">
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
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.04)" />
              <XAxis dataKey="name" className="text-sm" />
              <YAxis className="text-sm" />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#171717",
                  border: "none",
                  borderRadius: "8px",
                  color: "#ededed",
                  fontSize: "12px",
                }}
              />
              <Legend />
              <Bar
                dataKey="Baseline"
                fill="#0070f3"
                radius={[4, 4, 0, 0]}
              />
              <Bar
                dataKey="Simulated"
                fill="#60a5fa"
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
