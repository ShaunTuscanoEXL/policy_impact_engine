"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import api from "@/lib/api";
import type { Simulation, SimulationResult } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ArrowLeft, AlertCircle, Loader2 } from "lucide-react";
import { SummaryCards } from "@/components/impact/summary-cards";
import { DecisionFlowChart } from "@/components/impact/decision-sankey";
import { SegmentTable } from "@/components/impact/segment-table";
import { FinancialPanel } from "@/components/impact/financial-panel";

interface SimulationWithResults extends Simulation {
  results: SimulationResult[];
}

const statusVariant: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  COMPLETED: "default",
  RUNNING: "secondary",
  PENDING: "outline",
  FAILED: "destructive",
};

export default function SimulationDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [simulation, setSimulation] = useState<SimulationWithResults | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchSimulation() {
      try {
        setLoading(true);
        const { data } = await api.get<SimulationWithResults>(`/simulations/${id}`);
        setSimulation(data);
      } catch (err: any) {
        setError(err?.response?.data?.detail || "Failed to load simulation.");
      } finally {
        setLoading(false);
      }
    }
    fetchSimulation();
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !simulation) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <AlertCircle className="h-10 w-10 text-destructive" />
        <p className="text-lg text-muted-foreground">{error || "Simulation not found."}</p>
        <Link href="/simulations" className={buttonVariants({ variant: "outline" })}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Simulations
        </Link>
      </div>
    );
  }

  const result = simulation.results?.[0];
  const summary = result?.summary_stats;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold tracking-tight">
              {simulation.scenario_name}
            </h1>
            <Badge variant={statusVariant[simulation.status] ?? "outline"}>
              {simulation.status}
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground">
            Created {new Date(simulation.created_at).toLocaleDateString("en-US", {
              year: "numeric",
              month: "long",
              day: "numeric",
            })}
            {simulation.completed_at &&
              ` \u00b7 Completed ${new Date(simulation.completed_at).toLocaleDateString("en-US", {
                year: "numeric",
                month: "long",
                day: "numeric",
              })}`}
          </p>
        </div>
        <Link href="/simulations" className={buttonVariants({ variant: "outline" })}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Simulations
        </Link>
      </div>

      <Separator />

      {/* No results state */}
      {!result || !summary ? (
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <AlertCircle className="h-10 w-10 text-muted-foreground" />
          <p className="text-lg text-muted-foreground">
            {simulation.status === "RUNNING"
              ? "Simulation is still running. Results will appear here once complete."
              : simulation.status === "PENDING"
                ? "Simulation is queued. Results will appear once processing begins."
                : "No results available for this simulation."}
          </p>
        </div>
      ) : (
        <>
          {/* Summary Cards */}
          <SummaryCards summary={summary} />

          {/* Decision Flow Chart */}
          <DecisionFlowChart summary={summary} />

          {/* Segment Breakdown */}
          {summary.segment_breakdown &&
            Object.keys(summary.segment_breakdown).length > 0 && (
              <SegmentTable segmentBreakdown={summary.segment_breakdown} />
            )}

          {/* Financial Impact Panel */}
          {summary.financial_impact &&
            Object.keys(summary.financial_impact).length > 0 && (
              <FinancialPanel financialImpact={summary.financial_impact} />
            )}
        </>
      )}
    </div>
  );
}
