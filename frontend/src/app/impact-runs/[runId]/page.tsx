"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
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
import {
  Activity,
  ArrowLeft,
  Clock,
  Loader2,
  AlertCircle,
  CheckCircle,
  XCircle,
  GitBranch,
} from "lucide-react";

import { SummaryCards } from "@/components/impact/summary-cards";
import { DistributionChart } from "@/components/impact/distribution-chart";
import { FlipsChart } from "@/components/impact/flips-chart";
import { SubsystemAttribution } from "@/components/impact/subsystem-attribution";
import { SegmentTable } from "@/components/impact/segment-table";

const STATUS_STYLES: Record<string, string> = {
  PENDING:
    "bg-amber-500/10 text-amber-600 border-amber-500/20 dark:text-amber-400",
  RUNNING:
    "bg-blue-500/10 text-blue-600 border-blue-500/20 dark:text-blue-400",
  COMPLETED:
    "bg-emerald-500/10 text-emerald-600 border-emerald-500/20 dark:text-emerald-400",
  FAILED:
    "bg-red-500/10 text-red-600 border-red-500/20 dark:text-red-400",
};

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "COMPLETED":
      return <CheckCircle className="size-3.5" />;
    case "FAILED":
      return <XCircle className="size-3.5" />;
    case "RUNNING":
      return <Loader2 className="size-3.5 animate-spin" />;
    default:
      return <Clock className="size-3.5" />;
  }
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function ImpactRunDetailPage() {
  const params = useParams<{ runId: string }>();
  const runId = params.runId;

  const [run, setRun] = useState<ImpactRun | null>(null);
  const [repo, setRepo] = useState<LiveRepository | null>(null);
  const [versions, setVersions] = useState<LiveVersionSummary[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    try {
      const { data } = await api.get<ImpactRun>(`/impact-run/${runId}`);
      setRun(data);

      // Resolve repo + versions for friendly labels
      const [repoResp, versionsResp] = await Promise.all([
        api.get<LiveRepository>(`/live-repo/${data.repository_id}`).catch(() => null),
        api
          .get<LiveVersionSummary[]>(`/live-repo/${data.repository_id}/versions`)
          .catch(() => null),
      ]);
      if (repoResp) setRepo(repoResp.data);
      if (versionsResp) setVersions(versionsResp.data);
    } catch {
      toast.error("Failed to load impact run.");
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const versionLabel = (id: string | null) => {
    if (!id) return "empty baseline";
    const v = versions.find((x) => x.id === id);
    return v ? `v${v.version_number}` : id.slice(0, 8);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!run) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-20">
        <AlertCircle className="size-10 text-destructive" />
        <p className="text-lg text-muted-foreground">Impact run not found.</p>
        <Link href="/impact-runs">
          <Button variant="outline">
            <ArrowLeft className="mr-2 size-4" />
            Back to Impact Runs
          </Button>
        </Link>
      </div>
    );
  }

  const summary = run.summary;
  const baseLabel = versionLabel(run.base_version_id);
  const candLabel = versionLabel(run.candidate_version_id);

  return (
    <PageTransition>
      <div className="space-y-8">
        <p className="text-xs text-muted-foreground">
          Dashboard /{" "}
          <Link href="/impact-runs" className="hover:underline">
            Impact Runs
          </Link>{" "}
          / {baseLabel} → {candLabel}
        </p>

        {/* Header card with gradient + version comparison hero */}
        <Card className="card-elevated relative overflow-hidden border-border/50 p-6">
          <div
            className="pointer-events-none absolute -right-20 -top-20 h-56 w-56 rounded-full bg-gradient-to-br from-rose-500/15 via-violet-500/10 to-transparent blur-3xl"
            aria-hidden
          />
          <div
            className="pointer-events-none absolute -left-16 -bottom-16 h-40 w-40 rounded-full bg-gradient-to-br from-blue-500/15 via-emerald-500/5 to-transparent blur-3xl"
            aria-hidden
          />
          <div className="relative flex flex-wrap items-start justify-between gap-6">
            <div className="flex items-start gap-4">
              <Link href="/impact-runs">
                <Button variant="ghost" size="icon-sm" className="mt-1">
                  <ArrowLeft className="size-4" />
                </Button>
              </Link>
              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-3">
                  <div className="icon-badge bg-rose-500/15 ring-1 ring-inset ring-rose-500/20">
                    <Activity className="size-5 text-rose-600 dark:text-rose-400" />
                  </div>
                  <h1 className="text-2xl font-bold tracking-tight">
                    <span className="text-gradient">Impact Run</span>
                  </h1>
                  <Badge
                    variant="outline"
                    className={STATUS_STYLES[run.status] || ""}
                  >
                    <StatusIcon status={run.status} />
                    <span className="ml-1">{run.status}</span>
                  </Badge>
                </div>

                {repo && (
                  <div>
                    <Link
                      href={`/live-repo/${repo.id}`}
                      className="inline-flex items-center gap-1.5 text-sm hover:text-primary hover:underline"
                      title={repo.id}
                    >
                      <GitBranch className="size-4 text-amber-500" />
                      <span className="font-medium">{repo.name}</span>
                      {repo.product && repo.jurisdiction && (
                        <span className="text-xs text-muted-foreground">
                          · {repo.product} · {repo.jurisdiction}
                        </span>
                      )}
                    </Link>
                  </div>
                )}

                {/* Version comparison hero — own row so it can't collide
                    with the repo Link beside it */}
                <div className="flex w-fit items-center gap-3 rounded-lg border border-border/40 bg-card/60 p-2 shadow-sm">
                  <span className="rounded-md bg-slate-500/10 px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-slate-700 ring-1 ring-inset ring-slate-500/20 dark:text-slate-300">
                    Base {baseLabel}
                  </span>
                  <span className="text-muted-foreground/70">→</span>
                  <span className="rounded-md bg-blue-500/10 px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-blue-700 ring-1 ring-inset ring-blue-500/20 dark:text-blue-300">
                    Candidate {candLabel}
                  </span>
                </div>

                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                  {run.created_by && (
                    <span>
                      by{" "}
                      <span className="font-medium text-foreground">
                        {run.created_by}
                      </span>
                    </span>
                  )}
                  <span>·</span>
                  <span>{formatDate(run.created_at)}</span>
                  {run.completed_at && (
                    <>
                      <span>·</span>
                      <span>completed {formatDate(run.completed_at)}</span>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>
        </Card>

        {run.status === "FAILED" && (
          <Card className="card-elevated border-red-500/40 bg-red-500/5 p-6">
            <div className="flex items-start gap-3">
              <AlertCircle className="size-5 text-red-600" />
              <div>
                <p className="font-medium text-red-600">Run failed</p>
                {run.error && (
                  <pre className="mt-2 whitespace-pre-wrap text-xs text-muted-foreground">
                    {run.error}
                  </pre>
                )}
              </div>
            </div>
          </Card>
        )}

        {run.status === "COMPLETED" && summary && (
          <>
            {/* Hero summary cards */}
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 }}
            >
              <SummaryCards summary={summary} />
            </motion.div>

            {/* Two-column charts row */}
            <motion.div
              className="grid gap-4 lg:grid-cols-2"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
            >
              <DistributionChart summary={summary} />
              <FlipsChart summary={summary} />
            </motion.div>

            {/* Subsystem attribution */}
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.15 }}
            >
              <SubsystemAttribution summary={summary} />
            </motion.div>

            {/* Segment table */}
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
            >
              <SegmentTable summary={summary} />
            </motion.div>
          </>
        )}

        {(run.status === "PENDING" || run.status === "RUNNING") && (
          <Card className="card-elevated border-border/40 p-12">
            <div className="flex flex-col items-center justify-center gap-3 text-center">
              <Loader2 className="size-8 animate-spin text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                {run.status === "PENDING"
                  ? "Run is queued. Refresh in a moment to see results."
                  : "Run is in progress…"}
              </p>
            </div>
          </Card>
        )}
      </div>
    </PageTransition>
  );
}
