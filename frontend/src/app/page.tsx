"use client";

import { useEffect, useState } from "react";
import api from "@/lib/api";
import type { BrdDocument, Simulation, Scenario, SimulationResult } from "@/lib/types";
import { PageTransition, StaggerContainer, StaggerItem } from "@/components/page-transition";
import { StatsCards } from "@/components/dashboard/stats-cards";
import { RecentSimulations } from "@/components/dashboard/recent-simulations";
import { ImpactChart } from "@/components/dashboard/impact-chart";
import { QuickActions } from "@/components/dashboard/quick-actions";

export default function DashboardPage() {
  const [loading, setLoading] = useState(true);
  const [brdCount, setBrdCount] = useState<number | null>(null);
  const [simulationCount, setSimulationCount] = useState<number | null>(null);
  const [scenarioCount, setScenarioCount] = useState<number | null>(null);
  const [latestImpactRate, setLatestImpactRate] = useState<number | null>(null);
  const [recentSimulations, setRecentSimulations] = useState<Simulation[]>([]);

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
          if (latestCompleted) {
            try {
              const { data: result } = await api.get<SimulationResult>(
                `/simulations/${latestCompleted.id}/results`
              );
              if (result?.summary_stats?.affected_percentage != null) {
                setLatestImpactRate(result.summary_stats.affected_percentage);
              }
            } catch {
              // Results may not be available
            }
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
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            Overview of policy simulations and impact analysis
          </p>
        </div>

        {/* Bento Grid */}
        <StaggerContainer className="grid grid-cols-4 gap-4">
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
            <ImpactChart simulations={recentSimulations} />
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
