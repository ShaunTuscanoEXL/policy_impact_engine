"use client";

import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import type { Simulation } from "@/lib/types";
import { cn } from "@/lib/utils";

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
    <Card className="border-border/50 shadow-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">Recent Simulations</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {loading ? (
          <div className="space-y-3 p-6">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-4 animate-pulse rounded bg-muted" />
            ))}
          </div>
        ) : simulations.length === 0 ? (
          <p className="p-6 text-center text-sm text-muted-foreground">No simulations yet</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-xs uppercase tracking-wider text-muted-foreground">Name</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-muted-foreground">Status</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-muted-foreground">Date</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {simulations.slice(0, 5).map((sim) => (
                <TableRow key={sim.id} className="group cursor-pointer hover:bg-accent/50">
                  <TableCell>
                    <Link href={`/simulations/${sim.id}`} className="text-sm hover:underline">
                      {sim.scenario_name || "Unnamed"}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <span className="flex items-center gap-2">
                      <span className={cn("h-2 w-2 rounded-full", statusColors[sim.status] ?? "bg-neutral-400")} />
                      <span className="text-xs text-muted-foreground">
                        {sim.status.charAt(0) + sim.status.slice(1).toLowerCase().replace(/_/g, " ")}
                      </span>
                    </span>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
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
