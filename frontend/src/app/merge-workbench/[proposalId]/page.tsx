"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import api from "@/lib/api";
import type {
  BrdDocument,
  LiveRepository,
  MergeAction,
  MergeApplyResult,
  MergeItem,
  MergeProposal,
} from "@/lib/types";
import { toast } from "sonner";
import { PageTransition } from "@/components/page-transition";
import { PipelineContextBar } from "@/components/brds/pipeline/pipeline-context-bar";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogClose,
} from "@/components/ui/dialog";
import {
  GitMerge,
  ArrowLeft,
  Loader2,
  AlertTriangle,
  CheckCircle,
  XCircle,
  FileText,
  GitBranch,
  Sparkles,
} from "lucide-react";

const ACTION_OPTIONS: MergeAction[] = [
  "ACCEPT",
  "REJECT",
  "SUPERSEDE",
  "DROP",
  "KEEP_BOTH",
  "RETIRE",
  "NEEDS_HUMAN",
  "EDIT_NEEDED",
];

const SEVERITY_STYLES: Record<string, string> = {
  HARD: "bg-red-500/10 text-red-600 border-red-500/20 dark:text-red-400",
  SOFT: "bg-amber-500/10 text-amber-600 border-amber-500/20 dark:text-amber-400",
  INFO: "bg-slate-500/10 text-slate-600 border-slate-500/20 dark:text-slate-400",
};

const STATUS_STYLES: Record<string, string> = {
  PENDING: "bg-amber-500/10 text-amber-600 border-amber-500/20 dark:text-amber-400",
  APPROVED: "bg-emerald-500/10 text-emerald-600 border-emerald-500/20 dark:text-emerald-400",
  REJECTED: "bg-red-500/10 text-red-600 border-red-500/20 dark:text-red-400",
  APPLIED: "bg-blue-500/10 text-blue-600 border-blue-500/20 dark:text-blue-400",
};

const CATEGORY_LABEL: Record<string, string> = {
  EXACT_DUPLICATE: "Exact Duplicate",
  THRESHOLD_TIGHTENING: "Threshold Tightening",
  THRESHOLD_RELAXATION: "Threshold Relaxation",
  OPPOSITE_DIRECTION: "Opposite Direction",
  TIERED_REPLACEMENT: "Tiered Replacement",
  OVERLAPPING_RANGE: "Overlapping Range",
  NEW_RULE: "New Rule",
  REMOVED_RULE: "Removed Rule",
  ACTION_DRIFT: "Action Drift",
  COVERAGE_GAP: "Coverage Gap",
};

function formatThreshold(value: any): string {
  if (value === null || value === undefined) return "—";
  if (Array.isArray(value)) return `[${value.join(", ")}]`;
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function formatCondition(c: Record<string, any>): string {
  const field = c.field ?? "?";
  const op = c.operator ?? "?";
  const value = c.value;
  if (op === "between" && Array.isArray(value)) {
    return `${field} between [${value.join(", ")}]`;
  }
  if (op === "in" || op === "not_in") {
    return `${field} ${op} [${Array.isArray(value) ? value.join(", ") : value}]`;
  }
  return `${field} ${op} ${formatThreshold(value)}`;
}

function formatActionLine(a: Record<string, any>): {
  type: string;
  target: string;
  value: string;
} {
  const type = String(a.action_type ?? "?").toUpperCase();
  const target = a.target_field ?? "";
  const value =
    a.value === undefined || a.value === null ? "" : formatThreshold(a.value);
  return { type, target, value };
}

const ACTION_TONE: Record<string, string> = {
  REJECT: "text-rose-700 bg-rose-500/10 ring-rose-500/30 dark:text-rose-300",
  DECLINE: "text-rose-700 bg-rose-500/10 ring-rose-500/30 dark:text-rose-300",
  AUTO_REJECT:
    "text-rose-700 bg-rose-500/10 ring-rose-500/30 dark:text-rose-300",
  FLAG: "text-amber-700 bg-amber-500/10 ring-amber-500/30 dark:text-amber-300",
  MANUAL_REVIEW:
    "text-amber-700 bg-amber-500/10 ring-amber-500/30 dark:text-amber-300",
  REVIEW: "text-amber-700 bg-amber-500/10 ring-amber-500/30 dark:text-amber-300",
  SET: "text-blue-700 bg-blue-500/10 ring-blue-500/30 dark:text-blue-300",
  CAP: "text-violet-700 bg-violet-500/10 ring-violet-500/30 dark:text-violet-300",
  ADJUST:
    "text-violet-700 bg-violet-500/10 ring-violet-500/30 dark:text-violet-300",
  MODIFY:
    "text-violet-700 bg-violet-500/10 ring-violet-500/30 dark:text-violet-300",
  APPROVE:
    "text-emerald-700 bg-emerald-500/10 ring-emerald-500/30 dark:text-emerald-300",
};

const SUBSYSTEM_TONE: Record<string, string> = {
  BUREAU_GATE:
    "bg-blue-500/10 text-blue-700 dark:text-blue-300 ring-blue-500/30",
  DTI_GATE:
    "bg-amber-500/10 text-amber-700 dark:text-amber-300 ring-amber-500/30",
  INCOME_GATE:
    "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 ring-emerald-500/30",
  AMOUNT_CAP:
    "bg-orange-500/10 text-orange-700 dark:text-orange-300 ring-orange-500/30",
  PRICING_TIER:
    "bg-fuchsia-500/10 text-fuchsia-700 dark:text-fuchsia-300 ring-fuchsia-500/30",
  EMPLOYMENT_GATE:
    "bg-violet-500/10 text-violet-700 dark:text-violet-300 ring-violet-500/30",
  BANKING_BEHAVIOR:
    "bg-cyan-500/10 text-cyan-700 dark:text-cyan-300 ring-cyan-500/30",
  RATE_MODIFIER:
    "bg-rose-500/10 text-rose-700 dark:text-rose-300 ring-rose-500/30",
  FRAUD_SIGNAL:
    "bg-red-500/10 text-red-700 dark:text-red-300 ring-red-500/30",
  REGULATORY_FLOOR:
    "bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 ring-indigo-500/30",
  EXPOSURE_LIMIT:
    "bg-yellow-500/10 text-yellow-700 dark:text-yellow-300 ring-yellow-500/30",
  SCORING_MODEL:
    "bg-purple-500/10 text-purple-700 dark:text-purple-300 ring-purple-500/30",
  UNCLASSIFIED:
    "bg-slate-500/10 text-slate-600 dark:text-slate-400 ring-slate-500/30",
};

/**
 * Renders a complete rule (name, description, all conditions, all
 * actions with target+value) — full fidelity, no canonical projection
 * collapsing fields. The merge engine still does its diff work on the
 * canonical projection, but the reviewer sees the actual rule.
 */
function RulePanel({
  rule,
  side,
  side_label,
}: {
  rule: import("@/lib/types").MergeRulePayload | null | undefined;
  side: "incoming" | "live" | "neutral";
  side_label?: string;
}) {
  if (!rule) {
    return (
      <div className="rounded-md border border-dashed border-border/40 bg-muted/20 p-3">
        <p className="text-xs italic text-muted-foreground">
          No rule data on this side.
        </p>
      </div>
    );
  }
  const sideTone =
    side === "incoming"
      ? "border-emerald-500/30 bg-emerald-500/[0.03]"
      : side === "live"
        ? "border-rose-500/30 bg-rose-500/[0.03]"
        : "border-border/50 bg-muted/20";
  const labelTone =
    side === "incoming"
      ? "text-emerald-700 dark:text-emerald-300"
      : side === "live"
        ? "text-rose-700 dark:text-rose-300"
        : "text-muted-foreground";
  return (
    <div className={`space-y-3 rounded-lg border p-3.5 ${sideTone}`}>
      {/* Side label + subsystem + rule_type */}
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`text-[10px] font-bold uppercase tracking-[0.14em] ${labelTone}`}
        >
          {side_label ?? (side === "incoming" ? "Incoming" : side === "live" ? "Live" : "Rule")}
        </span>
        {rule.subsystem && (
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ring-1 ring-inset ${SUBSYSTEM_TONE[rule.subsystem] ?? SUBSYSTEM_TONE.UNCLASSIFIED}`}
          >
            {rule.subsystem}
          </span>
        )}
        {rule.rule_type && (
          <span className="inline-flex items-center rounded-full bg-muted/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            {rule.rule_type}
          </span>
        )}
        {rule.rule_id && (
          <span className="ml-auto font-mono text-[10px] text-muted-foreground">
            {rule.rule_id}
          </span>
        )}
      </div>

      {/* Rule name + description */}
      {rule.rule_name && (
        <div>
          <p className="text-sm font-semibold leading-tight">{rule.rule_name}</p>
          {rule.description && (
            <p className="mt-0.5 text-xs text-muted-foreground">
              {rule.description}
            </p>
          )}
        </div>
      )}

      {/* Conditions */}
      {rule.conditions && rule.conditions.length > 0 ? (
        <div>
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Conditions
          </p>
          <ul className="space-y-1">
            {rule.conditions.map((c, i) => (
              <li key={i} className="font-mono text-[11px]">
                <span className="rounded bg-muted/40 px-1.5 py-0.5">
                  {formatCondition(c)}
                </span>
                {i < rule.conditions.length - 1 && (
                  <span className="mx-1 text-[9px] font-bold text-muted-foreground/60">
                    {(rule.conditions[i + 1]?.logic ?? "AND")
                      .toString()
                      .toUpperCase()}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="text-[11px] italic text-muted-foreground/70">
          No conditions — applies always.
        </p>
      )}

      {/* Actions */}
      {rule.actions && rule.actions.length > 0 && (
        <div>
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Actions
          </p>
          <ul className="space-y-1">
            {rule.actions.map((a, i) => {
              const { type, target, value } = formatActionLine(a);
              return (
                <li key={i} className="flex flex-wrap items-baseline gap-1.5 font-mono text-[11px]">
                  <span
                    className={`inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ring-1 ring-inset ${ACTION_TONE[type] ?? "bg-muted/40 text-muted-foreground"}`}
                  >
                    {type}
                  </span>
                  {target && (
                    <span className="font-mono">
                      <span className="text-muted-foreground">→</span> {target}
                    </span>
                  )}
                  {value && (
                    <>
                      <span className="text-muted-foreground">=</span>
                      <span className="font-mono font-semibold">{value}</span>
                    </>
                  )}
                  {a.description && (
                    <span className="text-[10px] italic text-muted-foreground">
                      — {a.description}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}

function DiffBlock({
  item,
}: {
  item: import("@/lib/types").MergeItem;
}) {
  const incoming = item.incoming_rule;
  const live = item.live_rule;

  if (item.category === "NEW_RULE") {
    return (
      <RulePanel rule={incoming} side="incoming" side_label="New Rule" />
    );
  }

  if (item.category === "REMOVED_RULE") {
    return (
      <RulePanel
        rule={live}
        side="live"
        side_label="Removed from BRD (still live)"
      />
    );
  }

  // Collision categories: side-by-side LIVE vs INCOMING
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <RulePanel rule={live} side="live" side_label="Live (current)" />
      <RulePanel rule={incoming} side="incoming" side_label="Incoming (BRD)" />
    </div>
  );
}

export default function MergeWorkbenchDetailPage() {
  const params = useParams<{ proposalId: string }>();
  const router = useRouter();
  const proposalId = params.proposalId;

  const [proposal, setProposal] = useState<MergeProposal | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingItemId, setSavingItemId] = useState<string | null>(null);
  const [notesDraft, setNotesDraft] = useState<Record<string, string>>({});

  const [applyOpen, setApplyOpen] = useState(false);
  const [decidedBy, setDecidedBy] = useState("");
  const [applying, setApplying] = useState(false);
  const [repo, setRepo] = useState<LiveRepository | null>(null);
  const [brd, setBrd] = useState<BrdDocument | null>(null);

  const fetchProposal = useCallback(async () => {
    try {
      const { data } = await api.get<MergeProposal>(
        `/merge-proposal/${proposalId}`
      );
      setProposal(data);
      setNotesDraft(
        data.items.reduce<Record<string, string>>((acc, item) => {
          acc[item.id] = item.notes || "";
          return acc;
        }, {})
      );

      // Resolve repo + BRD names so the header shows something readable
      // instead of UUID prefixes.
      const [repoResp, brdResp] = await Promise.all([
        api.get<LiveRepository>(`/live-repo/${data.repository_id}`).catch(() => null),
        api.get<BrdDocument>(`/brds/${data.source_brd_id}`).catch(() => null),
      ]);
      if (repoResp) setRepo(repoResp.data);
      if (brdResp) setBrd(brdResp.data);
    } catch {
      toast.error("Failed to load merge proposal.");
      router.push("/merge-workbench");
    } finally {
      setLoading(false);
    }
  }, [proposalId, router]);

  useEffect(() => {
    fetchProposal();
  }, [fetchProposal]);

  const updateItem = useCallback(
    async (
      itemId: string,
      patch: { user_action?: MergeAction | null; notes?: string }
    ) => {
      setSavingItemId(itemId);
      try {
        const { data: updated } = await api.patch<MergeItem>(
          `/merge-proposal/${proposalId}/items/${itemId}`,
          patch
        );
        setProposal((prev) =>
          prev
            ? {
                ...prev,
                items: prev.items.map((i) => (i.id === itemId ? updated : i)),
              }
            : prev
        );
        toast.success("Decision saved.");
      } catch (err: any) {
        toast.error(
          err?.response?.data?.detail || "Failed to save item decision."
        );
      } finally {
        setSavingItemId(null);
      }
    },
    [proposalId]
  );

  const handleActionChange = useCallback(
    (itemId: string, value: string | null) => {
      const action = (value as MergeAction) || null;
      updateItem(itemId, { user_action: action });
    },
    [updateItem]
  );

  const handleNotesBlur = useCallback(
    (itemId: string) => {
      const item = proposal?.items.find((i) => i.id === itemId);
      if (!item) return;
      const newNotes = notesDraft[itemId] ?? "";
      if ((item.notes || "") === newNotes) return;
      updateItem(itemId, { notes: newNotes });
    },
    [proposal, notesDraft, updateItem]
  );

  const blockerIds = useMemo(
    () => new Set(proposal?.blockers || []),
    [proposal]
  );

  const unresolvedBlockers = useMemo(() => {
    if (!proposal) return [] as MergeItem[];
    return proposal.items.filter(
      (item) =>
        blockerIds.has(item.id) &&
        (item.user_action === null ||
          item.user_action === "NEEDS_HUMAN" ||
          item.user_action === "EDIT_NEEDED")
    );
  }, [proposal, blockerIds]);

  const canApply = useMemo(() => {
    if (!proposal) return false;
    if (proposal.status !== "PENDING") return false;
    return unresolvedBlockers.length === 0;
  }, [proposal, unresolvedBlockers]);

  const handleApply = useCallback(async () => {
    if (!proposal) return;
    if (!decidedBy.trim()) {
      toast.error("Please enter your name.");
      return;
    }
    setApplying(true);
    try {
      const { data } = await api.post<MergeApplyResult>(
        `/merge-proposal/${proposalId}/apply`,
        { decided_by: decidedBy.trim() }
      );
      if (data.applied) {
        toast.success(
          `Applied — created v${data.new_version_number ?? "?"}.`
        );
        setApplyOpen(false);
        router.push(`/live-repo/${proposal.repository_id}`);
      } else {
        toast.error(
          data.summary || `Cannot apply — ${data.blockers.length} blocker(s).`
        );
        await fetchProposal();
      }
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to apply proposal.");
    } finally {
      setApplying(false);
    }
  }, [proposal, proposalId, decidedBy, router, fetchProposal]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!proposal) return null;

  return (
    <PageTransition>
      <PipelineContextBar />
      <div className="space-y-8">
        <p className="text-xs text-muted-foreground mb-4">
          Dashboard /{" "}
          <Link href="/merge-workbench" className="hover:underline">
            Merge Workbench
          </Link>{" "}
          / Proposal
        </p>

        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-4">
            <Button
              variant="ghost"
              size="icon-sm"
              render={<Link href="/merge-workbench" />}
            >
              <ArrowLeft className="size-4" />
            </Button>
            <div className="space-y-2">
              <div className="flex items-center gap-3 flex-wrap">
                <GitMerge className="size-6 text-violet-500" />
                <h1 className="text-2xl font-bold tracking-tight">
                  <span className="text-gradient">Merge Proposal</span>
                </h1>
                <Badge
                  variant="outline"
                  className={STATUS_STYLES[proposal.status]}
                >
                  {proposal.status}
                </Badge>
                {unresolvedBlockers.length > 0 && (
                  <Badge
                    variant="outline"
                    className="bg-red-500/10 text-red-600 border-red-500/20 dark:text-red-400"
                  >
                    <AlertTriangle className="size-3" />
                    {unresolvedBlockers.length} blocker
                    {unresolvedBlockers.length !== 1 ? "s" : ""}
                  </Badge>
                )}
              </div>

              <div className="flex items-center gap-4 ml-9 flex-wrap text-sm text-muted-foreground">
                <Link
                  href={`/brds/${proposal.source_brd_id}`}
                  className="inline-flex items-center gap-1.5 hover:text-primary hover:underline"
                  title={proposal.source_brd_id}
                >
                  <FileText className="size-4" />
                  {brd?.filename ?? `BRD ${proposal.source_brd_id.slice(0, 8)}`}
                </Link>
                <Link
                  href={`/live-repo/${proposal.repository_id}`}
                  className="inline-flex items-center gap-1.5 hover:text-primary hover:underline"
                  title={proposal.repository_id}
                >
                  <GitBranch className="size-4" />
                  {repo
                    ? `${repo.name}${repo.product ? ` · ${repo.product}` : ""}${
                        repo.jurisdiction ? ` · ${repo.jurisdiction}` : ""
                      }`
                    : `Repo ${proposal.repository_id.slice(0, 8)}`}
                </Link>
                <span>Base: v{proposal.base_version}</span>
              </div>

              {proposal.summary && (
                <p className="ml-9 text-sm text-muted-foreground">
                  {proposal.summary}
                </p>
              )}
            </div>
          </div>

          <Dialog open={applyOpen} onOpenChange={setApplyOpen}>
            <Button
              variant="default"
              disabled={!canApply}
              title={
                canApply
                  ? "Apply this proposal"
                  : proposal.status !== "PENDING"
                  ? `Already ${proposal.status.toLowerCase()}`
                  : "Resolve all hard blockers first"
              }
              onClick={() => setApplyOpen(true)}
            >
              <Sparkles className="size-4" />
              Apply Merge
            </Button>
            <DialogContent className="sm:max-w-md">
              <DialogHeader>
                <DialogTitle>Apply Merge Proposal</DialogTitle>
                <DialogDescription>
                  Applying creates a new live repository version. Enter your
                  name to record who approved this change.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-1.5 py-2">
                <label className="text-xs font-medium">Decided By</label>
                <Input
                  value={decidedBy}
                  onChange={(e) => setDecidedBy(e.target.value)}
                  placeholder="e.g., jane.doe@example.com"
                />
              </div>
              <DialogFooter>
                <DialogClose render={<Button variant="outline" />}>
                  Cancel
                </DialogClose>
                <Button
                  variant="default"
                  onClick={handleApply}
                  disabled={applying}
                >
                  {applying && (
                    <Loader2 className="mr-2 size-4 animate-spin" />
                  )}
                  Apply
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>

        {/* Counts and Severity Legend */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.05 }}
        >
          <Card className="card-elevated p-4 border-border/40">
            <div className="space-y-3">
              {/* Severity Legend */}
              <div className="flex items-center gap-3 flex-wrap">
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Severity:
                </span>
                <Badge variant="outline" className={SEVERITY_STYLES.HARD}>
                  HARD — blocks apply
                </Badge>
                <Badge variant="outline" className={SEVERITY_STYLES.SOFT}>
                  SOFT — warn
                </Badge>
                <Badge variant="outline" className={SEVERITY_STYLES.INFO}>
                  INFO
                </Badge>
              </div>

              {Object.keys(proposal.counts_by_category).length > 0 && (
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    By category:
                  </span>
                  {Object.entries(proposal.counts_by_category).map(
                    ([cat, count]) => (
                      <Badge key={cat} variant="secondary">
                        {CATEGORY_LABEL[cat] || cat} ({count})
                      </Badge>
                    )
                  )}
                </div>
              )}

              {Object.keys(proposal.counts_by_severity).length > 0 && (
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    By severity:
                  </span>
                  {Object.entries(proposal.counts_by_severity).map(
                    ([sev, count]) => (
                      <Badge
                        key={sev}
                        variant="outline"
                        className={SEVERITY_STYLES[sev] || ""}
                      >
                        {sev}: {count}
                      </Badge>
                    )
                  )}
                </div>
              )}
            </div>
          </Card>
        </motion.div>

        {/* Items */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.1 }}
          className="space-y-4"
        >
          {proposal.items.length === 0 ? (
            <Card className="card-elevated p-12 border-border/40 flex flex-col items-center text-center">
              <CheckCircle className="size-12 text-emerald-500/40" />
              <p className="mt-3 text-sm text-muted-foreground">
                No items in this proposal.
              </p>
            </Card>
          ) : (
            proposal.items.map((item) => {
              const isBlocker = blockerIds.has(item.id);
              const isUnresolvedBlocker =
                isBlocker &&
                (item.user_action === null ||
                  item.user_action === "NEEDS_HUMAN" ||
                  item.user_action === "EDIT_NEEDED");
              return (
                <Card
                  key={item.id}
                  className={`card-elevated border-border/40 p-4 ${
                    isUnresolvedBlocker ? "ring-1 ring-red-500/30" : ""
                  }`}
                >
                  <div className="space-y-3">
                    {/* Header row */}
                    <div className="flex items-start justify-between gap-3 flex-wrap">
                      <div className="flex items-center gap-2 flex-wrap">
                        <Badge variant="secondary" className="font-mono">
                          {CATEGORY_LABEL[item.category] || item.category}
                        </Badge>
                        <Badge
                          variant="outline"
                          className={SEVERITY_STYLES[item.severity]}
                        >
                          {item.severity}
                        </Badge>
                        {item.canonical_key && (
                          <span className="font-mono text-xs text-muted-foreground">
                            {item.canonical_key}
                          </span>
                        )}
                        {item.confidence !== undefined && (
                          <span className="text-xs text-muted-foreground">
                            confidence: {(item.confidence * 100).toFixed(0)}%
                          </span>
                        )}
                      </div>
                      {savingItemId === item.id && (
                        <Loader2 className="size-4 animate-spin text-muted-foreground" />
                      )}
                    </div>

                    {/* Diff */}
                    <DiffBlock item={item} />

                    {/* Rationale */}
                    {item.rationale && (
                      <div className="text-sm text-muted-foreground">
                        <span className="font-semibold text-foreground">
                          Rationale:
                        </span>{" "}
                        {item.rationale}
                      </div>
                    )}

                    {/* Decision */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2 border-t border-border/40">
                      <div className="space-y-1.5">
                        <label className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                          Suggested
                        </label>
                        <div>
                          <Badge variant="outline">
                            {item.suggested_action}
                          </Badge>
                        </div>
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                          Your Decision
                        </label>
                        <Select
                          value={item.user_action ?? ""}
                          onValueChange={(val) =>
                            handleActionChange(item.id, val)
                          }
                        >
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="Pick an action…" />
                          </SelectTrigger>
                          <SelectContent>
                            {ACTION_OPTIONS.map((opt) => (
                              <SelectItem key={opt} value={opt}>
                                {opt}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>

                    {/* Notes */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                        Notes
                      </label>
                      <Input
                        value={notesDraft[item.id] ?? ""}
                        onChange={(e) =>
                          setNotesDraft((prev) => ({
                            ...prev,
                            [item.id]: e.target.value,
                          }))
                        }
                        onBlur={() => handleNotesBlur(item.id)}
                        placeholder="Optional reviewer notes (saves on blur)…"
                      />
                    </div>

                    {/* Status indicators */}
                    {item.user_action && (
                      <div className="flex items-center gap-1.5 text-xs">
                        {item.user_action === "REJECT" ||
                        item.user_action === "DROP" ||
                        item.user_action === "RETIRE" ? (
                          <XCircle className="size-3.5 text-red-500" />
                        ) : item.user_action === "NEEDS_HUMAN" ||
                          item.user_action === "EDIT_NEEDED" ? (
                          <AlertTriangle className="size-3.5 text-amber-500" />
                        ) : (
                          <CheckCircle className="size-3.5 text-emerald-500" />
                        )}
                        <span className="text-muted-foreground">
                          Decision: {item.user_action}
                        </span>
                      </div>
                    )}
                  </div>
                </Card>
              );
            })
          )}
        </motion.div>
      </div>
    </PageTransition>
  );
}
