"use client";

import { useEffect, useState } from "react";
import api from "@/lib/api";
import { PageTransition, StaggerContainer, StaggerItem } from "@/components/page-transition";
import { QuickActions } from "@/components/dashboard/quick-actions";
import { HeroBand } from "@/components/dashboard/hero-band";
import { PipelineFunnel } from "@/components/dashboard/pipeline-funnel";
import { ActivityFeed } from "@/components/dashboard/activity-feed";
import { TrendChart } from "@/components/dashboard/trend-chart";
import { LayoutDashboard, Loader2 } from "lucide-react";
import { WelcomeBanner } from "@/components/onboarding/welcome-banner";
import type {
  DashboardStats,
  DashboardActivityEvent,
  DashboardTrends,
} from "@/lib/types";

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [activity, setActivity] = useState<DashboardActivityEvent[]>([]);
  const [trends, setTrends] = useState<DashboardTrends | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function fetchAll() {
      setLoading(true);
      try {
        const [statsRes, activityRes, trendsRes] = await Promise.allSettled([
          api.get<DashboardStats>("/dashboard"),
          api.get<DashboardActivityEvent[]>("/dashboard/activity?limit=15"),
          api.get<DashboardTrends>("/dashboard/trends?limit=12"),
        ]);
        if (cancelled) return;
        if (statsRes.status === "fulfilled") setStats(statsRes.value.data);
        if (activityRes.status === "fulfilled") setActivity(activityRes.value.data);
        if (trendsRes.status === "fulfilled") setTrends(trendsRes.value.data);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    fetchAll();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <PageTransition>
      <div className="space-y-6">
        {/* Slice 8: dismissible welcome banner — explains the 5-stage
            pipeline. Hidden after the user clicks "Got it". */}
        <WelcomeBanner />

        {/* Header */}
        <div className="flex items-center gap-4">
          <div className="icon-badge bg-blue-100 dark:bg-blue-900/30">
            <LayoutDashboard className="size-5 text-blue-600 dark:text-blue-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              <span className="text-gradient">Mission Control</span>
            </h1>
            <p className="text-sm text-muted-foreground">
              What's live, what's pending, and what just happened across the policy lifecycle.
            </p>
          </div>
        </div>

        {loading && !stats ? (
          <div className="flex items-center justify-center py-32">
            <Loader2 className="size-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <StaggerContainer className="space-y-5">
            {/* Hero band: 4 KPI cards */}
            {stats && (
              <StaggerItem>
                <HeroBand
                  liveRepos={stats.live_repos}
                  pendingQueue={stats.pending_merge_queue}
                  lastImpactRun={stats.last_impact_run}
                  lastSuiteExecution={stats.last_suite_execution}
                />
              </StaggerItem>
            )}

            {/* Pipeline funnel */}
            {stats && (
              <StaggerItem>
                <PipelineFunnel counters={stats.pipeline} />
              </StaggerItem>
            )}

            {/* Trend chart + activity feed (2-col) */}
            <StaggerItem>
              <div className="grid gap-5 lg:grid-cols-3">
                <div className="lg:col-span-2">
                  {trends ? (
                    <TrendChart trends={trends} />
                  ) : (
                    <div className="h-64 animate-pulse rounded-xl bg-muted/40" />
                  )}
                </div>
                <ActivityFeed events={activity} loading={loading && activity.length === 0} />
              </div>
            </StaggerItem>

            {/* Quick actions (preserved from before) */}
            <StaggerItem>
              <QuickActions />
            </StaggerItem>
          </StaggerContainer>
        )}
      </div>
    </PageTransition>
  );
}
