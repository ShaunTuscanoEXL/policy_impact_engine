"use client";

/**
 * AuditTimeline — chronological log of every meaningful action taken
 * on a BRD (or repo / entity). Renders one row per AuditEvent with:
 *   - icon + colour band keyed off action type
 *   - actor + relative timestamp
 *   - rationale (when present)
 *   - structured metadata badges (version_number, total_flips, etc.)
 *
 * Pulls from `/api/v1/audit-events?brd_id=...` (or `?repository_id=...`)
 * via SWR-style refetch on mount + visibility-change so a user
 * returning from a downstream action sees the new event immediately.
 */
import { useCallback, useEffect, useState } from "react";
import api from "@/lib/api";
import type { AuditAction, AuditEvent } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Activity,
  CheckCircle2,
  GitMerge,
  Rocket,
  FlaskConical,
  Upload,
  ScrollText,
  Edit2,
  Trash2,
  Plus,
  XCircle,
  Loader2,
  Clock,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  /** Filter the timeline by BRD. */
  brdId?: string;
  /** Or filter by repo (used on live-repo pages). */
  repositoryId?: string;
  /** Maximum events to render. Defaults to 50. */
  limit?: number;
  /** Override the card title. */
  title?: string;
  /** Optional className for the wrapping card. */
  className?: string;
}

type ActionStyle = {
  Icon: typeof Activity;
  tone: string;
  iconBg: string;
  label: string;
};

const ACTION_STYLES: Record<AuditAction, ActionStyle> = {
  BRD_UPLOADED: {
    Icon: Upload,
    tone: "text-blue-700 dark:text-blue-300",
    iconBg: "bg-blue-500/15 ring-blue-500/30",
    label: "BRD uploaded",
  },
  RULES_EXTRACTED: {
    Icon: ScrollText,
    tone: "text-cyan-700 dark:text-cyan-300",
    iconBg: "bg-cyan-500/15 ring-cyan-500/30",
    label: "Rules extracted",
  },
  RULE_SET_APPROVED: {
    Icon: CheckCircle2,
    tone: "text-emerald-700 dark:text-emerald-300",
    iconBg: "bg-emerald-500/15 ring-emerald-500/30",
    label: "Rule set approved",
  },
  RULE_EDITED: {
    Icon: Edit2,
    tone: "text-amber-700 dark:text-amber-300",
    iconBg: "bg-amber-500/15 ring-amber-500/30",
    label: "Rule edited",
  },
  RULE_DELETED: {
    Icon: Trash2,
    tone: "text-rose-700 dark:text-rose-300",
    iconBg: "bg-rose-500/15 ring-rose-500/30",
    label: "Rule deleted",
  },
  RULE_ADDED: {
    Icon: Plus,
    tone: "text-emerald-700 dark:text-emerald-300",
    iconBg: "bg-emerald-500/15 ring-emerald-500/30",
    label: "Rule added",
  },
  MERGE_PROPOSAL_CREATED: {
    Icon: GitMerge,
    tone: "text-violet-700 dark:text-violet-300",
    iconBg: "bg-violet-500/15 ring-violet-500/30",
    label: "Merge proposal created",
  },
  MERGE_PROPOSAL_APPLIED: {
    Icon: GitMerge,
    tone: "text-fuchsia-700 dark:text-fuchsia-300",
    iconBg: "bg-fuchsia-500/15 ring-fuchsia-500/30",
    label: "Merge applied",
  },
  MERGE_PROPOSAL_REJECTED: {
    Icon: XCircle,
    tone: "text-rose-700 dark:text-rose-300",
    iconBg: "bg-rose-500/15 ring-rose-500/30",
    label: "Merge rejected",
  },
  MERGE_ITEM_DECIDED: {
    Icon: Edit2,
    tone: "text-slate-700 dark:text-slate-300",
    iconBg: "bg-slate-500/15 ring-slate-500/30",
    label: "Merge item decision",
  },
  VERSION_PROMOTED: {
    Icon: Rocket,
    tone: "text-emerald-700 dark:text-emerald-300",
    iconBg: "bg-emerald-500/15 ring-emerald-500/30",
    label: "Version promoted to production",
  },
  IMPACT_RUN_STARTED: {
    Icon: Activity,
    tone: "text-rose-700 dark:text-rose-300",
    iconBg: "bg-rose-500/15 ring-rose-500/30",
    label: "Impact run started",
  },
  IMPACT_RUN_COMPLETED: {
    Icon: Activity,
    tone: "text-rose-700 dark:text-rose-300",
    iconBg: "bg-rose-500/15 ring-rose-500/30",
    label: "Impact run completed",
  },
  SUITE_GENERATED: {
    Icon: FlaskConical,
    tone: "text-fuchsia-700 dark:text-fuchsia-300",
    iconBg: "bg-fuchsia-500/15 ring-fuchsia-500/30",
    label: "Test suite generated",
  },
  SUITE_EXECUTED: {
    Icon: FlaskConical,
    tone: "text-emerald-700 dark:text-emerald-300",
    iconBg: "bg-emerald-500/15 ring-emerald-500/30",
    label: "Test suite executed",
  },
};

function formatRelative(ts: string): string {
  const date = new Date(ts);
  const diffMs = Date.now() - date.getTime();
  const sec = Math.floor(diffMs / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 7) return `${day}d ago`;
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: date.getFullYear() !== new Date().getFullYear() ? "numeric" : undefined,
  });
}

function metadataBadges(event: AuditEvent): { key: string; value: string }[] {
  const meta = event.metadata || {};
  const out: { key: string; value: string }[] = [];
  if (typeof meta.version_number === "number") {
    out.push({ key: "version", value: `v${meta.version_number}` });
  }
  if (typeof meta.new_version_number === "number") {
    out.push({ key: "new version", value: `v${meta.new_version_number}` });
  }
  if (typeof meta.rule_count === "number") {
    out.push({
      key: "rules",
      value: `${meta.rule_count.toLocaleString()} rule${meta.rule_count !== 1 ? "s" : ""}`,
    });
  }
  if (typeof meta.items_total === "number") {
    out.push({
      key: "items",
      value: `${meta.items_total} merge item${meta.items_total !== 1 ? "s" : ""}`,
    });
  }
  if (typeof meta.total_flips === "number") {
    out.push({
      key: "flips",
      value: `${meta.total_flips.toLocaleString()} flips`,
    });
  }
  if (typeof meta.matches_expected === "number" && typeof meta.deviates_from_expected === "number") {
    const pass = meta.matches_expected;
    const fail = meta.deviates_from_expected;
    out.push({
      key: "exec",
      value: `${pass.toLocaleString()} pass / ${fail.toLocaleString()} fail`,
    });
  }
  if (typeof meta.status === "string" && meta.status !== "COMPLETED") {
    out.push({ key: "status", value: meta.status });
  }
  return out;
}

export function AuditTimeline({
  brdId,
  repositoryId,
  limit = 50,
  title = "Activity timeline",
  className,
}: Props) {
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchEvents = useCallback(async () => {
    if (!brdId && !repositoryId) {
      setEvents([]);
      setLoading(false);
      return;
    }
    try {
      const params: Record<string, any> = { limit };
      if (brdId) params.brd_id = brdId;
      else if (repositoryId) params.repository_id = repositoryId;
      const { data } = await api.get<AuditEvent[]>("/audit-events", { params });
      setEvents(data);
      setError(null);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to load audit events.");
    } finally {
      setLoading(false);
    }
  }, [brdId, repositoryId, limit]);

  useEffect(() => {
    fetchEvents();
    // Refresh when the tab becomes visible — catches the
    // "user-just-came-back-from-an-action" case.
    const onVis = () => {
      if (document.visibilityState === "visible") fetchEvents();
    };
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, [fetchEvents]);

  return (
    <Card className={cn("card-elevated border-border/50", className)}>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <span className="rounded-md bg-slate-500/10 p-1.5 ring-1 ring-inset ring-slate-500/20">
            <Clock className="size-4 text-slate-600 dark:text-slate-400" />
          </span>
          {title}
          {events && events.length > 0 && (
            <Badge variant="outline" className="ml-1 text-[10px]">
              {events.length} event{events.length !== 1 ? "s" : ""}
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            <Loader2 className="size-5 animate-spin" />
          </div>
        ) : error ? (
          <p className="py-6 text-center text-sm text-rose-600 dark:text-rose-400">
            {error}
          </p>
        ) : !events || events.length === 0 ? (
          <p className="py-6 text-center text-sm italic text-muted-foreground">
            No audit events yet — actions taken in this pipeline will appear here.
          </p>
        ) : (
          <ol className="relative space-y-4">
            {/* Vertical rail */}
            <span
              className="absolute left-[19px] top-3 bottom-3 w-px bg-border/60"
              aria-hidden
            />
            {events.map((event) => {
              const style =
                ACTION_STYLES[event.action] ?? {
                  Icon: Activity,
                  tone: "text-slate-700 dark:text-slate-300",
                  iconBg: "bg-slate-500/15 ring-slate-500/30",
                  label: event.action,
                };
              const badges = metadataBadges(event);
              return (
                <li key={event.id} className="relative flex gap-3 pl-0">
                  <div
                    className={cn(
                      "relative z-10 flex size-10 shrink-0 items-center justify-center rounded-full ring-1 ring-inset",
                      style.iconBg,
                    )}
                  >
                    <style.Icon className={cn("size-4", style.tone)} />
                  </div>
                  <div className="flex-1 space-y-1 pb-1">
                    <div className="flex flex-wrap items-baseline gap-2">
                      <span className={cn("text-sm font-medium", style.tone)}>
                        {style.label}
                      </span>
                      <span className="text-[11px] text-muted-foreground">
                        by{" "}
                        <span className="font-medium text-foreground">
                          {event.actor || "system"}
                        </span>{" "}
                        · {formatRelative(event.created_at)}
                      </span>
                    </div>
                    {event.rationale && (
                      <p className="rounded-md bg-muted/40 px-2.5 py-1.5 text-xs italic text-muted-foreground">
                        &ldquo;{event.rationale}&rdquo;
                      </p>
                    )}
                    {badges.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {badges.map((b) => (
                          <Badge
                            key={b.key}
                            variant="outline"
                            className="text-[10px] font-mono"
                          >
                            {b.value}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}
