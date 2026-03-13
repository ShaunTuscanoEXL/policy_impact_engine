"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import api from "@/lib/api";
import type { Simulation } from "@/lib/types";
import { toast } from "sonner";
import { PageTransition } from "@/components/page-transition";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
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
import { Plus, Eye, Trash2, Loader2, PlayCircle, ClipboardCheck } from "lucide-react";

const statusColors: Record<string, string> = {
  COMPLETED: "bg-emerald-500",
  RUNNING: "bg-blue-500",
  PENDING: "bg-neutral-400",
  FAILED: "bg-red-500",
  AWAITING_REVIEW: "bg-amber-500",
};

const statusLabels: Record<string, string> = {
  COMPLETED: "Completed",
  RUNNING: "Running",
  PENDING: "Pending",
  FAILED: "Failed",
  AWAITING_REVIEW: "Awaiting Review",
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
    <PageTransition>
      <div className="space-y-8">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-muted-foreground mb-4">Dashboard / Simulations</p>
            <h1 className="text-2xl font-semibold tracking-tight">Simulations</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Run and review policy impact simulations.
            </p>
          </div>
          <Button render={<Link href="/simulations/new" />}>
            <Plus className="size-4" />
            New Simulation
          </Button>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.1 }}
        >
          <Card className="border-border/50 shadow-sm">
            {loading ? (
              <div className="flex items-center justify-center py-16">
                <Loader2 className="size-6 animate-spin text-muted-foreground" />
              </div>
            ) : simulations.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <PlayCircle className="size-10 text-muted-foreground/30" />
                <p className="mt-3 text-sm text-muted-foreground">
                  No simulations yet. Run one to get started.
                </p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs uppercase tracking-wider text-muted-foreground">Scenario Name</TableHead>
                    <TableHead className="text-xs uppercase tracking-wider text-muted-foreground">Status</TableHead>
                    <TableHead className="text-xs uppercase tracking-wider text-muted-foreground">Rule Set</TableHead>
                    <TableHead className="text-xs uppercase tracking-wider text-muted-foreground">Dataset</TableHead>
                    <TableHead className="text-xs uppercase tracking-wider text-muted-foreground">Created At</TableHead>
                    <TableHead className="text-xs uppercase tracking-wider text-muted-foreground text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {simulations.map((sim) => (
                    <TableRow key={sim.id} className="group hover:bg-accent/50">
                      <TableCell className="font-medium">
                        {sim.scenario_name}
                      </TableCell>
                      <TableCell>
                        <span className="flex items-center gap-2">
                          <span className={cn("h-2 w-2 rounded-full", statusColors[sim.status] || "bg-neutral-400")} />
                          <span className="text-xs text-muted-foreground">{statusLabels[sim.status] || sim.status}</span>
                        </span>
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
                        <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          {sim.status === "COMPLETED" && (
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              render={<Link href={`/simulations/${sim.id}`} />}
                            >
                              <Eye className="size-4" />
                            </Button>
                          )}
                          {sim.status === "AWAITING_REVIEW" && (
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              render={<Link href={`/rules/${sim.rule_set_id}?simulationId=${sim.id}`} />}
                            >
                              <ClipboardCheck className="size-4" />
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
                  ))}
                </TableBody>
              </Table>
            )}
          </Card>
        </motion.div>
      </div>
    </PageTransition>
  );
}
