"use client";

/**
 * CoherencePanel — Slice 14. Surfaces the BRD coherence report in the
 * rule reviewer: does the graph of extracted rules actually connect the
 * way the document describes?
 *
 * Catches the class of problem where rules are individually correct but
 * wrong as a set — an eligibility/classification defined but never gated
 * on downstream, a rule conditioning on a field nothing produces, or a
 * dependency cycle. Fetched from /rule-sets/{id}/coherence.
 */
import { useCallback, useEffect, useState } from "react";
import api from "@/lib/api";
import type { CoherenceReport, CoherenceIssueKind } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  ShieldCheck,
  AlertTriangle,
  XCircle,
  Info,
  Loader2,
  GitFork,
  Link2Off,
  Unlink,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  ruleSetId: string;
  /** Bumps to force a refetch (e.g. after a rule edit). */
  refreshKey?: number;
}

const KIND_META: Record<
  CoherenceIssueKind,
  { label: string; Icon: typeof Info }
> = {
  unreferenced_eligibility: { label: "Unreferenced eligibility", Icon: Unlink },
  dead_consumer: { label: "Dead reference", Icon: Link2Off },
  orphan_producer: { label: "Orphan output", Icon: Info },
  dependency_cycle: { label: "Dependency cycle", Icon: GitFork },
};

const SEV_TONE: Record<string, { bg: string; text: string; ring: string; Icon: typeof Info }> = {
  error: {
    bg: "bg-rose-500/10",
    text: "text-rose-700 dark:text-rose-300",
    ring: "ring-rose-500/30",
    Icon: XCircle,
  },
  warning: {
    bg: "bg-amber-500/10",
    text: "text-amber-700 dark:text-amber-300",
    ring: "ring-amber-500/30",
    Icon: AlertTriangle,
  },
  info: {
    bg: "bg-blue-500/10",
    text: "text-blue-700 dark:text-blue-300",
    ring: "ring-blue-500/30",
    Icon: Info,
  },
};

export function CoherencePanel({ ruleSetId, refreshKey = 0 }: Props) {
  const [report, setReport] = useState<CoherenceReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchReport = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.get<CoherenceReport>(
        `/rule-sets/${ruleSetId}/coherence`,
      );
      setReport(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to load coherence report.");
    } finally {
      setLoading(false);
    }
  }, [ruleSetId]);

  useEffect(() => {
    fetchReport();
  }, [fetchReport, refreshKey]);

  if (loading) {
    return (
      <Card className="card-elevated border-border/50">
        <CardContent className="flex items-center gap-2 py-5 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          Analyzing rule dependencies…
        </CardContent>
      </Card>
    );
  }

  if (error || !report) {
    return null; // Non-blocking — coherence is advisory
  }

  const clean = report.issue_count === 0;
  const chainCount = report.dependency_edges.length;

  return (
    <Card
      className={cn(
        "card-elevated border-border/50",
        report.error_count > 0 && "border-rose-500/40",
      )}
    >
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <span
            className={cn(
              "rounded-md p-1.5 ring-1 ring-inset",
              clean
                ? "bg-emerald-500/10 ring-emerald-500/20"
                : report.error_count > 0
                  ? "bg-rose-500/10 ring-rose-500/20"
                  : "bg-amber-500/10 ring-amber-500/20",
            )}
          >
            {clean ? (
              <ShieldCheck className="size-4 text-emerald-600 dark:text-emerald-400" />
            ) : (
              <AlertTriangle
                className={cn(
                  "size-4",
                  report.error_count > 0
                    ? "text-rose-600 dark:text-rose-400"
                    : "text-amber-600 dark:text-amber-400",
                )}
              />
            )}
          </span>
          BRD Coherence
          {clean ? (
            <Badge
              variant="outline"
              className="bg-emerald-500/10 text-emerald-700 ring-1 ring-emerald-500/30 dark:text-emerald-300"
            >
              Rules connect correctly
            </Badge>
          ) : (
            <Badge
              variant="outline"
              className={cn(
                report.error_count > 0
                  ? "bg-rose-500/10 text-rose-700 ring-1 ring-rose-500/30 dark:text-rose-300"
                  : "bg-amber-500/10 text-amber-700 ring-1 ring-amber-500/30 dark:text-amber-300",
              )}
            >
              {report.error_count > 0 && `${report.error_count} error`}
              {report.error_count > 0 && report.warning_count > 0 && ", "}
              {report.warning_count > 0 && `${report.warning_count} to review`}
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted-foreground">
          Checks the rules as a whole — does each eligibility/classification
          defined in the BRD actually get used by the rules that should depend
          on it?{" "}
          {chainCount > 0 && (
            <span className="font-medium text-foreground">
              {chainCount} dependency link{chainCount !== 1 ? "s" : ""} detected.
            </span>
          )}
        </p>

        {clean ? (
          <div className="rounded-lg bg-emerald-500/5 p-3 text-sm text-emerald-700 ring-1 ring-inset ring-emerald-500/20 dark:text-emerald-300">
            No dead references, orphaned eligibility, or dependency cycles.
            Every produced field is consumed, and every consumed field is
            either a loan input or produced upstream.
          </div>
        ) : (
          <div className="space-y-2">
            {report.issues.map((issue, i) => {
              const sev = SEV_TONE[issue.severity] ?? SEV_TONE.info;
              const kind = KIND_META[issue.kind];
              const KindIcon = kind?.Icon ?? Info;
              return (
                <div
                  key={i}
                  className={cn(
                    "rounded-lg p-3 text-sm ring-1 ring-inset",
                    sev.bg,
                    sev.ring,
                  )}
                >
                  <div className="flex items-start gap-2">
                    <sev.Icon className={cn("mt-0.5 size-4 shrink-0", sev.text)} />
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={cn("font-semibold", sev.text)}>
                          {kind?.label ?? issue.kind}
                        </span>
                        {issue.field && (
                          <code className="rounded bg-background/60 px-1.5 py-0.5 text-[11px] font-mono">
                            {issue.field}
                          </code>
                        )}
                        {issue.rule_ids.length > 0 && (
                          <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                            <KindIcon className="size-3" />
                            {issue.rule_ids.join(", ")}
                          </span>
                        )}
                      </div>
                      <p className="text-xs leading-snug text-foreground/80">
                        {issue.message}
                      </p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
