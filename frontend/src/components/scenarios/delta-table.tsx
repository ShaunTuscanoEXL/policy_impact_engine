"use client";

import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Trophy } from "lucide-react";
import type { SimulationResult } from "@/lib/types";

interface DeltaTableProps {
  results: {
    name: string;
    result: SimulationResult;
  }[];
}

interface MetricRow {
  label: string;
  values: number[];
  bestIndex: number;
  format: (v: number) => string;
  lowerIsBetter?: boolean;
}

export function DeltaTable({ results }: DeltaTableProps) {
  const metrics: MetricRow[] = buildMetrics(results);

  return (
    <Card className="border-border/50 shadow-sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Trophy className="size-5" />
          Delta Comparison
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Metric</TableHead>
              {results.map((r) => (
                <TableHead key={r.name} className="text-right">
                  {r.name}
                </TableHead>
              ))}
              <TableHead className="text-right">Best</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {metrics.map((metric) => (
              <TableRow key={metric.label}>
                <TableCell className="font-medium">{metric.label}</TableCell>
                {metric.values.map((val, i) => {
                  const isBest = i === metric.bestIndex;
                  const isWorst =
                    results.length > 1 &&
                    i ===
                      metric.values.indexOf(
                        metric.lowerIsBetter
                          ? Math.max(...metric.values)
                          : Math.min(...metric.values)
                      );
                  return (
                    <TableCell
                      key={results[i].name}
                      className={`text-right tabular-nums ${
                        isBest
                          ? "text-green-600 font-semibold dark:text-green-400"
                          : isWorst
                            ? "text-red-600 dark:text-red-400"
                            : ""
                      }`}
                    >
                      {metric.format(val)}
                    </TableCell>
                  );
                })}
                <TableCell className="text-right">
                  <Badge
                    variant="outline"
                    className="border-green-200 bg-green-50 text-green-700 dark:border-green-800 dark:bg-green-950 dark:text-green-400"
                  >
                    {results[metric.bestIndex].name}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function buildMetrics(
  results: { name: string; result: SimulationResult }[]
): MetricRow[] {
  const fmtNum = (v: number) => v.toLocaleString();
  const fmtPct = (v: number) => `${v.toFixed(2)}%`;
  const fmtDelta = (v: number) =>
    `${v >= 0 ? "+" : ""}${v.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;

  const affectedValues = results.map(
    (r) => r.result.summary_stats.affected_customers
  );

  const approvalRateValues = results.map((r) => {
    const stats = r.result.summary_stats;
    const total = stats.total_customers || 1;
    const baseApproved = stats.decision_changes.baseline_approved ?? 0;
    const simApproved = stats.decision_changes.simulated_approved ?? 0;
    return ((simApproved - baseApproved) / total) * 100;
  });

  const avgDeltaValues = results.map(
    (r) => r.result.summary_stats.amount_changes.avg_delta
  );

  const exposureValues = results.map(
    (r) => r.result.summary_stats.amount_changes.total_delta
  );

  const revenueValues = results.map((r) => {
    const fi = r.result.summary_stats.financial_impact ?? {};
    return (fi as Record<string, number>).revenue_impact ??
      (fi as Record<string, number>).total_revenue_change ??
      r.result.summary_stats.amount_changes.total_delta;
  });

  const findBest = (values: number[], lowerIsBetter = false) => {
    if (lowerIsBetter) {
      return values.indexOf(Math.min(...values));
    }
    return values.indexOf(Math.max(...values));
  };

  return [
    {
      label: "Total Affected",
      values: affectedValues,
      bestIndex: findBest(affectedValues, true),
      format: fmtNum,
      lowerIsBetter: true,
    },
    {
      label: "Approval Rate Change",
      values: approvalRateValues,
      bestIndex: findBest(approvalRateValues),
      format: fmtPct,
    },
    {
      label: "Avg Amount Delta",
      values: avgDeltaValues,
      bestIndex: findBest(avgDeltaValues),
      format: fmtDelta,
    },
    {
      label: "Exposure Change",
      values: exposureValues,
      bestIndex: findBest(exposureValues, true),
      format: fmtDelta,
      lowerIsBetter: true,
    },
    {
      label: "Revenue Impact",
      values: revenueValues,
      bestIndex: findBest(revenueValues),
      format: fmtDelta,
    },
  ];
}
