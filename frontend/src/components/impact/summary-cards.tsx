"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Users,
  ArrowDownRight,
  ArrowUpRight,
  Activity,
  ShieldAlert,
} from "lucide-react";
import {
  StaggerContainer,
  StaggerItem,
  HoverCard,
} from "@/components/page-transition";
import type { ImpactRunSummary } from "@/lib/types";

interface SummaryCardsProps {
  summary: ImpactRunSummary;
}

/** Hero KPI strip at the top of an impact-run detail page. Inspired by
 * the master branch's SummaryCards but adapted to our (base, candidate)
 * decision_distribution shape. */
export function SummaryCards({ summary }: SummaryCardsProps) {
  const flips = summary.decision_flips ?? {};
  const totalFlips = Object.values(flips).reduce((acc, n) => acc + n, 0);
  const totalLoans = summary.total_loans ?? 0;
  const affectedPct = totalLoans > 0 ? (totalFlips / totalLoans) * 100 : 0;

  // Net rejected change = (cand REJECTED + FAILED) - base REJECTED
  const baseRej = summary.decision_distribution.base?.REJECTED ?? 0;
  const candRej = summary.decision_distribution.candidate?.REJECTED ?? 0;
  const rejDelta = candRej - baseRej;

  // Net approved change
  const baseAppr =
    (summary.decision_distribution.base?.APPROVED ?? 0) +
    (summary.decision_distribution.base?.FLAGGED ?? 0);
  const candAppr =
    (summary.decision_distribution.candidate?.APPROVED ?? 0) +
    (summary.decision_distribution.candidate?.FLAGGED ?? 0);
  const apprDelta = candAppr - baseAppr;

  // Top subsystem driving flips
  const subsystems = Object.entries(summary.by_subsystem ?? {})
    .map(([name, info]) => ({ name, count: info.flips_caused }))
    .sort((a, b) => b.count - a.count);
  const topSubsystem = subsystems[0];

  const cards = [
    {
      label: "Affected Loans",
      value: `${totalFlips.toLocaleString()}`,
      detail: `${affectedPct.toFixed(1)}% of ${totalLoans.toLocaleString()}`,
      icon: Users,
      color: "text-blue-600",
      bg: "bg-blue-100 dark:bg-blue-900/30",
    },
    {
      label: "Net Rejected",
      value: `${rejDelta >= 0 ? "+" : ""}${rejDelta.toLocaleString()}`,
      detail: `${baseRej.toLocaleString()} → ${candRej.toLocaleString()}`,
      icon: rejDelta >= 0 ? ArrowDownRight : ArrowUpRight,
      color: rejDelta > 0 ? "text-red-600" : rejDelta < 0 ? "text-green-600" : "text-muted-foreground",
      bg:
        rejDelta > 0
          ? "bg-red-100 dark:bg-red-900/30"
          : rejDelta < 0
            ? "bg-green-100 dark:bg-green-900/30"
            : "bg-muted",
    },
    {
      label: "Net Approved",
      value: `${apprDelta >= 0 ? "+" : ""}${apprDelta.toLocaleString()}`,
      detail: `${baseAppr.toLocaleString()} → ${candAppr.toLocaleString()}`,
      icon: apprDelta >= 0 ? ArrowUpRight : ArrowDownRight,
      color: apprDelta > 0 ? "text-green-600" : apprDelta < 0 ? "text-red-600" : "text-muted-foreground",
      bg:
        apprDelta > 0
          ? "bg-green-100 dark:bg-green-900/30"
          : apprDelta < 0
            ? "bg-red-100 dark:bg-red-900/30"
            : "bg-muted",
    },
    {
      label: "Top Driver",
      value: topSubsystem?.name ?? "—",
      detail: topSubsystem
        ? `${topSubsystem.count.toLocaleString()} flips`
        : "No subsystem flips",
      icon: topSubsystem ? Activity : ShieldAlert,
      color: topSubsystem ? "text-violet-600" : "text-muted-foreground",
      bg: topSubsystem
        ? "bg-violet-100 dark:bg-violet-900/30"
        : "bg-muted",
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
                  <div className={`rounded-md p-2 ${card.bg}`}>
                    <Icon className={`h-4 w-4 ${card.color}`} />
                  </div>
                </CardHeader>
                <CardContent>
                  <div className={`text-2xl font-bold ${card.color}`}>{card.value}</div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {card.detail}
                  </div>
                </CardContent>
              </Card>
            </HoverCard>
          </StaggerItem>
        );
      })}
    </StaggerContainer>
  );
}
