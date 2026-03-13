"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import api from "@/lib/api";
import type { BrdDocument, Simulation, Scenario, SimulationResult } from "@/lib/types";
import { StatsCards } from "@/components/dashboard/stats-cards";
import { RecentSimulations } from "@/components/dashboard/recent-simulations";
import { Button } from "@/components/ui/button";
import { Upload } from "lucide-react";

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

        // BRDs count
        if (results[0].status === "fulfilled") {
          setBrdCount(results[0].value.data.length);
        }

        // Simulations count + recent list
        if (results[1].status === "fulfilled") {
          const simulations = results[1].value.data;
          setSimulationCount(simulations.length);

          // Sort by created_at descending and take first 10
          const sorted = [...simulations].sort(
            (a, b) =>
              new Date(b.created_at).getTime() -
              new Date(a.created_at).getTime()
          );
          setRecentSimulations(sorted.slice(0, 10));

          // Find latest completed simulation for impact rate
          const latestCompleted = sorted.find(
            (s) => s.status === "COMPLETED"
          );
          if (latestCompleted) {
            try {
              const { data: result } = await api.get<SimulationResult>(
                `/simulations/${latestCompleted.id}/results`
              );
              if (result?.summary_stats?.affected_percentage != null) {
                setLatestImpactRate(result.summary_stats.affected_percentage);
              }
            } catch {
              // Results may not be available, that's okay
            }
          }
        }

        // Scenarios count
        if (results[2].status === "fulfilled") {
          setScenarioCount(results[2].value.data.length);
        }
      } catch {
        // Errors are handled per-request above
      } finally {
        setLoading(false);
      }
    }

    fetchDashboardData();
  }, []);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="mt-1 text-muted-foreground">
            Overview of policy simulations and impact analysis.
          </p>
        </div>
        <div className="flex gap-3">
          <Link href="/brds">
            <Button variant="outline">
              <Upload className="mr-2 h-4 w-4" />
              Upload BRD
            </Button>
          </Link>
          <Link href="/datasets">
            <Button variant="outline">
              <Upload className="mr-2 h-4 w-4" />
              Upload Dataset
            </Button>
          </Link>
        </div>
      </div>

      {/* Stats Cards */}
      <StatsCards
        brdCount={brdCount}
        simulationCount={simulationCount}
        scenarioCount={scenarioCount}
        latestImpactRate={latestImpactRate}
        loading={loading}
      />

      {/* Recent Simulations Table */}
      <RecentSimulations simulations={recentSimulations} loading={loading} />
    </div>
  );
}
