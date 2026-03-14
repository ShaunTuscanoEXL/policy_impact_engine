"use client";

import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import type { Simulation } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Activity } from "lucide-react";

interface RecentSimulationsProps {
  simulations: Simulation[];
  loading: boolean;
}

const statusColors: Record<string, string> = {
  COMPLETED: "bg-emerald-500",
  RUNNING: "bg-blue-500",
  PENDING: "bg-neutral-400",
  FAILED: "bg-red-500",
  AWAITING_REVIEW: "bg-amber-500",
};

export function RecentSimulations({ simulations, loading }: RecentSimulationsProps) {
  return (
    <Card className="card-elevated border-border/40">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <Activity className="size-4 text-violet-500" />
          Recent Simulations
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {loading ? (
          <div className="space-y-3 p-6">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-4 animate-pulse rounded-lg bg-muted" />
            ))}
          </div>
        ) : simulations.length === 0 ? (
          <p className="p-6 text-center text-sm text-muted-foreground">No simulations yet</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-violet-500/20">Name</TableHead>
                <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-violet-500/20">Status</TableHead>
                <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-violet-500/20">Date</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {simulations.slice(0, 5).map((sim) => (
                <TableRow key={sim.id} className="group cursor-pointer transition-colors duration-150 hover:bg-accent/50">
                  <TableCell>
                    <Link href={`/simulations/${sim.id}`} className="text-sm font-medium hover:text-primary transition-colors">
                      {sim.scenario_name || "Unnamed"}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <span className="flex items-center gap-2">
                      <span className={cn("h-1.5 w-1.5 rounded-full", statusColors[sim.status] ?? "bg-neutral-400")} />
                      <span className="text-xs text-muted-foreground">
                        {sim.status.charAt(0) + sim.status.slice(1).toLowerCase().replace(/_/g, " ")}
                      </span>
                    </span>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground tabular-nums">
                    {new Date(sim.created_at).toLocaleDateString()}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
