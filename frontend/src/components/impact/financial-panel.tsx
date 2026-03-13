"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TrendingDown, TrendingUp, DollarSign } from "lucide-react";

interface FinancialPanelProps {
  financialImpact: Record<string, any>;
}

export function FinancialPanel({ financialImpact }: FinancialPanelProps) {
  const baselineExposure = financialImpact.total_baseline_exposure ?? 0;
  const simulatedExposure = financialImpact.total_simulated_exposure ?? 0;
  const exposureChange = financialImpact.exposure_change ?? simulatedExposure - baselineExposure;

  const revenueBaseline = financialImpact.estimated_revenue_baseline ?? 0;
  const revenueSimulated = financialImpact.estimated_revenue_simulated ?? 0;
  const revenueDelta = revenueSimulated - revenueBaseline;

  const avgRateBaseline = financialImpact.avg_rate_baseline ?? 0;
  const avgRateSimulated = financialImpact.avg_rate_simulated ?? 0;
  const rateDelta = avgRateSimulated - avgRateBaseline;

  const cards = [
    {
      title: "Total Exposure Change",
      baseline: formatCurrency(baselineExposure),
      simulated: formatCurrency(simulatedExposure),
      delta: exposureChange,
      deltaFormatted: formatCurrency(exposureChange),
      icon: DollarSign,
    },
    {
      title: "Revenue Impact",
      baseline: formatCurrency(revenueBaseline),
      simulated: formatCurrency(revenueSimulated),
      delta: revenueDelta,
      deltaFormatted: formatCurrency(revenueDelta),
      icon: DollarSign,
    },
    {
      title: "Average Rate Change",
      baseline: `${avgRateBaseline.toFixed(2)}%`,
      simulated: `${avgRateSimulated.toFixed(2)}%`,
      delta: rateDelta,
      deltaFormatted: `${rateDelta >= 0 ? "+" : ""}${rateDelta.toFixed(2)}%`,
      icon: rateDelta >= 0 ? TrendingUp : TrendingDown,
    },
  ];

  return (
    <div className="grid gap-4 md:grid-cols-3">
      {cards.map((card) => {
        const Icon = card.icon;
        const isPositive = card.delta >= 0;
        return (
          <Card key={card.title}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {card.title}
              </CardTitle>
              <div
                className={`rounded-md p-2 ${
                  isPositive
                    ? "bg-green-100 dark:bg-green-900/30"
                    : "bg-red-100 dark:bg-red-900/30"
                }`}
              >
                <Icon
                  className={`h-4 w-4 ${
                    isPositive ? "text-green-600" : "text-red-600"
                  }`}
                />
              </div>
            </CardHeader>
            <CardContent className="space-y-2">
              <div
                className={`text-2xl font-bold ${
                  isPositive ? "text-green-600" : "text-red-600"
                }`}
              >
                {card.deltaFormatted}
              </div>
              <div className="flex justify-between text-sm text-muted-foreground">
                <span>Baseline: {card.baseline}</span>
                <span>Simulated: {card.simulated}</span>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

function formatCurrency(value: number): string {
  const abs = Math.abs(value);
  const prefix = value >= 0 ? "+" : "-";
  if (abs >= 1_000_000) {
    return `${prefix}$${(abs / 1_000_000).toFixed(1)}M`;
  }
  if (abs >= 1_000) {
    return `${prefix}$${(abs / 1_000).toFixed(1)}K`;
  }
  return `${prefix}$${abs.toFixed(0)}`;
}
