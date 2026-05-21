"use client";

import { useCallback, useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import api from "@/lib/api";
import { toast } from "sonner";
import { PageTransition } from "@/components/page-transition";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button, buttonVariants } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  ArrowLeft,
  Activity,
  FlaskConical,
  Loader2,
  Play,
  CheckCircle2,
  AlertCircle,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import type {
  LiveRepositoryDetail,
  LiveVersionSummary,
  ImpactRun,
  TestCaseSuiteListItem,
  SuiteExecutionResponse,
} from "@/lib/types";
import { ProductionBadge } from "@/components/live-repo/production-badge";
import { PromoteToProductionButton } from "@/components/live-repo/promote-button";
import { SummaryCards } from "@/components/impact/summary-cards";
import { DistributionChart } from "@/components/impact/distribution-chart";
import { FlipsChart } from "@/components/impact/flips-chart";
import { BusinessImpactCard } from "@/components/impact/business-impact-card";
import { SuiteExecutionPanel } from "@/components/test-cases/suite-execution-panel";
import { cn } from "@/lib/utils";

/**
 * Validate Version page — the "is this candidate safe to promote?"
 * single-pane-of-glass view. Combines:
 *   - Impact analysis (this version vs current production)
 *   - Test-suite execution (this version evaluated against scenario tests)
 *   - One-click Promote to Production CTA when both look good
 */
export default function ValidateVersionPage() {
  const params = useParams<{ repoId: string; versionN: string }>();
  const router = useRouter();
  const repoId = params.repoId;
  const versionN = parseInt(params.versionN, 10);

  const [repo, setRepo] = useState<LiveRepositoryDetail | null>(null);
  const [loading, setLoading] = useState(true);

  const [impactRun, setImpactRun] = useState<ImpactRun | null>(null);
  const [impactRunning, setImpactRunning] = useState(false);

  const [suites, setSuites] = useState<TestCaseSuiteListItem[]>([]);
  const [pickedSuiteId, setPickedSuiteId] = useState<string | null>(null);
  const [suiteReport, setSuiteReport] = useState<SuiteExecutionResponse | null>(null);
  const [suiteRunning, setSuiteRunning] = useState(false);

  const candidateVersion = useMemo<LiveVersionSummary | undefined>(
    () => repo?.versions.find((v) => v.version_number === versionN),
    [repo, versionN],
  );
  const productionVersion = useMemo<LiveVersionSummary | undefined>(
    () => repo?.versions.find((v) => v.version_number === repo?.production_version_number),
    [repo],
  );
  const isProduction = candidateVersion?.id === repo?.production_version_id;

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const repoRes = await api.get<LiveRepositoryDetail>(`/live-repo/${repoId}`);
      setRepo(repoRes.data);

      // Find any prior impact run with this base + candidate combo so we
      // don't force a re-run when one already exists.
      const candId = repoRes.data.versions.find(
        (v) => v.version_number === versionN,
      )?.id;
      const baseId = repoRes.data.production_version_id;
      if (candId) {
        try {
          const irRes = await api.get<ImpactRun[]>(
            `/impact-run?repository_id=${repoId}`,
          );
          const matching = irRes.data
            .filter(
              (ir) =>
                ir.candidate_version_id === candId &&
                (baseId ? ir.base_version_id === baseId : true) &&
                ir.status === "COMPLETED",
            )
            .sort(
              (a, b) =>
                new Date(b.completed_at ?? b.created_at).getTime() -
                new Date(a.completed_at ?? a.created_at).getTime(),
            );
          if (matching[0]) setImpactRun(matching[0]);
        } catch {
          /* ignore — show "Run Impact" CTA */
        }
      }

      // Pull every test suite — let user pick one to execute against
      // this version (or auto-pick the most recently created one).
      const suitesRes = await api.get<TestCaseSuiteListItem[]>("/test-cases");
      setSuites(suitesRes.data);
      if (suitesRes.data.length > 0 && !pickedSuiteId) {
        setPickedSuiteId(suitesRes.data[0].id);
      }
      // If the auto-picked suite has been executed against this version
      // already, surface the existing report immediately.
      const suiteForThisVersion = suitesRes.data.find(
        (s) =>
          s.last_execution &&
          s.last_execution.version_number === versionN,
      );
      if (suiteForThisVersion) {
        setPickedSuiteId(suiteForThisVersion.id);
        try {
          const detailRes = await api.get<{ last_execution_report: SuiteExecutionResponse | null }>(
            `/test-cases/${suiteForThisVersion.id}`,
          );
          if (detailRes.data?.last_execution_report) {
            setSuiteReport(detailRes.data.last_execution_report);
          }
        } catch { /* tolerable */ }
      }
    } catch (err: any) {
      toast.error(
        err?.response?.data?.detail || "Failed to load repository / version.",
      );
    } finally {
      setLoading(false);
    }
  }, [repoId, versionN, pickedSuiteId]);

  useEffect(() => {
    fetchAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repoId, versionN]);

  const handleRunImpact = async () => {
    if (!candidateVersion) return;
    setImpactRunning(true);
    try {
      const { data } = await api.post<ImpactRun>("/impact-run", {
        repository_id: repoId,
        base_version_id: repo?.production_version_id ?? null,
        candidate_version_id: candidateVersion.id,
        created_by: "validate-page",
      });
      setImpactRun(data);
      toast.success(`Impact run completed.`);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Impact run failed.");
    } finally {
      setImpactRunning(false);
    }
  };

  const handleExecuteSuite = async () => {
    if (!pickedSuiteId || !candidateVersion) return;
    setSuiteRunning(true);
    try {
      const { data } = await api.post<SuiteExecutionResponse>(
        `/test-cases/${pickedSuiteId}/execute`,
        { version_id: candidateVersion.id },
      );
      setSuiteReport(data);
      const matches = data.summary?.matches_expected ?? 0;
      const dev = data.summary?.deviates_from_expected ?? 0;
      const total = matches + dev;
      const pct = total ? Math.round((matches / total) * 100) : 0;
      toast.success(`Suite executed — ${pct}% pass rate.`);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Suite execution failed.");
    } finally {
      setSuiteRunning(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!repo || !candidateVersion) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <AlertCircle className="size-10 text-destructive" />
        <p className="mt-3 text-sm text-muted-foreground">
          Version v{versionN} not found in this repository.
        </p>
      </div>
    );
  }

  // Compute "validation health" for the hero
  const flipPct = impactRun?.summary
    ? (() => {
        const flips = impactRun.summary.decision_flips ?? {};
        const total = impactRun.summary.total_loans ?? 0;
        const totalFlips = Object.entries(flips).reduce<number>(
          (acc, [k, v]) => (typeof v === "number" && k.includes("_to_") ? acc + v : acc),
          0,
        );
        return total ? (totalFlips / total) * 100 : 0;
      })()
    : null;
  const passPct = suiteReport?.summary
    ? (() => {
        const m = suiteReport.summary.matches_expected ?? 0;
        const d = suiteReport.summary.deviates_from_expected ?? 0;
        return m + d ? (m / (m + d)) * 100 : 0;
      })()
    : null;

  const validatedHealthy =
    flipPct != null && passPct != null && flipPct < 25 && passPct >= 95;

  return (
    <PageTransition>
      <div className="space-y-6">
        <p className="text-xs text-muted-foreground">
          Dashboard /{" "}
          <Link href="/live-repo" className="hover:underline">
            Live Repo
          </Link>{" "}
          /{" "}
          <Link href={`/live-repo/${repoId}`} className="hover:underline">
            {repo.name}
          </Link>{" "}
          / Validate v{versionN}
        </p>

        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-4">
            <Button
              variant="ghost"
              size="icon-sm"
              render={<Link href={`/live-repo/${repoId}`} />}
            >
              <ArrowLeft className="size-4" />
            </Button>
            <div className="space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <ShieldCheck className="size-6 text-emerald-500" />
                <h1 className="text-2xl font-bold tracking-tight">
                  <span className="text-gradient">
                    Validate v{versionN}
                  </span>
                </h1>
                {isProduction && <ProductionBadge size="md" />}
                {validatedHealthy && !isProduction && (
                  <Badge className="bg-emerald-500/15 text-emerald-700 ring-1 ring-inset ring-emerald-500/30 dark:text-emerald-300">
                    <Sparkles className="size-3" />
                    Looks safe to promote
                  </Badge>
                )}
              </div>
              <p className="text-sm text-muted-foreground">
                {candidateVersion.summary || "No summary"}
              </p>
              <p className="text-[11px] text-muted-foreground">
                {repo.name} · {repo.product}/{repo.jurisdiction} ·{" "}
                {candidateVersion.rule_count} rules ·{" "}
                {productionVersion ? (
                  <>
                    Compared against production{" "}
                    <span className="font-mono">
                      v{productionVersion.version_number}
                    </span>
                  </>
                ) : (
                  "no production version yet"
                )}
              </p>
            </div>
          </div>

          {/* Promote CTA */}
          <PromoteToProductionButton
            repoId={repoId}
            versionNumber={versionN}
            currentProductionVersionNumber={repo.production_version_number ?? null}
            size="default"
            variant={validatedHealthy ? "default" : "outline"}
            onPromoted={fetchAll}
          />
        </div>

        <Separator />

        {/* Two-column results */}
        <div className="grid gap-5 lg:grid-cols-2">
          {/* Impact Analysis */}
          <Card className="card-elevated border-border/40">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <span className="rounded-md bg-rose-500/10 p-1.5 ring-1 ring-inset ring-rose-500/20">
                  <Activity className="size-4 text-rose-600 dark:text-rose-400" />
                </span>
                Impact Analysis
                {impactRun && (
                  <Link
                    href={`/impact-runs/${impactRun.id}`}
                    className={cn(
                      buttonVariants({ variant: "ghost", size: "sm" }),
                      "ml-auto text-xs",
                    )}
                  >
                    Open full report →
                  </Link>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {!impactRun ? (
                <div className="rounded-lg border border-dashed border-border/60 p-6 text-center">
                  <p className="text-sm text-muted-foreground">
                    No impact run for this version yet.
                  </p>
                  <Button
                    variant="default"
                    size="sm"
                    className="mt-3"
                    onClick={handleRunImpact}
                    disabled={impactRunning || !repo.production_version_id}
                  >
                    {impactRunning ? (
                      <Loader2 className="size-3.5 animate-spin" />
                    ) : (
                      <Play className="size-3.5" />
                    )}
                    Run Impact vs production
                  </Button>
                  {!repo.production_version_id && (
                    <p className="mt-2 text-[11px] italic text-muted-foreground">
                      Set a production version first to compare against.
                    </p>
                  )}
                </div>
              ) : (
                <>
                  {/* Slice 2: business-friendly summary above the
                      developer-view charts. Renders only when the
                      run produced a `business_summary` block (post-
                      Slice 2 runs). */}
                  {impactRun.summary && (
                    <BusinessImpactCard summary={impactRun.summary} />
                  )}
                  <SummaryCards summary={impactRun.summary as any} />
                  {impactRun.summary?.decision_distribution && (
                    <DistributionChart summary={impactRun.summary} />
                  )}
                  {impactRun.summary?.decision_flips && (
                    <FlipsChart summary={impactRun.summary} />
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleRunImpact}
                    disabled={impactRunning}
                    className="w-full"
                  >
                    {impactRunning ? (
                      <Loader2 className="size-3.5 animate-spin" />
                    ) : (
                      <Play className="size-3.5" />
                    )}
                    Re-run impact
                  </Button>
                </>
              )}
            </CardContent>
          </Card>

          {/* Suite Execution */}
          <Card className="card-elevated border-border/40">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <span className="rounded-md bg-fuchsia-500/10 p-1.5 ring-1 ring-inset ring-fuchsia-500/20">
                  <FlaskConical className="size-4 text-fuchsia-600 dark:text-fuchsia-400" />
                </span>
                Scenario Test Validation
                {suiteReport && pickedSuiteId && (
                  <Link
                    href={`/test-suites/${pickedSuiteId}`}
                    className={cn(
                      buttonVariants({ variant: "ghost", size: "sm" }),
                      "ml-auto text-xs",
                    )}
                  >
                    Open suite →
                  </Link>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {suites.length === 0 ? (
                <div className="rounded-lg border border-dashed border-border/60 p-6 text-center">
                  <p className="text-sm text-muted-foreground">
                    No test suites generated yet.
                  </p>
                  <Link
                    href="/test-suites"
                    className={cn(
                      buttonVariants({ variant: "default", size: "sm" }),
                      "mt-3",
                    )}
                  >
                    Generate one →
                  </Link>
                </div>
              ) : (
                <>
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium">Test suite</label>
                    <select
                      value={pickedSuiteId ?? ""}
                      onChange={(e) => {
                        setPickedSuiteId(e.target.value);
                        setSuiteReport(null);
                      }}
                      className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs"
                    >
                      {suites.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.rule_set_name || s.id.slice(0, 8)} ({s.total_cases} cases)
                          {s.last_execution
                            ? ` · last ran on v${s.last_execution.version_number}`
                            : ""}
                        </option>
                      ))}
                    </select>
                  </div>
                  <Button
                    variant={suiteReport ? "outline" : "default"}
                    size="sm"
                    onClick={handleExecuteSuite}
                    disabled={!pickedSuiteId || suiteRunning}
                    className="w-full"
                  >
                    {suiteRunning ? (
                      <Loader2 className="size-3.5 animate-spin" />
                    ) : (
                      <Play className="size-3.5" />
                    )}
                    {suiteReport ? "Re-execute against v" : "Execute against v"}
                    {versionN}
                  </Button>
                  {suiteReport && (
                    <SuiteExecutionPanel
                      report={suiteReport}
                      executedAt={new Date().toISOString()}
                    />
                  )}
                </>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Footer guidance card */}
        {validatedHealthy && !isProduction && (
          <Card className="border-emerald-500/30 bg-emerald-500/5">
            <CardContent className="flex items-center gap-4 p-5">
              <div className="flex size-10 items-center justify-center rounded-xl bg-emerald-500/15 ring-1 ring-inset ring-emerald-500/30">
                <CheckCircle2 className="size-5 text-emerald-600 dark:text-emerald-400" />
              </div>
              <div className="flex-1">
                <p className="text-sm font-semibold">v{versionN} looks safe to promote.</p>
                <p className="text-xs text-muted-foreground">
                  Impact run shows {flipPct?.toFixed(1)}% flips and the test suite
                  is at {Math.round(passPct ?? 0)}% pass rate against this version.
                </p>
              </div>
              <PromoteToProductionButton
                repoId={repoId}
                versionNumber={versionN}
                currentProductionVersionNumber={repo.production_version_number ?? null}
                size="default"
                variant="default"
                onPromoted={fetchAll}
              />
            </CardContent>
          </Card>
        )}
      </div>
    </PageTransition>
  );
}
