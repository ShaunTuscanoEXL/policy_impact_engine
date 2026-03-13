"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import api from "@/lib/api";
import type { Scenario, Simulation, SimulationResult } from "@/lib/types";
import { toast } from "sonner";
import { ComparisonCharts } from "@/components/scenarios/comparison-charts";
import { DeltaTable } from "@/components/scenarios/delta-table";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ArrowLeft, GitCompare, Loader2 } from "lucide-react";

interface SimWithResult {
  simulation: Simulation;
  result: SimulationResult;
}

export default function ScenarioDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [simData, setSimData] = useState<SimWithResult[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchScenario() {
      try {
        const { data: sc } = await api.get(`/scenarios/${params.id}`);
        setScenario(sc);

        // Fetch each simulation and its results in parallel
        const simResults = await Promise.all(
          sc.simulation_ids.map(async (simId: string) => {
            const [simRes, resultRes] = await Promise.all([
              api.get(`/simulations/${simId}`),
              api.get(`/simulations/${simId}/results`).catch(() => null),
            ]);
            return {
              simulation: simRes.data,
              result: resultRes?.data?.[0] ?? null,
            };
          })
        );

        setSimData(
          simResults.filter(
            (s): s is SimWithResult => s.result !== null
          )
        );
      } catch {
        toast.error("Failed to load scenario.");
        router.push("/scenarios");
      } finally {
        setLoading(false);
      }
    }
    fetchScenario();
  }, [params.id, router]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!scenario) return null;

  const chartResults = simData.map((s) => ({
    name: s.simulation.scenario_name,
    result: s.result,
  }));

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start gap-4">
        <Button
          variant="ghost"
          size="icon-sm"
          render={<Link href="/scenarios" />}
        >
          <ArrowLeft className="size-4" />
        </Button>
        <div>
          <div className="flex items-center gap-3">
            <GitCompare className="size-6 text-muted-foreground" />
            <h1 className="text-2xl font-bold tracking-tight">
              {scenario.name}
            </h1>
          </div>
          {scenario.description && (
            <p className="mt-1 ml-10 text-sm text-muted-foreground">
              {scenario.description}
            </p>
          )}
          <div className="mt-2 ml-10 flex flex-wrap items-center gap-2">
            <span className="text-sm text-muted-foreground">
              Comparing:
            </span>
            {simData.map((s) => (
              <Badge key={s.simulation.id} variant="secondary">
                {s.simulation.scenario_name}
              </Badge>
            ))}
          </div>
        </div>
      </div>

      {simData.length < 2 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <GitCompare className="size-10 text-muted-foreground/40" />
            <p className="mt-3 text-sm text-muted-foreground">
              Not enough simulation results available for comparison. At least 2
              completed simulations with results are required.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Comparison Bar Chart */}
          <ComparisonCharts results={chartResults} />

          <Separator />

          {/* Delta Table */}
          <DeltaTable results={chartResults} />
        </>
      )}
    </div>
  );
}
