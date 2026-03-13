"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  FileText,
  PlayCircle,
  GitCompare,
  TrendingUp,
  Loader2,
} from "lucide-react";

interface StatsCardsProps {
  brdCount: number | null;
  simulationCount: number | null;
  scenarioCount: number | null;
  latestImpactRate: number | null;
  loading: boolean;
}

const stats = [
  {
    key: "brds" as const,
    label: "Total BRDs",
    icon: FileText,
    color: "text-blue-600",
    bgColor: "bg-blue-100 dark:bg-blue-900/30",
  },
  {
    key: "simulations" as const,
    label: "Total Simulations",
    icon: PlayCircle,
    color: "text-green-600",
    bgColor: "bg-green-100 dark:bg-green-900/30",
  },
  {
    key: "scenarios" as const,
    label: "Active Scenarios",
    icon: GitCompare,
    color: "text-purple-600",
    bgColor: "bg-purple-100 dark:bg-purple-900/30",
  },
  {
    key: "impact" as const,
    label: "Latest Impact Rate",
    icon: TrendingUp,
    color: "text-orange-600",
    bgColor: "bg-orange-100 dark:bg-orange-900/30",
  },
];

export function StatsCards({
  brdCount,
  simulationCount,
  scenarioCount,
  latestImpactRate,
  loading,
}: StatsCardsProps) {
  function getValue(key: string): string {
    if (loading) return "...";
    switch (key) {
      case "brds":
        return brdCount !== null ? String(brdCount) : "0";
      case "simulations":
        return simulationCount !== null ? String(simulationCount) : "0";
      case "scenarios":
        return scenarioCount !== null ? String(scenarioCount) : "0";
      case "impact":
        return latestImpactRate !== null
          ? `${latestImpactRate.toFixed(1)}%`
          : "N/A";
      default:
        return "0";
    }
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {stats.map((stat) => {
        const Icon = stat.icon;
        return (
          <Card key={stat.key}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {stat.label}
              </CardTitle>
              <div className={`rounded-md p-2 ${stat.bgColor}`}>
                <Icon className={`h-4 w-4 ${stat.color}`} />
              </div>
            </CardHeader>
            <CardContent>
              {loading ? (
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              ) : (
                <div className="text-2xl font-bold">{getValue(stat.key)}</div>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
