"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import api from "@/lib/api";
import type {
  ImpactRun,
  LiveRepository,
  LiveVersionSummary,
} from "@/lib/types";
import { toast } from "sonner";
import { PageTransition } from "@/components/page-transition";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
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
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import {
  Activity,
  Loader2,
  Eye,
  Sparkles,
  Play,
  Clock,
  CheckCircle,
  XCircle,
} from "lucide-react";

const STATUS_STYLES: Record<string, string> = {
  PENDING: "bg-amber-500/10 text-amber-600 border-amber-500/20 dark:text-amber-400",
  RUNNING: "bg-blue-500/10 text-blue-600 border-blue-500/20 dark:text-blue-400",
  COMPLETED: "bg-emerald-500/10 text-emerald-600 border-emerald-500/20 dark:text-emerald-400",
  FAILED: "bg-red-500/10 text-red-600 border-red-500/20 dark:text-red-400",
};

const NO_BASE_VALUE = "__NONE__";
// Sentinel "nothing picked yet" values so the Selects stay controlled
// throughout their lifetime. Base UI errors loudly when a Select switches
// between undefined (uncontrolled) and a string (controlled).
const UNSET_REPO = "__unset_repo__";
const UNSET_CANDIDATE = "__unset_candidate__";

function formatDate(s: string): string {
  return new Date(s).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function StatusIcon({ status }: { status: string }) {
  if (status === "COMPLETED")
    return <CheckCircle className="size-3.5 text-emerald-500" />;
  if (status === "FAILED")
    return <XCircle className="size-3.5 text-red-500" />;
  if (status === "RUNNING")
    return <Loader2 className="size-3.5 animate-spin text-blue-500" />;
  return <Clock className="size-3.5 text-amber-500" />;
}

export default function ImpactRunsPage() {
  const [runs, setRuns] = useState<ImpactRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [repos, setRepos] = useState<LiveRepository[]>([]);
  const [versionsByRepo, setVersionsByRepo] = useState<
    Record<string, LiveVersionSummary[]>
  >({});

  // Create dialog state
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [selectedRepoId, setSelectedRepoId] = useState<string>(UNSET_REPO);
  const [baseVersionId, setBaseVersionId] = useState<string>(NO_BASE_VALUE);
  const [candidateVersionId, setCandidateVersionId] = useState<string>(UNSET_CANDIDATE);
  const [createdBy, setCreatedBy] = useState("");
  const [versionsLoading, setVersionsLoading] = useState(false);

  // Sheet state
  const [openRunId, setOpenRunId] = useState<string | null>(null);

  const fetchRuns = useCallback(async () => {
    try {
      const { data } = await api.get<ImpactRun[]>("/impact-run");
      setRuns(data);
    } catch {
      toast.error("Failed to load impact runs.");
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchRepos = useCallback(async () => {
    try {
      const { data } = await api.get<LiveRepository[]>("/live-repo");
      setRepos(data);
    } catch {
      // non-fatal here
    }
  }, []);

  useEffect(() => {
    fetchRuns();
    fetchRepos();
  }, [fetchRuns, fetchRepos]);

  const loadVersionsFor = useCallback(
    async (repoId: string) => {
      if (versionsByRepo[repoId]) return;
      setVersionsLoading(true);
      try {
        const { data } = await api.get<LiveVersionSummary[]>(
          `/live-repo/${repoId}/versions`
        );
        setVersionsByRepo((prev) => ({ ...prev, [repoId]: data }));
      } catch {
        toast.error("Failed to load versions for this repository.");
      } finally {
        setVersionsLoading(false);
      }
    },
    [versionsByRepo]
  );

  const handleRepoChange = useCallback(
    (val: string | null) => {
      const repoId = val && val !== UNSET_REPO ? val : UNSET_REPO;
      setSelectedRepoId(repoId);
      setBaseVersionId(NO_BASE_VALUE);
      setCandidateVersionId(UNSET_CANDIDATE);
      if (repoId !== UNSET_REPO) loadVersionsFor(repoId);
    },
    [loadVersionsFor]
  );

  const repoVersions = useMemo(
    () =>
      selectedRepoId !== UNSET_REPO
        ? versionsByRepo[selectedRepoId] || []
        : [],
    [selectedRepoId, versionsByRepo]
  );

  const resetForm = () => {
    setSelectedRepoId(UNSET_REPO);
    setBaseVersionId(NO_BASE_VALUE);
    setCandidateVersionId(UNSET_CANDIDATE);
    setCreatedBy("");
  };

  const handleCreate = useCallback(async () => {
    if (selectedRepoId === UNSET_REPO) {
      toast.error("Select a repository.");
      return;
    }
    if (candidateVersionId === UNSET_CANDIDATE) {
      toast.error("Select a candidate version.");
      return;
    }
    setCreating(true);
    try {
      const payload: Record<string, any> = {
        repository_id: selectedRepoId,
        candidate_version_id: candidateVersionId,
      };
      if (baseVersionId !== NO_BASE_VALUE) {
        payload.base_version_id = baseVersionId;
      }
      if (createdBy.trim()) payload.created_by = createdBy.trim();

      await api.post("/impact-run", payload);
      toast.success("Impact run started.");
      setCreateOpen(false);
      resetForm();
      fetchRuns();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to start impact run.");
    } finally {
      setCreating(false);
    }
  }, [
    selectedRepoId,
    candidateVersionId,
    baseVersionId,
    createdBy,
    fetchRuns,
  ]);

  const openRun = useMemo(
    () => runs.find((r) => r.id === openRunId) || null,
    [runs, openRunId]
  );

  // For the open run, ensure we have the repo's versions so we can map IDs → numbers.
  useEffect(() => {
    if (openRun) loadVersionsFor(openRun.repository_id);
  }, [openRun, loadVersionsFor]);

  const versionNumberFor = useCallback(
    (repoId: string, versionId: string | null): string => {
      if (!versionId) return "—";
      const list = versionsByRepo[repoId];
      if (!list) return versionId.slice(0, 8);
      const v = list.find((x) => x.id === versionId);
      return v ? `v${v.version_number}` : versionId.slice(0, 8);
    },
    [versionsByRepo]
  );

  const repoLabelFor = useCallback(
    (repoId: string) => {
      const r = repos.find((x) => x.id === repoId);
      if (!r) return repoId.slice(0, 8);
      const tags = [r.product, r.jurisdiction].filter(Boolean).join(" · ");
      return tags ? `${r.name} (${tags})` : r.name;
    },
    [repos]
  );

  // Eagerly load repo versions for all runs, so the table shows version numbers.
  useEffect(() => {
    const uniqueRepos = Array.from(new Set(runs.map((r) => r.repository_id)));
    uniqueRepos.forEach((rid) => {
      if (!versionsByRepo[rid]) loadVersionsFor(rid);
    });
  }, [runs, versionsByRepo, loadVersionsFor]);

  return (
    <PageTransition>
      <div className="space-y-8">
        <div>
          <p className="text-xs text-muted-foreground mb-4">
            Dashboard / Impact Runs
          </p>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="icon-badge bg-rose-100 dark:bg-rose-900/30">
                <Activity className="size-5 text-rose-600 dark:text-rose-400" />
              </div>
              <div>
                <h1 className="text-2xl font-bold tracking-tight">
                  <span className="text-gradient">Impact Runs</span>
                </h1>
                <p className="text-sm text-muted-foreground">
                  Compare two repository versions against the loan-record
                  population to see decision flips.
                </p>
              </div>
            </div>

            <Dialog open={createOpen} onOpenChange={setCreateOpen}>
              <DialogTrigger render={<Button variant="default" />}>
                <Sparkles className="size-4" />
                New Impact Run
              </DialogTrigger>
              <DialogContent className="sm:max-w-md">
                <DialogHeader>
                  <DialogTitle>Start New Impact Run</DialogTitle>
                  <DialogDescription>
                    Pick a repository and the two versions to compare. Leave
                    base empty to compare candidate against an empty baseline.
                  </DialogDescription>
                </DialogHeader>

                <div className="space-y-3 py-2">
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium">Repository</label>
                    <Select
                      value={selectedRepoId}
                      onValueChange={handleRepoChange}
                    >
                      <SelectTrigger className="w-full">
                        {/* Bypass SelectValue entirely when unset — Base UI
                            otherwise falls back to rendering the raw sentinel
                            value as text. */}
                        <span
                          className={
                            selectedRepoId === UNSET_REPO
                              ? "text-muted-foreground"
                              : ""
                          }
                        >
                          {selectedRepoId === UNSET_REPO
                            ? "Select repository…"
                            : repoLabelFor(selectedRepoId)}
                        </span>
                      </SelectTrigger>
                      <SelectContent>
                        {repos.length === 0 ? (
                          <SelectItem value="__empty__" disabled>
                            No repositories available
                          </SelectItem>
                        ) : (
                          repos.map((r) => (
                            <SelectItem key={r.id} value={r.id}>
                              {r.name} ({r.product}/{r.jurisdiction})
                            </SelectItem>
                          ))
                        )}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium">
                        Base Version
                      </label>
                      <Select
                        value={baseVersionId}
                        onValueChange={(v) =>
                          setBaseVersionId(v || NO_BASE_VALUE)
                        }
                        disabled={selectedRepoId === UNSET_REPO || versionsLoading}
                      >
                        <SelectTrigger className="w-full">
                          <span>
                            {baseVersionId === NO_BASE_VALUE
                              ? "None (empty baseline)"
                              : versionNumberFor(selectedRepoId, baseVersionId)}
                          </span>
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value={NO_BASE_VALUE}>
                            None (empty baseline)
                          </SelectItem>
                          {repoVersions.map((v) => (
                            <SelectItem key={v.id} value={v.id}>
                              v{v.version_number}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-1.5">
                      <label className="text-xs font-medium">
                        Candidate Version
                      </label>
                      <Select
                        value={candidateVersionId}
                        onValueChange={(v) =>
                          setCandidateVersionId(v || UNSET_CANDIDATE)
                        }
                        disabled={selectedRepoId === UNSET_REPO || versionsLoading}
                      >
                        <SelectTrigger className="w-full">
                          <span
                            className={
                              candidateVersionId === UNSET_CANDIDATE
                                ? "text-muted-foreground"
                                : ""
                            }
                          >
                            {candidateVersionId === UNSET_CANDIDATE
                              ? "Pick…"
                              : versionNumberFor(selectedRepoId, candidateVersionId)}
                          </span>
                        </SelectTrigger>
                        <SelectContent>
                          {repoVersions.length === 0 ? (
                            <SelectItem value="__empty_cand__" disabled>
                              No versions available
                            </SelectItem>
                          ) : (
                            repoVersions.map((v) => (
                              <SelectItem key={v.id} value={v.id}>
                                v{v.version_number}
                              </SelectItem>
                            ))
                          )}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-medium">
                      Created By{" "}
                      <span className="text-muted-foreground">(optional)</span>
                    </label>
                    <Input
                      value={createdBy}
                      onChange={(e) => setCreatedBy(e.target.value)}
                      placeholder="e.g., jane.doe@example.com"
                    />
                  </div>
                </div>

                <DialogFooter>
                  <DialogClose render={<Button variant="outline" />}>
                    Cancel
                  </DialogClose>
                  <Button
                    variant="default"
                    onClick={handleCreate}
                    disabled={creating}
                  >
                    {creating && (
                      <Loader2 className="mr-2 size-4 animate-spin" />
                    )}
                    <Play className="size-4" />
                    Run
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.1 }}
        >
          <Card className="card-elevated border-border/40">
            {loading ? (
              <div className="flex items-center justify-center py-16">
                <Loader2 className="size-6 animate-spin text-muted-foreground" />
              </div>
            ) : runs.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <Activity className="size-12 text-muted-foreground/20" />
                <p className="mt-3 text-sm text-muted-foreground">
                  No impact runs yet. Start one above.
                </p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-rose-500/20">
                      Created
                    </TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-rose-500/20">
                      Repository
                    </TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-rose-500/20">
                      Base
                    </TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-rose-500/20">
                      Candidate
                    </TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-rose-500/20">
                      Status
                    </TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-rose-500/20">
                      Loans
                    </TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-rose-500/20 text-right">
                      Actions
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {runs.map((run) => (
                    <TableRow
                      key={run.id}
                      className="group transition-colors duration-150 hover:bg-accent/50"
                    >
                      <TableCell className="text-muted-foreground text-sm">
                        {formatDate(run.created_at)}
                      </TableCell>
                      <TableCell>
                        <Link
                          href={`/live-repo/${run.repository_id}`}
                          className="text-sm hover:text-primary hover:underline"
                          title={run.repository_id}
                        >
                          {repoLabelFor(run.repository_id)}
                        </Link>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">
                          {versionNumberFor(
                            run.repository_id,
                            run.base_version_id
                          )}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary">
                          {versionNumberFor(
                            run.repository_id,
                            run.candidate_version_id
                          )}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={STATUS_STYLES[run.status] || ""}
                        >
                          <StatusIcon status={run.status} />
                          {run.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground text-sm">
                        {run.summary?.total_loans ?? "—"}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="default"
                          size="sm"
                          title="View detailed impact analysis"
                          render={<Link href={`/impact-runs/${run.id}`} />}
                          disabled={!run.summary && run.status !== "FAILED"}
                        >
                          <Eye className="size-3.5" />
                          Analyze
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </Card>
        </motion.div>

        {/* Detailed analysis lives at /impact-runs/[runId] (replaces the inline Sheet) */}

      </div>
    </PageTransition>
  );
}
