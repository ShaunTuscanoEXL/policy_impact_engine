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
import { Separator } from "@/components/ui/separator";
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
      <div className="space-y-6">
        <p className="text-xs text-muted-foreground mb-4">
          Dashboard /{" "}
          <Link href="/impact-runs" className="hover:underline">
            Impact Runs
          </Link>{" "}
          / {baseLabel} → {candLabel}
        </p>

        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-4">
            <Link href="/impact-runs">
              <Button variant="ghost" size="icon-sm">
                <ArrowLeft className="size-4" />
              </Button>
            </Link>
            <div className="space-y-2">
              <div className="flex items-center gap-3">
                <div className="icon-badge bg-rose-100 dark:bg-rose-900/30">
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
                  {run.status}
                </Badge>
              </div>

              <div className="ml-9 flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
                {repo && (
                  <Link
                    href={`/live-repo/${repo.id}`}
                    className="inline-flex items-center gap-1.5 hover:text-primary hover:underline"
                  >
                    <GitBranch className="size-4" />
                    {repo.name}
                    {repo.product && repo.jurisdiction && (
                      <span className="text-xs">
                        ({repo.product} · {repo.jurisdiction})
                      </span>
                    )}
                  </Link>
                )}
                <span>
                  Base{" "}
                  <Badge variant="outline" className="ml-1">
                    {baseLabel}
                  </Badge>
                </span>
                <span>
                  Candidate{" "}
                  <Badge variant="secondary" className="ml-1">
                    {candLabel}
                  </Badge>
                </span>
                {run.created_by && (
                  <span>
                    by{" "}
                    <span className="font-medium text-foreground">
                      {run.created_by}
                    </span>
                  </span>
                )}
                <span>{formatDate(run.created_at)}</span>
              </div>
            </div>
          </div>
        </div>

        <Separator />

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
