"use client";

/**
 * BusinessImpactCard — translates the raw impact-run summary into the
 * language a policy/credit-team viewer thinks in:
 *
 *   "Approval rate: 76.2% → 71.4% (−4.8 pts on 100,000 loans)"
 *   "5,210 fewer loans funded (mostly NEAR_PRIME)"
 *   "Projected exposure change: −$132M"
 *
 * The card is meant to sit ABOVE the developer-view distribution +
 * flip charts — same data, different audience. When the run hasn't
 * produced a `business_summary` block yet (legacy run before Slice 2
 * landed), the card silently no-ops so it doesn't break old pages.
 */
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import {
  TrendingDown,
  TrendingUp,
  Activity,
  DollarSign,
  Users,
  Target,
  AlertTriangle,
} from "lucide-react";
import type { BusinessImpactSummary, ImpactRunSummary } from "@/lib/types";

interface Props {
  summary: ImpactRunSummary;
}

function formatPct(rate: number): string {
  return `${(rate * 100).toFixed(1)}%`;
}

function formatPctDelta(delta: number): string {
  const pts = delta * 100;
  const sign = pts > 0 ? "+" : pts < 0 ? "−" : "±";
  return `${sign}${Math.abs(pts).toFixed(1)} pts`;
}

function formatUsd(amount: number): string {
  const abs = Math.abs(amount);
  let value: string;
  if (abs >= 1_000_000_000) {
    value = `$${(abs / 1_000_000_000).toFixed(2)}B`;
  } else if (abs >= 1_000_000) {
    value = `$${(abs / 1_000_000).toFixed(2)}M`;
  } else if (abs >= 1_000) {
    value = `$${(abs / 1_000).toFixed(1)}K`;
  } else {
    value = `$${abs.toFixed(0)}`;
  }
  return amount < 0 ? `−${value}` : value;
}

function formatCount(n: number): string {
  return n.toLocaleString("en-US");
}

function deltaTone(delta: number): {
  bg: string;
  text: string;
  ring: string;
  Icon: typeof TrendingUp;
  label: string;
} {
  if (delta < 0) {
    return {
      bg: "bg-rose-500/10",
      text: "text-rose-700 dark:text-rose-300",
      ring: "ring-rose-500/30",
      Icon: TrendingDown,
      label: "Tighter",
    };
  }
  if (delta > 0) {
    return {
      bg: "bg-emerald-500/10",
      text: "text-emerald-700 dark:text-emerald-300",
      ring: "ring-emerald-500/30",
      Icon: TrendingUp,
      label: "Looser",
    };
  }
  return {
    bg: "bg-slate-500/10",
    text: "text-slate-700 dark:text-slate-300",
    ring: "ring-slate-500/30",
    Icon: Activity,
    label: "Unchanged",
  };
}

function buildHeadline(bs: BusinessImpactSummary, total: number): string {
  // Smoke alarm: if the candidate (or both sides) approve zero loans,
  // the rules are misconfigured — units mismatch in a scoring rule, an
  // overly loose FLAG condition, an off-by-one threshold, etc. Surface
  // it instead of saying "no material change" (which technically would
  // be true when base AND candidate both produce zero).
  if (bs.candidate_approval_rate === 0 && bs.base_approval_rate === 0) {
    return `Neither version approves any loan in this corpus — every loan hits a FLAG/REJECT rule. Likely a misconfigured rule (units mismatch in a scoring band, an overly loose FLAG condition, or a threshold typo). Inspect the "Top Subsystem Driver" + check rule-attention warnings.`;
  }
  if (bs.candidate_approval_rate === 0) {
    return `Candidate approves 0 loans (was ${formatPct(bs.base_approval_rate)} on baseline). The new version's gates are catching every applicant — review FLAG/REJECT rules added in this version.`;
  }

  const pts = Math.abs(bs.approval_rate_delta * 100);
  if (pts < 0.05 && Math.abs(bs.net_funded_loans_change) === 0) {
    return `No material change vs the baseline across ${formatCount(total)} loans.`;
  }
  const direction =
    bs.approval_rate_delta < 0 ? "tighter" : "looser";
  const segHint = bs.top_changed_segment
    ? ` (mostly ${bs.top_changed_segment.replaceAll("_", " ")})`
    : "";
  if (bs.net_funded_loans_change < 0) {
    return `If you ship this, ~${formatCount(Math.abs(bs.net_funded_loans_change))} fewer loans funded${segHint} — policy is ${direction} by ${pts.toFixed(1)} pts.`;
  }
  if (bs.net_funded_loans_change > 0) {
    return `If you ship this, ~${formatCount(bs.net_funded_loans_change)} more loans funded${segHint} — policy is ${direction} by ${pts.toFixed(1)} pts.`;
  }
  return `Approval rate moves ${formatPctDelta(bs.approval_rate_delta)}${segHint}, but the net loan count is unchanged (offset gains/losses).`;
}

export function BusinessImpactCard({ summary }: Props) {
  const bs = summary.business_summary;
  if (!bs) return null;

  // Treat zero-approvals as a critical alarm regardless of delta.
  const isZeroApproval =
    bs.candidate_approval_rate === 0 && bs.base_approval_rate === 0;
  const tone = isZeroApproval
    ? {
        bg: "bg-rose-500/15",
        text: "text-rose-700 dark:text-rose-300",
        ring: "ring-rose-500/40",
        Icon: AlertTriangle,
        label: "Misconfigured",
      }
    : deltaTone(bs.approval_rate_delta);
  const exposureTone = deltaTone(bs.net_exposure_change_usd);
  const headline = buildHeadline(bs, summary.total_loans);

  // Top 3 segments by absolute change for the segment table
  const segmentRows = Object.entries(summary.by_segment || {})
    .map(([seg, info]) => ({ seg, ...info }))
    .sort(
      (a, b) =>
        Math.abs(b.approval_rate_change) - Math.abs(a.approval_rate_change),
    )
    .slice(0, 6);

  return (
    <Card className="card-elevated border-border/50">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <span className="rounded-md bg-blue-500/10 p-1.5 ring-1 ring-inset ring-blue-500/20">
            <Target className="size-4 text-blue-600 dark:text-blue-400" />
          </span>
          Business Impact Summary
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* Plain-English headline — the only line a busy stakeholder
            will read on the way to standup. */}
        <div
          className={cn(
            "rounded-lg p-3.5 text-sm font-medium ring-1 ring-inset",
            tone.bg,
            tone.text,
            tone.ring,
          )}
        >
          <div className="flex items-start gap-2">
            <tone.Icon className="mt-0.5 size-4 shrink-0" />
            <p className="leading-snug">{headline}</p>
          </div>
        </div>

        {/* Hero metrics row */}
        <div className="grid gap-3 sm:grid-cols-4">
          <div className="rounded-lg border border-border/40 p-3">
            <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              <Activity className="size-3" /> Approval rate
            </div>
            <div className="mt-1 font-mono text-xl font-bold">
              {formatPct(bs.candidate_approval_rate)}
            </div>
            <div className={cn("text-[11px] font-medium", tone.text)}>
              from {formatPct(bs.base_approval_rate)} ·{" "}
              {formatPctDelta(bs.approval_rate_delta)}
            </div>
          </div>

          <div className="rounded-lg border border-border/40 p-3">
            <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              <Users className="size-3" /> Net loans funded
            </div>
            <div
              className={cn(
                "mt-1 font-mono text-xl font-bold",
                bs.net_funded_loans_change < 0
                  ? "text-rose-700 dark:text-rose-300"
                  : bs.net_funded_loans_change > 0
                    ? "text-emerald-700 dark:text-emerald-300"
                    : "text-foreground",
              )}
            >
              {bs.net_funded_loans_change > 0 ? "+" : ""}
              {formatCount(bs.net_funded_loans_change)}
            </div>
            <div className="text-[11px] text-muted-foreground">
              −{formatCount(bs.loans_newly_denied)} denied · +
              {formatCount(bs.loans_newly_approved)} approved
            </div>
          </div>

          <div className="rounded-lg border border-border/40 p-3">
            <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              <DollarSign className="size-3" /> Net exposure change
            </div>
            <div
              className={cn(
                "mt-1 font-mono text-xl font-bold",
                exposureTone.text,
              )}
            >
              {formatUsd(bs.net_exposure_change_usd)}
            </div>
            <div className="text-[11px] text-muted-foreground">
              −{formatUsd(bs.exposure_change_loss_usd).replace("−", "")} lost ·
              +{formatUsd(bs.exposure_change_gain_usd).replace("−", "")} gained
            </div>
          </div>

          <div className="rounded-lg border border-border/40 p-3">
            <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              <Target className="size-3" /> Top affected segment
            </div>
            <div className="mt-1 font-mono text-xl font-bold">
              {bs.top_changed_segment
                ? bs.top_changed_segment.replaceAll("_", " ")
                : "—"}
            </div>
            {bs.top_changed_segment &&
              summary.by_segment?.[bs.top_changed_segment] && (
                <div className="text-[11px] text-muted-foreground">
                  {formatPctDelta(
                    summary.by_segment[bs.top_changed_segment]
                      .approval_rate_change,
                  )}{" "}
                  approval ·{" "}
                  {formatCount(
                    summary.by_segment[bs.top_changed_segment].loans,
                  )}{" "}
                  loans
                </div>
              )}
          </div>
        </div>

        {/* Per-segment breakdown */}
        {segmentRows.length > 0 && (
          <div className="overflow-hidden rounded-lg border border-border/40">
            <div className="grid grid-cols-12 gap-2 border-b border-border/40 bg-muted/30 px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              <div className="col-span-3">Segment</div>
              <div className="col-span-2 text-right">Loans</div>
              <div className="col-span-2 text-right">Approval (base)</div>
              <div className="col-span-2 text-right">Approval (cand.)</div>
              <div className="col-span-1 text-right">Δ</div>
              <div className="col-span-2 text-right">Funded Δ</div>
            </div>
            {segmentRows.map(
              ({ seg, loans, base_approval_rate, candidate_approval_rate, approval_rate_change, funded_amount_delta_usd }) => {
                const rowTone = deltaTone(approval_rate_change);
                return (
                  <div
                    key={seg}
                    className="grid grid-cols-12 gap-2 border-b border-border/30 px-3 py-2 text-xs last:border-0 hover:bg-muted/20"
                  >
                    <div className="col-span-3 font-medium">
                      {seg.replaceAll("_", " ")}
                    </div>
                    <div className="col-span-2 text-right font-mono text-muted-foreground">
                      {formatCount(loans)}
                    </div>
                    <div className="col-span-2 text-right font-mono">
                      {formatPct(base_approval_rate)}
                    </div>
                    <div className="col-span-2 text-right font-mono">
                      {formatPct(candidate_approval_rate)}
                    </div>
                    <div
                      className={cn(
                        "col-span-1 text-right font-mono font-semibold",
                        rowTone.text,
                      )}
                    >
                      {formatPctDelta(approval_rate_change)}
                    </div>
                    <div
                      className={cn(
                        "col-span-2 text-right font-mono",
                        (funded_amount_delta_usd ?? 0) < 0
                          ? "text-rose-700 dark:text-rose-300"
                          : (funded_amount_delta_usd ?? 0) > 0
                            ? "text-emerald-700 dark:text-emerald-300"
                            : "text-muted-foreground",
                      )}
                    >
                      {formatUsd(funded_amount_delta_usd ?? 0)}
                    </div>
                  </div>
                );
              },
            )}
          </div>
        )}

        <p className="text-[10px] italic text-muted-foreground">
          Funded $ counts only APPROVED decisions; FLAGGED loans are queued
          for manual review and excluded from auto-funded exposure totals.
        </p>
      </CardContent>
    </Card>
  );
}
