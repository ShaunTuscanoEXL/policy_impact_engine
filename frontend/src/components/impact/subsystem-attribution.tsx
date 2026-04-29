"use client";

import { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Layers } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ImpactRunSummary, Subsystem } from "@/lib/types";

interface SubsystemAttributionProps {
  summary: ImpactRunSummary;
}

const SUBSYSTEM_PALETTE: Record<string, { bg: string; text: string; bar: string }> = {
  REGULATORY_FLOOR: { bg: "bg-violet-500/10", text: "text-violet-700 dark:text-violet-300", bar: "bg-violet-500" },
  BUREAU_GATE: { bg: "bg-red-500/10", text: "text-red-700 dark:text-red-400", bar: "bg-red-500" },
  INCOME_GATE: { bg: "bg-orange-500/10", text: "text-orange-700 dark:text-orange-400", bar: "bg-orange-500" },
  DTI_GATE: { bg: "bg-amber-500/10", text: "text-amber-700 dark:text-amber-400", bar: "bg-amber-500" },
  EMPLOYMENT_GATE: { bg: "bg-lime-500/10", text: "text-lime-700 dark:text-lime-400", bar: "bg-lime-500" },
  BANKING_BEHAVIOR: { bg: "bg-emerald-500/10", text: "text-emerald-700 dark:text-emerald-400", bar: "bg-emerald-500" },
  FRAUD_SIGNAL: { bg: "bg-cyan-500/10", text: "text-cyan-700 dark:text-cyan-400", bar: "bg-cyan-500" },
  EXPOSURE_LIMIT: { bg: "bg-blue-500/10", text: "text-blue-700 dark:text-blue-400", bar: "bg-blue-500" },
  AMOUNT_CAP: { bg: "bg-indigo-500/10", text: "text-indigo-700 dark:text-indigo-400", bar: "bg-indigo-500" },
  PRICING_TIER: { bg: "bg-purple-500/10", text: "text-purple-700 dark:text-purple-400", bar: "bg-purple-500" },
  RATE_MODIFIER: { bg: "bg-fuchsia-500/10", text: "text-fuchsia-700 dark:text-fuchsia-400", bar: "bg-fuchsia-500" },
  SCORING_MODEL: { bg: "bg-pink-500/10", text: "text-pink-700 dark:text-pink-400", bar: "bg-pink-500" },
  UNCLASSIFIED: { bg: "bg-slate-500/10", text: "text-slate-700 dark:text-slate-300", bar: "bg-slate-500" },
};

function paletteFor(s: string) {
  return SUBSYSTEM_PALETTE[s] ?? SUBSYSTEM_PALETTE.UNCLASSIFIED;
}

function prettify(name: string) {
  return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function SubsystemAttribution({ summary }: SubsystemAttributionProps) {
  const items = useMemo(() => {
    const entries = Object.entries(summary.by_subsystem ?? {})
      .map(([name, info]) => ({
        name,
        flips: info.flips_caused,
      }))
      .sort((a, b) => b.flips - a.flips);
    const total = entries.reduce((a, e) => a + e.flips, 0);
    return entries.map((e) => ({
      ...e,
      pct: total > 0 ? (e.flips / total) * 100 : 0,
    }));
  }, [summary]);

  const total = items.reduce((a, i) => a + i.flips, 0);

  return (
    <Card className="card-elevated overflow-hidden border-border/50">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base">
            <span className="rounded-md bg-violet-500/10 p-1.5 ring-1 ring-inset ring-violet-500/20">
              <Layers className="size-4 text-violet-600 dark:text-violet-400" />
            </span>
            Flips Attributed by Subsystem
          </CardTitle>
          {items.length > 0 && (
            <Badge variant="outline" className="text-[11px]">
              {total.toLocaleString()} attributed flips
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="pt-2">
        {items.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 py-12 text-center">
            <div className="rounded-full bg-slate-500/10 p-3 ring-1 ring-inset ring-slate-500/20">
              <Layers className="size-5 text-slate-600 dark:text-slate-400" />
            </div>
            <p className="text-sm font-medium">No subsystem attribution</p>
            <p className="text-xs text-muted-foreground">
              No rule subsystem caused a decision change between these versions.
            </p>
          </div>
        ) : (
          <div className="space-y-2.5">
            {items.map((item) => {
              const p = paletteFor(item.name);
              return (
                <div key={item.name} className="group">
                  <div className="mb-1.5 flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <span
                        className={cn(
                          "inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-semibold ring-1 ring-inset",
                          p.bg,
                          p.text
                        )}
                      >
                        <span className={cn("size-1.5 rounded-full", p.bar)} />
                        {prettify(item.name)}
                      </span>
                    </div>
                    <div className="flex items-baseline gap-2">
                      <span className="font-mono text-sm font-semibold">
                        {item.flips.toLocaleString()}
                      </span>
                      <span className="font-mono text-[10px] text-muted-foreground">
                        {item.pct.toFixed(1)}%
                      </span>
                    </div>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-border/40">
                    <div
                      className={cn("h-full rounded-full transition-all duration-500", p.bar)}
                      style={{ width: `${Math.max(item.pct, 2)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
