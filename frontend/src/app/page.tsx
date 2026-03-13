"use client";

import { useEffect, useState } from "react";
import api from "@/lib/api";
import type { BrdDocument, Simulation, Scenario, SimulationResult } from "@/lib/types";
import { PageTransition, StaggerContainer, StaggerItem } from "@/components/page-transition";
import { StatsCards } from "@/components/dashboard/stats-cards";
import { RecentSimulations } from "@/components/dashboard/recent-simulations";
import { ImpactChart } from "@/components/dashboard/impact-chart";
import { QuickActions } from "@/components/dashboard/quick-actions";
import { LayoutDashboard } from "lucide-react";

export default function DashboardPage() {
  const [loading, setLoading] = useState(true);
  const [brdCount, setBrdCount] = useState<number | null>(null);
  const [simulationCount, setSimulationCount] = useState<number | null>(null);
  const [scenarioCount, setScenarioCount] = useState<number | null>(null);
  const [latestImpactRate, setLatestImpactRate] = useState<number | null>(null);
  const [recentSimulations, setRecentSimulations] = useState<Simulation[]>([]);
  const [chartData, setChartData] = useState<{ name: string; date: string; impact: number }[]>([]);

  useEffect(() => {
    async function fetchDashboardData() {
      setLoading(true);
      try {
        const results = await Promise.allSettled([
          api.get<BrdDocument[]>("/brds"),
          api.get<Simulation[]>("/simulations"),
          api.get<Scenario[]>("/scenarios"),
        ]);

        if (results[0].status === "fulfilled") {
          setBrdCount(results[0].value.data.length);
        }

        if (results[1].status === "fulfilled") {
          const simulations = results[1].value.data;
          setSimulationCount(simulations.length);
          const sorted = [...simulations].sort(
            (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
          );
          setRecentSimulations(sorted.slice(0, 10));

          const latestCompleted = sorted.find((s) => s.status === "COMPLETED");
          // Fetch results for completed simulations (for chart + impact rate)
          const completedSims = sorted.filter((s) => s.status === "COMPLETED").slice(0, 10);
          const resultPromises = completedSims.map((s) =>
            api.get<SimulationResult[]>(`/simulations/${s.id}/results`).catch(() => null)
          );
          const resultResponses = await Promise.all(resultPromises);

          const points: { name: string; date: string; impact: number }[] = [];
          for (let i = 0; i < completedSims.length; i++) {
            const res = resultResponses[i];
            const r = Array.isArray(res?.data) ? res?.data[0] : res?.data;
            const pct = r?.summary_stats?.affected_percentage;
            if (pct != null) {
              points.push({
                name: completedSims[i].scenario_name || `Sim ${i + 1}`,
                date: new Date(completedSims[i].created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
                impact: pct,
              });
            }
          }
          setChartData(points.reverse());

          // Set latest impact rate from first completed
          if (points.length > 0) {
            setLatestImpactRate(points[points.length - 1].impact);
          }
        }

        if (results[2].status === "fulfilled") {
          setScenarioCount(results[2].value.data.length);
        }
      } catch {
        // Errors handled per-request
      } finally {
        setLoading(false);
      }
    }

    fetchDashboardData();
  }, []);

  return (
    <PageTransition>
      <div className="space-y-8">
        {/* Header */}
        <div className="flex items-center gap-4">
          <div className="icon-badge bg-blue-100 dark:bg-blue-900/30">
            <LayoutDashboard className="size-5 text-blue-600 dark:text-blue-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              <span className="text-gradient">Dashboard</span>
            </h1>
            <p className="text-sm text-muted-foreground">
              Overview of policy simulations and impact analysis
            </p>
          </div>
        </div>

        {/* Bento Grid */}
        <StaggerContainer className="grid grid-cols-4 gap-5">
          {/* Row 1: 4 stat cards */}
          <StatsCards
            brdCount={brdCount}
            simulationCount={simulationCount}
            scenarioCount={scenarioCount}
            latestImpactRate={latestImpactRate}
            loading={loading}
          />

          {/* Row 2: Recent table (span 2) + Chart (span 2) */}
          <StaggerItem className="col-span-2">
            <RecentSimulations simulations={recentSimulations} loading={loading} />
          </StaggerItem>
          <StaggerItem className="col-span-2">
            <ImpactChart data={chartData} />
          </StaggerItem>

          {/* Row 3: Quick Actions (span 4) */}
          <StaggerItem className="col-span-4">
            <QuickActions />
          </StaggerItem>
        </StaggerContainer>
      </div>
    </PageTransition>
  );
}
