"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Users,
  ArrowDownRight,
  ArrowUpRight,
  DollarSign,
} from "lucide-react";
import type { ImpactSummary } from "@/lib/types";
import { StaggerContainer, StaggerItem, HoverCard } from "@/components/page-transition";

interface SummaryCardsProps {
  summary: ImpactSummary;
}

export function SummaryCards({ summary }: SummaryCardsProps) {
  const cards = [
    {
      label: "Affected Customers",
      value: `${summary.affected_customers} (${summary.affected_percentage.toFixed(1)}%)`,
      icon: Users,
      color: "text-blue-600",
      bgColor: "bg-blue-100 dark:bg-blue-900/30",
    },
    {
      label: "Approved \u2192 Rejected",
      value: String(summary.decision_changes.approved_to_rejected),
      icon: ArrowDownRight,
      color: "text-red-600",
      bgColor: "bg-red-100 dark:bg-red-900/30",
    },
    {
      label: "Rejected \u2192 Approved",
      value: String(summary.decision_changes.rejected_to_approved),
      icon: ArrowUpRight,
      color: "text-green-600",
      bgColor: "bg-green-100 dark:bg-green-900/30",
    },
    {
      label: "Net Revenue Impact",
      value: formatCurrency(summary.financial_impact.net_revenue_delta ?? summary.financial_impact.exposure_change ?? 0),
      icon: DollarSign,
      color:
        (summary.financial_impact.net_revenue_delta ?? summary.financial_impact.exposure_change ?? 0) >= 0
          ? "text-green-600"
          : "text-red-600",
      bgColor:
        (summary.financial_impact.net_revenue_delta ?? summary.financial_impact.exposure_change ?? 0) >= 0
          ? "bg-green-100 dark:bg-green-900/30"
          : "bg-red-100 dark:bg-red-900/30",
    },
  ];

  return (
    <StaggerContainer className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => {
        const Icon = card.icon;
        return (
          <StaggerItem key={card.label}>
          <HoverCard>
          <Card className="card-elevated border-border/40">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {card.label}
              </CardTitle>
              <div className={`rounded-md p-2 ${card.bgColor}`}>
                <Icon className={`h-4 w-4 ${card.color}`} />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{card.value}</div>
            </CardContent>
          </Card>
          </HoverCard>
          </StaggerItem>
        );
      })}
    </StaggerContainer>
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
