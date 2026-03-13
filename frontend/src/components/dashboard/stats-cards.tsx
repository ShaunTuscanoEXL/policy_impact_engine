"use client";

import { Card, CardContent } from "@/components/ui/card";
import { HoverCard, StaggerItem } from "@/components/page-transition";
import { FileText, PlayCircle, GitCompare, BarChart3 } from "lucide-react";

interface StatsCardsProps {
  brdCount: number | null;
  simulationCount: number | null;
  scenarioCount: number | null;
  latestImpactRate: number | null;
  loading: boolean;
}

export function StatsCards({ brdCount, simulationCount, scenarioCount, latestImpactRate, loading }: StatsCardsProps) {
  const cards = [
    { label: "BRD Documents", value: brdCount, icon: FileText },
    { label: "Simulations", value: simulationCount, icon: PlayCircle },
    { label: "Scenarios", value: scenarioCount, icon: GitCompare },
    { label: "Avg Impact Rate", value: latestImpactRate != null ? `${latestImpactRate.toFixed(1)}%` : "\u2014", icon: BarChart3 },
  ];

  return (
    <>
      {cards.map((card) => (
        <StaggerItem key={card.label}>
          <HoverCard>
            <Card className="relative overflow-hidden border-border/50 shadow-sm">
              <CardContent className="p-6">
                <card.icon className="absolute top-4 right-4 h-8 w-8 text-muted-foreground/10" />
                <p className="text-sm font-medium text-muted-foreground">{card.label}</p>
                {loading ? (
                  <div className="mt-1 h-9 w-16 animate-pulse rounded bg-muted" />
                ) : (
                  <p className="mt-1 text-3xl font-semibold tracking-tight">
                    {typeof card.value === "number" ? card.value : card.value}
                  </p>
                )}
              </CardContent>
            </Card>
          </HoverCard>
        </StaggerItem>
      ))}
    </>
  );
}
