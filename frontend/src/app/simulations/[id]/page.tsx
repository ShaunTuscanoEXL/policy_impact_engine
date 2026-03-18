"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import api from "@/lib/api";
import type { Simulation, SimulationResult } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ArrowLeft, AlertCircle, Loader2, CheckCircle, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SummaryCards } from "@/components/impact/summary-cards";
import { DecisionFlowChart } from "@/components/impact/decision-sankey";
import { SegmentTable } from "@/components/impact/segment-table";
import { FinancialPanel } from "@/components/impact/financial-panel";
import { PageTransition } from "@/components/page-transition";
import { motion } from "framer-motion";

const statusVariant: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  COMPLETED: "default",
  RUNNING: "secondary",
  PENDING: "outline",
  AWAITING_REVIEW: "outline",
  FAILED: "destructive",
};

export default function SimulationDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [simulation, setSimulation] = useState<Simulation | null>(null);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchSimulation() {
      try {
        setLoading(true);
        const [simRes, resultsRes] = await Promise.all([
          api.get<Simulation>(`/simulations/${id}`),
          api.get<SimulationResult[]>(`/simulations/${id}/results`).catch(() => null),
        ]);
        setSimulation(simRes.data);
        setResult(resultsRes?.data?.[0] ?? null);
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

  const summary = result?.summary_stats;

  return (
    <PageTransition>
    <div className="space-y-6">
      <p className="text-xs text-muted-foreground mb-4">Dashboard / Simulations / Detail</p>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight">
              <span className="text-gradient">{simulation.scenario_name}</span>
            </h1>
            <Badge variant={statusVariant[simulation.status] ?? "outline"}>
              {simulation.status}
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground">
            {simulation.rule_set_name && (
              <><span className="font-medium text-foreground">{simulation.rule_set_name}</span> &middot; </>
            )}
            {simulation.dataset_name && (
              <><span className="font-medium text-foreground">{simulation.dataset_name}</span> &middot; </>
            )}
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
                : simulation.status === "AWAITING_REVIEW"
                  ? "Rules have been extracted and are ready for review."
                  : "No results available for this simulation."}
          </p>
          {simulation.status === "AWAITING_REVIEW" && (
            <Link
              href={`/rules/${simulation.rule_set_id}?simulationId=${simulation.id}`}
              className={buttonVariants({ variant: "default" })}
            >
              <CheckCircle className="mr-2 h-4 w-4" />
              Review &amp; Approve Rules
            </Link>
          )}
        </div>
      ) : (
        <>
          {/* Summary Cards */}
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
          <SummaryCards summary={summary} />
          </motion.div>

          {/* Decision Flow Chart */}
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
          <DecisionFlowChart summary={summary} />
          </motion.div>

          {/* Segment Breakdown */}
          {summary.segment_breakdown &&
            Object.keys(summary.segment_breakdown).length > 0 && (
              <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
              <SegmentTable segmentBreakdown={summary.segment_breakdown} />
              </motion.div>
            )}

          {/* Financial Impact Panel */}
          {summary.financial_impact &&
            Object.keys(summary.financial_impact).length > 0 && (
              <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}>
              <FinancialPanel financialImpact={summary.financial_impact} />
              </motion.div>
            )}

          {/* Amount Changes */}
          {summary.amount_changes && (
            <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
              <AmountChangesPanel amountChanges={summary.amount_changes} />
            </motion.div>
          )}
        </>
      )}
    </div>
    </PageTransition>
  );
}

function AmountChangesPanel({ amountChanges }: { amountChanges: Record<string, any> }) {
  const items = [
    {
      label: "Amount Increased",
      count: amountChanges.increased ?? 0,
      detail: amountChanges.total_increase != null
        ? formatCompactCurrency(amountChanges.total_increase)
        : null,
      icon: TrendingUp,
      color: "text-green-600",
      bgColor: "bg-green-100 dark:bg-green-900/30",
    },
    {
      label: "Amount Decreased",
      count: amountChanges.decreased ?? 0,
      detail: amountChanges.total_decrease != null
        ? formatCompactCurrency(amountChanges.total_decrease)
        : null,
      icon: TrendingDown,
      color: "text-red-600",
      bgColor: "bg-red-100 dark:bg-red-900/30",
    },
    {
      label: "Unchanged",
      count: amountChanges.unchanged ?? 0,
      detail: null,
      icon: Minus,
      color: "text-muted-foreground",
      bgColor: "bg-muted",
    },
  ];

  return (
    <Card className="card-elevated border-border/40">
      <CardHeader>
        <CardTitle className="text-base">Amount Changes</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4 grid-cols-3">
          {items.map((item) => {
            const Icon = item.icon;
            return (
              <div key={item.label} className="flex items-center gap-3">
                <div className={`rounded-md p-2 ${item.bgColor}`}>
                  <Icon className={`h-4 w-4 ${item.color}`} />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">{item.label}</p>
                  <p className="text-lg font-semibold">{item.count}</p>
                  {item.detail && (
                    <p className={`text-xs ${item.color}`}>{item.detail}</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

function formatCompactCurrency(value: number): string {
  const abs = Math.abs(value);
  const prefix = value >= 0 ? "+" : "-";
  if (abs >= 1_000_000) return `${prefix}$${(abs / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${prefix}$${(abs / 1_000).toFixed(1)}K`;
  return `${prefix}$${abs.toFixed(0)}`;
}
