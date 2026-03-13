"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import api from "@/lib/api";
import type { Scenario, Simulation } from "@/lib/types";
import { toast } from "sonner";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
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
import { GitCompare, Plus, Trash2, Eye, Loader2 } from "lucide-react";

export default function ScenariosPage() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [simulations, setSimulations] = useState<Simulation[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Form state
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedSimIds, setSelectedSimIds] = useState<string[]>([]);

  const completedSimulations = simulations.filter(
    (s) => s.status === "COMPLETED"
  );

  const fetchData = useCallback(async () => {
    try {
      const [scenariosRes, simulationsRes] = await Promise.all([
        api.get("/scenarios"),
        api.get("/simulations"),
      ]);
      setScenarios(scenariosRes.data);
      setSimulations(simulationsRes.data);
    } catch {
      toast.error("Failed to load data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const toggleSimulation = (simId: string) => {
    setSelectedSimIds((prev) =>
      prev.includes(simId)
        ? prev.filter((id) => id !== simId)
        : prev.length < 3
          ? [...prev, simId]
          : prev
    );
  };

  const handleCreate = async () => {
    if (!name.trim()) {
      toast.error("Please enter a scenario name.");
      return;
    }
    if (selectedSimIds.length < 2) {
      toast.error("Please select at least 2 simulations to compare.");
      return;
    }
    setCreating(true);
    try {
      const { data } = await api.post("/scenarios", {
        name: name.trim(),
        description: description.trim() || null,
        simulation_ids: selectedSimIds,
      });
      toast.success("Scenario created.");
      setScenarios((prev) => [data, ...prev]);
      setName("");
      setDescription("");
      setSelectedSimIds([]);
    } catch {
      toast.error("Failed to create scenario.");
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = useCallback(async (id: string) => {
    setDeleting(true);
    try {
      await api.delete(`/scenarios/${id}`);
      toast.success("Scenario deleted.");
      setScenarios((prev) => prev.filter((s) => s.id !== id));
    } catch {
      toast.error("Failed to delete scenario.");
    } finally {
      setDeleting(false);
      setDeleteId(null);
    }
  }, []);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Scenarios</h1>
        <p className="mt-2 text-muted-foreground">
          Compare multiple simulation scenarios side by side.
        </p>
      </div>

      {/* Create Scenario Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Plus className="size-5" />
            Create Scenario
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium">Name</label>
              <Input
                placeholder="e.g. Conservative vs Aggressive"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Description</label>
              <textarea
                className="flex min-h-[60px] w-full rounded-lg border border-input bg-transparent px-2.5 py-1.5 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
                placeholder="Optional description..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
              />
            </div>
          </div>

          <Separator />

          <div className="space-y-2">
            <label className="text-sm font-medium">
              Select Simulations to Compare (2-3)
            </label>
            {completedSimulations.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No completed simulations available. Run simulations first.
              </p>
            ) : (
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {completedSimulations.map((sim) => {
                  const checked = selectedSimIds.includes(sim.id);
                  return (
                    <label
                      key={sim.id}
                      className={`flex cursor-pointer items-center gap-3 rounded-lg border p-3 transition-colors ${
                        checked
                          ? "border-primary bg-primary/5"
                          : "border-border hover:bg-muted/50"
                      } ${
                        !checked && selectedSimIds.length >= 3
                          ? "cursor-not-allowed opacity-50"
                          : ""
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleSimulation(sim.id)}
                        disabled={!checked && selectedSimIds.length >= 3}
                        className="size-4 rounded border-input accent-primary"
                      />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium">
                          {sim.scenario_name}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {new Date(sim.created_at).toLocaleDateString()}
                        </p>
                      </div>
                    </label>
                  );
                })}
              </div>
            )}
          </div>

          <div className="flex justify-end">
            <Button
              onClick={handleCreate}
              disabled={
                creating || !name.trim() || selectedSimIds.length < 2
              }
            >
              {creating && <Loader2 className="mr-2 size-4 animate-spin" />}
              <GitCompare className="size-4" />
              Create Scenario
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Scenario List */}
      <Card>
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="size-6 animate-spin text-muted-foreground" />
          </div>
        ) : scenarios.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <GitCompare className="size-10 text-muted-foreground/40" />
            <p className="mt-3 text-sm text-muted-foreground">
              No scenarios yet. Create one above to compare simulations.
            </p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead className="text-center"># Simulations</TableHead>
                <TableHead>Created At</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {scenarios.map((sc) => (
                <TableRow key={sc.id}>
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      <GitCompare className="size-4 text-muted-foreground" />
                      {sc.name}
                    </div>
                  </TableCell>
                  <TableCell className="text-center">
                    <Badge variant="secondary">
                      {sc.simulation_ids.length}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(sc.created_at).toLocaleDateString("en-US", {
                      year: "numeric",
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        render={<Link href={`/scenarios/${sc.id}`} />}
                      >
                        <Eye className="size-4" />
                      </Button>

                      <Dialog
                        open={deleteId === sc.id}
                        onOpenChange={(open) =>
                          setDeleteId(open ? sc.id : null)
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
                            <DialogTitle>Delete Scenario</DialogTitle>
                            <DialogDescription>
                              Are you sure you want to delete &ldquo;
                              {sc.name}&rdquo;? This action cannot be undone.
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
                              onClick={() => handleDelete(sc.id)}
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
    </div>
  );
}
