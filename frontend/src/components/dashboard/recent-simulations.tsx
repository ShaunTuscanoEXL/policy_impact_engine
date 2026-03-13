"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ArrowRight, Loader2 } from "lucide-react";
import type { Simulation } from "@/lib/types";

interface RecentSimulationsProps {
  simulations: Simulation[];
  loading: boolean;
}

const statusVariants: Record<
  Simulation["status"],
  { label: string; className: string }
> = {
  COMPLETED: {
    label: "Completed",
    className:
      "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  },
  RUNNING: {
    label: "Running",
    className:
      "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
  },
  PENDING: {
    label: "Pending",
    className:
      "bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400",
  },
  FAILED: {
    label: "Failed",
    className:
      "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
  },
};

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function RecentSimulations({
  simulations,
  loading,
}: RecentSimulationsProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent Simulations</CardTitle>
        <CardDescription>
          Latest simulation runs and their status
        </CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : simulations.length === 0 ? (
          <div className="py-8 text-center text-muted-foreground">
            No simulations found. Run your first simulation to see results here.
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Scenario Name</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Dataset</TableHead>
                <TableHead>Created At</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {simulations.map((sim) => {
                const statusInfo = statusVariants[sim.status];
                return (
                  <TableRow key={sim.id}>
                    <TableCell className="font-medium">
                      {sim.scenario_name}
                    </TableCell>
                    <TableCell>
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${statusInfo.className}`}
                      >
                        {statusInfo.label}
                      </span>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {sim.dataset_id.slice(0, 8)}...
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDate(sim.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Link
                        href={`/simulations/${sim.id}`}
                        className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
                      >
                        View
                        <ArrowRight className="h-3 w-3" />
                      </Link>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
