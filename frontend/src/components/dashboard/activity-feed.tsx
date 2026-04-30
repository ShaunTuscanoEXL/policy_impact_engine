"use client";

import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import {
  FileText,
  GitBranch,
  CheckCircle2,
  GitMerge,
  Activity,
  FlaskConical,
  Clock,
  Inbox,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { DashboardActivityEvent } from "@/lib/types";

interface ActivityFeedProps {
  events: DashboardActivityEvent[];
  loading?: boolean;
}

const EVENT_META: Record<
  DashboardActivityEvent["type"],
  { icon: typeof FileText; bg: string; color: string }
> = {
  brd_uploaded: {
    icon: FileText,
    bg: "bg-blue-500/10",
    color: "text-blue-600 dark:text-blue-400",
  },
  version_created: {
    icon: GitBranch,
    bg: "bg-amber-500/10",
    color: "text-amber-600 dark:text-amber-400",
  },
  version_promoted: {
    icon: CheckCircle2,
    bg: "bg-emerald-500/10",
    color: "text-emerald-600 dark:text-emerald-400",
  },
  merge_proposal: {
    icon: GitMerge,
    bg: "bg-violet-500/10",
    color: "text-violet-600 dark:text-violet-400",
  },
  impact_run: {
    icon: Activity,
    bg: "bg-rose-500/10",
    color: "text-rose-600 dark:text-rose-400",
  },
  suite_executed: {
    icon: FlaskConical,
    bg: "bg-fuchsia-500/10",
    color: "text-fuchsia-600 dark:text-fuchsia-400",
  },
};

function relativeTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const diffMs = Date.now() - d.getTime();
  const diffMin = Math.round(diffMs / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffH = Math.round(diffMin / 60);
  if (diffH < 24) return `${diffH}h ago`;
  const diffD = Math.round(diffH / 24);
  if (diffD < 7) return `${diffD}d ago`;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/**
 * Right-rail activity feed showing the last N events across the
 * product. Each row links to the relevant detail page.
 */
export function ActivityFeed({ events, loading }: ActivityFeedProps) {
  return (
    <Card className="card-elevated border-border/40 h-full">
      <CardContent className="p-5">
        <div className="mb-3 flex items-center gap-2">
          <div className="flex size-7 items-center justify-center rounded-lg bg-slate-500/10 ring-1 ring-inset ring-slate-500/20">
            <Clock className="size-3.5 text-slate-600 dark:text-slate-400" />
          </div>
          <h3 className="text-sm font-semibold tracking-tight">Recent Activity</h3>
        </div>

        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-12 animate-pulse rounded-lg bg-muted/40" />
            ))}
          </div>
        ) : events.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <Inbox className="size-10 text-muted-foreground/20" />
            <p className="mt-2 text-xs text-muted-foreground">
              No activity yet. Upload a BRD to get started.
            </p>
          </div>
        ) : (
          <ul className="space-y-1">
            {events.map((e, i) => {
              const meta = EVENT_META[e.type];
              const Icon = meta.icon;
              return (
                <li key={`${e.type}-${i}-${e.ts}`}>
                  <Link
                    href={e.href}
                    className="flex items-start gap-3 rounded-lg p-2 transition-colors hover:bg-accent/50"
                  >
                    <div
                      className={cn(
                        "mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md ring-1 ring-inset",
                        meta.bg,
                        meta.color.replace("text-", "ring-").split(" ")[0] + "/20",
                      )}
                    >
                      <Icon className={cn("size-3.5", meta.color)} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-xs font-medium text-foreground">
                        {e.title}
                      </p>
                      {e.subtitle && (
                        <p className="truncate text-[11px] text-muted-foreground">
                          {e.subtitle}
                        </p>
                      )}
                    </div>
                    <span className="shrink-0 text-[10px] font-medium text-muted-foreground/80">
                      {relativeTime(e.ts)}
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
