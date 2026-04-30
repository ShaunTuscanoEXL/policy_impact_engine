"use client";

import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { ProductionBadge } from "@/components/live-repo/production-badge";
import {
  GitBranch,
  GitMerge,
  Activity,
  FlaskConical,
  ArrowUpRight,
  Clock,
  AlertCircle,
  CheckCircle2,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type {
  DashboardLiveRepoSummary,
  DashboardPendingMergeQueue,
  DashboardLastImpactRun,
  DashboardLastSuiteExecution,
} from "@/lib/types";

interface HeroBandProps {
  liveRepos: DashboardLiveRepoSummary[];
  pendingQueue: DashboardPendingMergeQueue;
  lastImpactRun: DashboardLastImpactRun | null;
  lastSuiteExecution: DashboardLastSuiteExecution | null;
}

function ageString(hours: number | null): string {
  if (hours == null) return "—";
  if (hours < 1) return `${Math.round(hours * 60)}m`;
  if (hours < 24) return `${Math.round(hours)}h`;
  return `${Math.round(hours / 24)}d`;
}

/**
 * Top-of-dashboard "what matters right now" band — four KPI cards each
 * answering one question an operator opens the app to ask:
 *
 *   1. What's live? (production versions across repos)
 *   2. What needs my attention? (pending merge queue)
 *   3. What just happened in policy? (last impact run flips)
 *   4. Are tests still passing? (last suite execution pass rate)
 */
export function HeroBand({
  liveRepos,
  pendingQueue,
  lastImpactRun,
  lastSuiteExecution,
}: HeroBandProps) {
  const productionRepos = liveRepos.filter(
    (r) => r.production_version_number != null,
  );
  const StalenessIcon =
    pendingQueue.count === 0
      ? CheckCircle2
      : (pendingQueue.oldest_age_hours ?? 0) > 24
        ? AlertCircle
        : Clock;
  const queueAccent =
    pendingQueue.count === 0
      ? "from-emerald-500/20 to-emerald-500/5 border-emerald-500/30 text-emerald-700 dark:text-emerald-300"
      : (pendingQueue.oldest_age_hours ?? 0) > 24
        ? "from-red-500/20 to-red-500/5 border-red-500/30 text-red-700 dark:text-red-300"
        : "from-amber-500/20 to-amber-500/5 border-amber-500/30 text-amber-700 dark:text-amber-300";

  const flipRatePct = lastImpactRun
    ? (lastImpactRun.flip_rate * 100).toFixed(1)
    : null;
  const passRatePct = lastSuiteExecution
    ? Math.round(lastSuiteExecution.pass_rate * 100)
    : null;
  const passAccent =
    passRatePct == null
      ? "from-slate-500/10 to-slate-500/5 border-slate-500/20 text-slate-700 dark:text-slate-300"
      : passRatePct >= 95
        ? "from-emerald-500/20 to-emerald-500/5 border-emerald-500/30 text-emerald-700 dark:text-emerald-300"
        : passRatePct >= 80
          ? "from-amber-500/20 to-amber-500/5 border-amber-500/30 text-amber-700 dark:text-amber-300"
          : "from-red-500/20 to-red-500/5 border-red-500/30 text-red-700 dark:text-red-300";

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {/* 1. What's live in production */}
      <Card className="relative overflow-hidden border-border/40 card-elevated">
        <div className="absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r from-amber-500 to-orange-500" />
        <CardContent className="space-y-3 p-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="flex size-8 items-center justify-center rounded-lg bg-amber-500/10 ring-1 ring-inset ring-amber-500/20">
                <GitBranch className="size-4 text-amber-600 dark:text-amber-400" />
              </div>
              <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Live Repositories
              </span>
            </div>
            <Link
              href="/live-repo"
              className="text-muted-foreground/60 hover:text-foreground"
              title="Manage live repositories"
            >
              <ArrowUpRight className="size-4" />
            </Link>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-3xl font-bold tabular-nums">
              {productionRepos.length}
            </span>
            <span className="text-xs text-muted-foreground">
              live · {liveRepos.length} total
            </span>
          </div>
          <div className="space-y-1">
            {productionRepos.slice(0, 3).map((r) => (
              <Link
                key={r.id}
                href={`/live-repo/${r.id}`}
                className="flex items-center justify-between rounded-md px-1.5 py-1 text-xs hover:bg-accent/50"
              >
                <span className="truncate font-medium">{r.name}</span>
                <span className="ml-2 flex shrink-0 items-center gap-1">
                  <span className="font-mono text-[10px] text-muted-foreground">
                    v{r.production_version_number}
                  </span>
                  {r.has_unpromoted_candidate && (
                    <span
                      className="inline-flex items-center gap-0.5 rounded-full bg-blue-500/10 px-1 py-0.5 text-[9px] font-bold uppercase text-blue-600 ring-1 ring-inset ring-blue-500/20 dark:text-blue-400"
                      title={`Newer candidate v${r.current_version} not yet promoted`}
                    >
                      <Sparkles className="size-2.5" />
                      v{r.current_version}
                    </span>
                  )}
                </span>
              </Link>
            ))}
            {productionRepos.length === 0 && (
              <p className="text-xs italic text-muted-foreground">
                No version promoted to production yet.
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* 2. Pending HITL queue */}
      <Card
        className={cn(
          "relative overflow-hidden border bg-gradient-to-br card-elevated",
          queueAccent,
        )}
      >
        <CardContent className="space-y-3 p-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="flex size-8 items-center justify-center rounded-lg bg-white/40 ring-1 ring-inset ring-current/10 dark:bg-black/20">
                <GitMerge className="size-4" />
              </div>
              <span className="text-[11px] font-semibold uppercase tracking-wider opacity-80">
                Pending Merge Queue
              </span>
            </div>
            <Link
              href="/merge-workbench"
              className="opacity-50 hover:opacity-100"
              title="Open merge workbench"
            >
              <ArrowUpRight className="size-4" />
            </Link>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-3xl font-bold tabular-nums">
              {pendingQueue.count}
            </span>
            <span className="text-xs opacity-80">
              {pendingQueue.count === 1 ? "proposal awaiting" : "proposals awaiting"}
            </span>
          </div>
          <div className="flex items-center gap-1.5 text-xs">
            <StalenessIcon className="size-3.5" />
            <span>
              {pendingQueue.count === 0 ? (
                <>Queue clear — nothing waiting on you.</>
              ) : (
                <>
                  Oldest waiting{" "}
                  <span className="font-mono font-semibold">
                    {ageString(pendingQueue.oldest_age_hours)}
                  </span>
                </>
              )}
            </span>
          </div>
        </CardContent>
      </Card>

      {/* 3. Last impact run */}
      <Card className="relative overflow-hidden border-border/40 card-elevated">
        <div className="absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r from-rose-500 to-pink-500" />
        <CardContent className="space-y-3 p-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="flex size-8 items-center justify-center rounded-lg bg-rose-500/10 ring-1 ring-inset ring-rose-500/20">
                <Activity className="size-4 text-rose-600 dark:text-rose-400" />
              </div>
              <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Last Impact Run
              </span>
            </div>
            {lastImpactRun && (
              <Link
                href={`/impact-runs/${lastImpactRun.id}`}
                className="text-muted-foreground/60 hover:text-foreground"
                title="Open impact run detail"
              >
                <ArrowUpRight className="size-4" />
              </Link>
            )}
          </div>
          {lastImpactRun ? (
            <>
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-3xl font-bold tabular-nums">
                  {flipRatePct}%
                </span>
                <span className="text-xs text-muted-foreground">
                  decision flips
                </span>
              </div>
              <div className="space-y-0.5 text-xs">
                <div className="text-muted-foreground">
                  {lastImpactRun.total_flips.toLocaleString()} of{" "}
                  {lastImpactRun.total_loans.toLocaleString()} loans changed
                </div>
                {lastImpactRun.by_subsystem_top.length > 0 && (
                  <div className="flex items-center gap-1 text-muted-foreground">
                    <span>Top driver:</span>
                    <span className="font-mono font-semibold text-foreground">
                      {lastImpactRun.by_subsystem_top[0].key}
                    </span>
                  </div>
                )}
              </div>
            </>
          ) : (
            <p className="text-xs italic text-muted-foreground">
              No impact runs yet. Compare two versions to see what changes.
            </p>
          )}
        </CardContent>
      </Card>

      {/* 4. Last suite execution */}
      <Card
        className={cn(
          "relative overflow-hidden border bg-gradient-to-br card-elevated",
          passAccent,
        )}
      >
        <CardContent className="space-y-3 p-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="flex size-8 items-center justify-center rounded-lg bg-white/40 ring-1 ring-inset ring-current/10 dark:bg-black/20">
                <FlaskConical className="size-4" />
              </div>
              <span className="text-[11px] font-semibold uppercase tracking-wider opacity-80">
                Last Test-Suite Run
              </span>
            </div>
            {lastSuiteExecution && (
              <Link
                href={`/test-suites/${lastSuiteExecution.suite_id}`}
                className="opacity-50 hover:opacity-100"
                title="Open suite detail"
              >
                <ArrowUpRight className="size-4" />
              </Link>
            )}
          </div>
          {lastSuiteExecution ? (
            <>
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-3xl font-bold tabular-nums">
                  {passRatePct}%
                </span>
                <span className="text-xs opacity-80">pass rate</span>
              </div>
              <div className="text-xs opacity-80">
                {lastSuiteExecution.passing.toLocaleString()} /{" "}
                {lastSuiteExecution.total_assertions.toLocaleString()} loans matched
                {lastSuiteExecution.version_number != null && (
                  <> · vs v{lastSuiteExecution.version_number}</>
                )}
              </div>
            </>
          ) : (
            <p className="text-xs italic opacity-80">
              No test-suite runs yet. Generate a suite and execute it.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
