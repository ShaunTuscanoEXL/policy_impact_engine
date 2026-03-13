"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  TrendingDown,
  TrendingUp,
  DollarSign,
  ShieldAlert,
  Receipt,
  Landmark,
} from "lucide-react";

interface FinancialPanelProps {
  financialImpact: Record<string, any>;
}

export function FinancialPanel({ financialImpact }: FinancialPanelProps) {
  const fi = financialImpact;

  const exposureChange = fi.exposure_change ?? 0;
  const interestDelta = fi.interest_income_delta ?? 0;
  const expectedLossDelta = fi.expected_loss_delta ?? 0;
  const originationDelta = fi.origination_fee_delta ?? (fi.revenue_impact ?? 0);
  const netRevenueDelta = fi.net_revenue_delta ?? 0;
  const rateDelta = (fi.avg_rate_simulated ?? 0) - (fi.avg_rate_baseline ?? 0);

  const cards = [
    {
      title: "Total Exposure Change",
      baseline: formatCurrency(fi.total_baseline_exposure ?? 0),
      simulated: formatCurrency(fi.total_simulated_exposure ?? 0),
      delta: exposureChange,
      deltaFormatted: formatCurrency(exposureChange),
      icon: DollarSign,
    },
    {
      title: "Interest Income Delta",
      baseline: formatCurrency(fi.interest_income_baseline ?? 0),
      simulated: formatCurrency(fi.interest_income_simulated ?? 0),
      delta: interestDelta,
      deltaFormatted: formatCurrency(interestDelta),
      icon: interestDelta >= 0 ? TrendingUp : TrendingDown,
    },
    {
      title: "Expected Loss Delta",
      baseline: formatCurrency(fi.expected_loss_baseline ?? 0),
      simulated: formatCurrency(fi.expected_loss_simulated ?? 0),
      delta: expectedLossDelta,
      deltaFormatted: formatCurrency(expectedLossDelta),
      icon: ShieldAlert,
      invertColor: true, // higher loss = bad
    },
    {
      title: "Origination Fee Delta",
      baseline: formatCurrency(fi.origination_fee_baseline ?? fi.estimated_revenue_baseline ?? 0),
      simulated: formatCurrency(fi.origination_fee_simulated ?? fi.estimated_revenue_simulated ?? 0),
      delta: originationDelta,
      deltaFormatted: formatCurrency(originationDelta),
      icon: Receipt,
    },
    {
      title: "Net Revenue Delta",
      baseline: formatCurrency(fi.net_revenue_baseline ?? 0),
      simulated: formatCurrency(fi.net_revenue_simulated ?? 0),
      delta: netRevenueDelta,
      deltaFormatted: formatCurrency(netRevenueDelta),
      icon: Landmark,
    },
    {
      title: "Average Rate Change",
      baseline: `${(fi.avg_rate_baseline ?? 0).toFixed(2)}%`,
      simulated: `${(fi.avg_rate_simulated ?? 0).toFixed(2)}%`,
      delta: rateDelta,
      deltaFormatted: `${rateDelta >= 0 ? "+" : ""}${rateDelta.toFixed(2)}%`,
      icon: rateDelta >= 0 ? TrendingUp : TrendingDown,
    },
  ];

  return (
    <div className="grid gap-4 grid-cols-2 lg:grid-cols-3">
      {cards.map((card) => {
        const Icon = card.icon;
        const invertColor = "invertColor" in card && card.invertColor;
        const isPositive = invertColor ? card.delta <= 0 : card.delta >= 0;
        return (
          <Card key={card.title} className="card-elevated border-border/40">
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
