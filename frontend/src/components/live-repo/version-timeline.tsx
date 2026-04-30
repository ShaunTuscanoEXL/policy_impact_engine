"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Eye,
  Download,
  Activity,
  GitCommit,
  FileText,
  User,
  Calendar,
  Loader2,
  ShieldCheck,
} from "lucide-react";
import { ProductionBadge } from "@/components/live-repo/production-badge";
import { PromoteToProductionButton } from "@/components/live-repo/promote-button";
import type { LiveVersionSummary, ImpactRun } from "@/lib/types";

interface VersionTimelineProps {
  repoId: string;
  repoName: string;
  versions: LiveVersionSummary[];
  productionVersionNumber: number | null;
  productionVersionId: string | null;
  onRefresh: () => void;
  onViewSnapshot: (versionNumber: number) => void;
  onDownload: (versionNumber: number) => void;
}

/**
 * Vertical timeline of every version in a repo, with a clear PRODUCTION
 * marker and per-row actions including the headline "Compare to current
 * production" one-click impact run that flips this version into a candidate
 * vs the live production version, navigating straight to the result.
 */
export function VersionTimeline({
  repoId,
  versions,
  productionVersionNumber,
  productionVersionId,
  onRefresh,
  onViewSnapshot,
  onDownload,
}: VersionTimelineProps) {
  const router = useRouter();
  const [comparingId, setComparingId] = useState<string | null>(null);

  // Reverse-chronological so newest versions are on top
  const ordered = [...versions]
    .filter((v) => v.version_number > 0)
    .sort((a, b) => b.version_number - a.version_number);

  const handleCompare = async (
    candidateVersionId: string,
    candidateVersionNumber: number,
  ) => {
    if (!productionVersionId) {
      toast.error("Cannot compare — no production version is set yet.");
      return;
    }
    if (candidateVersionId === productionVersionId) {
      toast.info("This version is already in production.");
      return;
    }
    setComparingId(candidateVersionId);
    try {
      const { data } = await api.post<ImpactRun>("/impact-run", {
        repository_id: repoId,
        base_version_id: productionVersionId,
        candidate_version_id: candidateVersionId,
        created_by: "version-timeline",
      });
      toast.success(
        `Comparing v${candidateVersionNumber} against production v${productionVersionNumber}…`,
      );
      router.push(`/impact-runs/${data.id}`);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to start impact run.");
    } finally {
      setComparingId(null);
    }
  };

  if (ordered.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <GitCommit className="size-12 text-muted-foreground/20" />
        <p className="mt-3 text-sm text-muted-foreground">
          No versions yet. Apply a merge proposal from a BRD to create version 1.
        </p>
      </div>
    );
  }

  return (
    <div className="relative pl-8">
      {/* Vertical rail */}
      <div className="absolute left-3 top-2 bottom-2 w-px bg-gradient-to-b from-amber-500/30 via-border to-transparent" />

      <ul className="space-y-6">
        {ordered.map((v, idx) => {
          const isProduction = v.version_number === productionVersionNumber;
          const isOlderThanProduction =
            productionVersionNumber != null &&
            v.version_number < productionVersionNumber;
          const isNewerThanProduction =
            productionVersionNumber != null &&
            v.version_number > productionVersionNumber;

          return (
            <li key={v.id} className="relative">
              {/* Timeline node */}
              <div
                className={`absolute -left-[22px] top-1.5 flex size-4 items-center justify-center rounded-full ring-4 ring-background ${
                  isProduction
                    ? "bg-emerald-500"
                    : isNewerThanProduction
                      ? "bg-blue-500"
                      : "bg-muted-foreground/40"
                }`}
              >
                <div className="size-1.5 rounded-full bg-white" />
              </div>

              <div
                className={`rounded-xl border p-4 transition-colors ${
                  isProduction
                    ? "border-emerald-500/30 bg-emerald-500/[0.03]"
                    : isNewerThanProduction
                      ? "border-blue-500/20 bg-blue-500/[0.02]"
                      : "border-border/50 bg-card/40"
                }`}
              >
                {/* Header row: version + badges */}
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <Badge
                    variant={isProduction ? "default" : "outline"}
                    className={
                      isProduction
                        ? "bg-emerald-600 text-white hover:bg-emerald-600"
                        : ""
                    }
                  >
                    v{v.version_number}
                  </Badge>
                  {isProduction && <ProductionBadge size="md" />}
                  {isNewerThanProduction && (
                    <Badge
                      variant="outline"
                      className="border-blue-500/30 bg-blue-500/10 text-blue-700 dark:text-blue-300"
                    >
                      CANDIDATE — newer than production
                    </Badge>
                  )}
                  {isOlderThanProduction && (
                    <Badge
                      variant="outline"
                      className="border-slate-400/30 bg-slate-400/10 text-slate-600 dark:text-slate-400"
                    >
                      historical
                    </Badge>
                  )}
                  <span className="ml-auto text-[10px] font-mono text-muted-foreground">
                    {v.rule_count} rule{v.rule_count === 1 ? "" : "s"}
                  </span>
                </div>

                {/* Summary */}
                <p className="mb-2 text-sm text-foreground">
                  {v.summary || (
                    <span className="italic text-muted-foreground">
                      No summary
                    </span>
                  )}
                </p>

                {/* Metadata row */}
                <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
                  <span className="inline-flex items-center gap-1">
                    <Calendar className="size-3" />
                    {new Date(v.created_at).toLocaleString("en-US", {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                  {v.created_by && (
                    <span className="inline-flex items-center gap-1">
                      <User className="size-3" />
                      {v.created_by}
                    </span>
                  )}
                  {v.source_brd_id && (
                    <Link
                      href={`/brds/${v.source_brd_id}`}
                      className="inline-flex items-center gap-1 text-primary hover:underline"
                    >
                      <FileText className="size-3" />
                      Source BRD
                    </Link>
                  )}
                </div>

                {/* Action row */}
                <div className="flex flex-wrap items-center gap-1.5">
                  {!isProduction && (
                    <Button
                      variant="default"
                      size="sm"
                      title="Open the validation pane (impact + suite tests + promote)"
                      render={
                        <Link
                          href={`/live-repo/${repoId}/validate/${v.version_number}`}
                        />
                      }
                    >
                      <ShieldCheck className="size-3.5" />
                      Validate
                    </Button>
                  )}
                  {!isProduction && productionVersionId && (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={comparingId === v.id}
                      onClick={() => handleCompare(v.id, v.version_number)}
                      title={`Compare v${v.version_number} against production v${productionVersionNumber}`}
                    >
                      {comparingId === v.id ? (
                        <Loader2 className="size-3.5 animate-spin" />
                      ) : (
                        <Activity className="size-3.5" />
                      )}
                      Compare to v{productionVersionNumber}
                    </Button>
                  )}
                  <PromoteToProductionButton
                    repoId={repoId}
                    versionNumber={v.version_number}
                    currentProductionVersionNumber={productionVersionNumber}
                    size="sm"
                    variant="outline"
                    onPromoted={onRefresh}
                  />
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onViewSnapshot(v.version_number)}
                  >
                    <Eye className="size-3.5" />
                    Snapshot
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onDownload(v.version_number)}
                  >
                    <Download className="size-3.5" />
                    .py
                  </Button>
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
