"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import api from "@/lib/api";
import type { Simulation } from "@/lib/types";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogClose,
} from "@/components/ui/dialog";
import { Plus, Eye, Trash2, Loader2, PlayCircle } from "lucide-react";

const statusConfig: Record<
  Simulation["status"],
  { label: string; variant: "default" | "secondary" | "outline" | "destructive" }
> = {
  COMPLETED: { label: "Completed", variant: "default" },
  RUNNING: { label: "Running", variant: "secondary" },
  PENDING: { label: "Pending", variant: "outline" },
  FAILED: { label: "Failed", variant: "destructive" },
};

export default function SimulationsPage() {
  const [simulations, setSimulations] = useState<Simulation[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const fetchSimulations = useCallback(async () => {
    try {
      const { data } = await api.get("/simulations");
      setSimulations(data);
    } catch {
      toast.error("Failed to load simulations.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSimulations();
  }, [fetchSimulations]);

  const handleDelete = useCallback(async (id: string) => {
    setDeleting(true);
    try {
      await api.delete(`/simulations/${id}`);
      toast.success("Simulation deleted.");
      setSimulations((prev) => prev.filter((s) => s.id !== id));
    } catch {
      toast.error("Failed to delete simulation.");
    } finally {
      setDeleting(false);
      setDeleteId(null);
    }
  }, []);

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Simulations</h1>
          <p className="mt-2 text-muted-foreground">
            Run and review policy impact simulations.
          </p>
        </div>
        <Button render={<Link href="/simulations/new" />}>
          <Plus className="size-4" />
          New Simulation
        </Button>
      </div>

      <Card>
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="size-6 animate-spin text-muted-foreground" />
          </div>
        ) : simulations.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <PlayCircle className="size-10 text-muted-foreground/40" />
            <p className="mt-3 text-sm text-muted-foreground">
              No simulations yet. Run one to get started.
            </p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Scenario Name</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Rule Set</TableHead>
                <TableHead>Dataset</TableHead>
                <TableHead>Created At</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {simulations.map((sim) => {
                const config = statusConfig[sim.status];
                return (
                  <TableRow key={sim.id}>
                    <TableCell className="font-medium">
                      {sim.scenario_name}
                    </TableCell>
                    <TableCell>
                      <Badge variant={config.variant}>{config.label}</Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground font-mono text-xs">
                      {sim.rule_set_id.slice(0, 8)}...
                    </TableCell>
                    <TableCell className="text-muted-foreground font-mono text-xs">
                      {sim.dataset_id.slice(0, 8)}...
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {new Date(sim.created_at).toLocaleDateString("en-US", {
                        year: "numeric",
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        {sim.status === "COMPLETED" && (
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            render={<Link href={`/simulations/${sim.id}`} />}
                          >
                            <Eye className="size-4" />
                          </Button>
                        )}

                        <Dialog
                          open={deleteId === sim.id}
                          onOpenChange={(open) =>
                            setDeleteId(open ? sim.id : null)
                          }
                        >
                          <DialogTrigger
                            render={
                              <Button variant="ghost" size="icon-sm" />
                            }
                          >
                            <Trash2 className="size-4 text-destructive" />
                          </DialogTrigger>
                          <DialogContent>
                            <DialogHeader>
                              <DialogTitle>Delete Simulation</DialogTitle>
                              <DialogDescription>
                                Are you sure you want to delete &ldquo;
                                {sim.scenario_name}&rdquo;? This action cannot
                                be undone.
                              </DialogDescription>
                            </DialogHeader>
                            <DialogFooter>
                              <DialogClose
                                render={<Button variant="outline" />}
                              >
                                Cancel
                              </DialogClose>
                              <Button
                                variant="destructive"
                                disabled={deleting}
                                onClick={() => handleDelete(sim.id)}
                              >
                                {deleting && (
                                  <Loader2 className="mr-2 size-4 animate-spin" />
                                )}
                                Delete
                              </Button>
                            </DialogFooter>
                          </DialogContent>
                        </Dialog>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </Card>
    </div>
  );
}
