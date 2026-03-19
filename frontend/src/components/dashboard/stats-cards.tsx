"use client";

import { Card, CardContent } from "@/components/ui/card";
import { HoverCard, StaggerItem } from "@/components/page-transition";
import { FileText, Database, FlaskConical } from "lucide-react";

interface StatsCardsProps {
  brdCount: number | null;
  loading: boolean;
}

export function StatsCards({ brdCount, loading }: StatsCardsProps) {
  const cards = [
    { label: "BRD Documents", value: brdCount, icon: FileText, accent: "from-blue-500 to-blue-600", iconBg: "bg-blue-50 dark:bg-blue-500/10", iconColor: "text-blue-600 dark:text-blue-400", dotColor: "bg-blue-500" },
    { label: "Loan Records", value: "\u2014", icon: Database, accent: "from-emerald-500 to-emerald-600", iconBg: "bg-emerald-50 dark:bg-emerald-500/10", iconColor: "text-emerald-600 dark:text-emerald-400", dotColor: "bg-emerald-500" },
    { label: "Test Suites", value: "\u2014", icon: FlaskConical, accent: "from-pink-500 to-pink-600", iconBg: "bg-pink-50 dark:bg-pink-500/10", iconColor: "text-pink-600 dark:text-pink-400", dotColor: "bg-pink-500" },
  ];

  return (
    <>
      {cards.map((card) => (
        <StaggerItem key={card.label}>
          <HoverCard>
            <Card className="card-elevated card-glow relative overflow-hidden border-border/40 cursor-pointer">
              <div className={`absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r ${card.accent}`} />
              <CardContent className="p-5">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-3">
                      <div className={`h-1.5 w-1.5 rounded-full ${card.dotColor}`} />
                      <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{card.label}</p>
                    </div>
                    {loading ? (
                      <div className="h-9 w-16 animate-pulse rounded-lg bg-muted" />
                    ) : (
                      <p className="text-3xl font-bold tracking-tight tabular-nums text-foreground">
                        {typeof card.value === "number" ? card.value : card.value}
                      </p>
                    )}
                  </div>
                  <div className={`flex size-10 items-center justify-center rounded-xl ${card.iconBg}`}>
                    <card.icon className={`h-5 w-5 ${card.iconColor}`} />
                  </div>
                </div>
              </CardContent>
            </Card>
          </HoverCard>
        </StaggerItem>
      ))}
    </>
  );
}
