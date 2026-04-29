"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  CartesianGrid,
  LabelList,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { GitBranch } from "lucide-react";
import type { ImpactRunSummary } from "@/lib/types";

interface DistributionChartProps {
  summary: ImpactRunSummary;
}

const DECISION_ORDER = ["APPROVED", "FLAGGED", "REJECTED"] as const;

const DECISION_COLORS: Record<string, string> = {
  APPROVED: "#10b981",
  FLAGGED: "#f59e0b",
  REJECTED: "#ef4444",
};

interface TooltipPayloadEntry {
  name?: string;
  value?: number;
  color?: string;
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const baseEntry = payload.find((p) => p.name === "Baseline");
  const candEntry = payload.find((p) => p.name === "Candidate");
  const base = baseEntry?.value ?? 0;
  const cand = candEntry?.value ?? 0;
  const delta = cand - base;
  const decisionColor = label ? DECISION_COLORS[label] ?? "#64748b" : "#64748b";

  return (
    <div className="rounded-lg border border-border/60 bg-card p-3 text-xs shadow-lg ring-1 ring-black/5 backdrop-blur">
      <div className="mb-2 flex items-center gap-2 font-semibold">
        <span
          className="h-2 w-2 rounded-full"
          style={{ background: decisionColor }}
        />
        <span className="text-foreground">{label}</span>
      </div>
      <div className="space-y-1.5 text-muted-foreground">
        <div className="flex items-center justify-between gap-6">
          <span className="flex items-center gap-1.5">
            <span className="h-1.5 w-3 rounded-full bg-slate-400" />
            Baseline
          </span>
          <span className="font-mono font-medium text-foreground">
            {base.toLocaleString()}
          </span>
        </div>
        <div className="flex items-center justify-between gap-6">
          <span className="flex items-center gap-1.5">
            <span className="h-1.5 w-3 rounded-full bg-blue-400" />
            Candidate
          </span>
          <span className="font-mono font-medium text-foreground">
            {cand.toLocaleString()}
          </span>
        </div>
        <div className="mt-1 flex items-center justify-between gap-6 border-t border-border/40 pt-1.5">
          <span>Δ</span>
          <span
            className={
              "font-mono font-semibold " +
              (delta > 0
                ? "text-red-600 dark:text-red-400"
                : delta < 0
                  ? "text-emerald-600 dark:text-emerald-400"
                  : "text-muted-foreground")
            }
          >
            {delta > 0 ? "+" : ""}
            {delta.toLocaleString()}
          </span>
        </div>
      </div>
    </div>
  );
}

function CustomLegend() {
  return (
    <div className="mt-2 flex justify-center gap-5 text-xs text-muted-foreground">
      <span className="inline-flex items-center gap-1.5">
        <span className="h-2.5 w-2.5 rounded-sm bg-slate-400" />
        Baseline
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="h-2.5 w-2.5 rounded-sm bg-blue-400" />
        Candidate
      </span>
    </div>
  );
}

export function DistributionChart({ summary }: DistributionChartProps) {
  const base = summary.decision_distribution.base ?? {};
  const cand = summary.decision_distribution.candidate ?? {};

  const data = DECISION_ORDER.map((d) => ({
    name: d,
    Baseline: base[d] ?? 0,
    Candidate: cand[d] ?? 0,
  }));

  const totalLoans = summary.total_loans ?? data.reduce((a, d) => a + d.Baseline, 0);

  return (
    <Card className="card-elevated overflow-hidden border-border/50">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base">
            <span className="rounded-md bg-blue-500/10 p-1.5 ring-1 ring-inset ring-blue-500/20">
              <GitBranch className="size-4 text-blue-600 dark:text-blue-400" />
            </span>
            Decision Distribution
          </CardTitle>
          <Badge variant="outline" className="text-[11px]">
            {totalLoans.toLocaleString()} loans
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="h-[280px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={data}
              margin={{ top: 24, right: 24, left: 0, bottom: 0 }}
              barCategoryGap="28%"
            >
              <defs>
                <linearGradient id="barBaseline" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#cbd5e1" stopOpacity={1} />
                  <stop offset="100%" stopColor="#94a3b8" stopOpacity={1} />
                </linearGradient>
                <linearGradient id="barCandidate" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#60a5fa" stopOpacity={1} />
                  <stop offset="100%" stopColor="#2563eb" stopOpacity={1} />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="2 4"
                stroke="rgba(100,116,139,0.12)"
                vertical={false}
              />
              <XAxis
                dataKey="name"
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 11, fill: "rgb(100,116,139)" }}
              />
              <YAxis
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 11, fill: "rgb(100,116,139)" }}
                tickFormatter={(v) =>
                  v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v)
                }
              />
              <Tooltip
                cursor={{ fill: "rgba(100,116,139,0.06)" }}
                content={<CustomTooltip />}
              />
              <Legend content={<CustomLegend />} />
              <Bar
                dataKey="Baseline"
                fill="url(#barBaseline)"
                radius={[6, 6, 0, 0]}
                isAnimationActive={false}
                maxBarSize={56}
              >
                <LabelList
                  dataKey="Baseline"
                  position="top"
                  fontSize={11}
                  fill="rgb(100,116,139)"
                  formatter={(v) => Number(v ?? 0).toLocaleString()}
                />
              </Bar>
              <Bar
                dataKey="Candidate"
                fill="url(#barCandidate)"
                radius={[6, 6, 0, 0]}
                isAnimationActive={false}
                maxBarSize={56}
              >
                <LabelList
                  dataKey="Candidate"
                  position="top"
                  fontSize={11}
                  fill="rgb(37,99,235)"
                  formatter={(v) => Number(v ?? 0).toLocaleString()}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <p className="mt-1 px-1 text-[11px] leading-relaxed text-muted-foreground">
          <span className="font-medium text-foreground">Decision precedence:</span>{" "}
          REJECT terminates · FLAG (any rule) supersedes APPROVED · APPROVED only when no rule fires.
          A loan can be FLAGGED for manual review without being rejected.
        </p>
      </CardContent>
    </Card>
  );
}
