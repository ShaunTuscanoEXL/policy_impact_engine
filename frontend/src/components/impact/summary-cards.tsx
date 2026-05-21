"use client";

import { Card } from "@/components/ui/card";
import {
  Users,
  ArrowDownRight,
  ArrowUpRight,
  type LucideIcon,
} from "lucide-react";
import {
  StaggerContainer,
  StaggerItem,
} from "@/components/page-transition";
import type { ImpactRunSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

interface SummaryCardsProps {
  summary: ImpactRunSummary;
}

interface CardSpec {
  label: string;
  value: string;
  detail: string;
  icon: LucideIcon;
  /** A pair of tailwind classes for the gradient + accent */
  tone: "blue" | "red" | "green" | "violet" | "neutral";
}

const TONE_STYLES: Record<CardSpec["tone"], {
  ring: string;
  iconBg: string;
  iconText: string;
  valueText: string;
  decoration: string;
}> = {
  blue: {
    ring: "from-blue-500/30 via-blue-500/10 to-transparent",
    iconBg: "bg-blue-500/15",
    iconText: "text-blue-600 dark:text-blue-400",
    valueText: "text-blue-700 dark:text-blue-300",
    decoration: "from-blue-500/20 to-blue-500/0",
  },
  red: {
    ring: "from-red-500/30 via-red-500/10 to-transparent",
    iconBg: "bg-red-500/15",
    iconText: "text-red-600 dark:text-red-400",
    valueText: "text-red-700 dark:text-red-300",
    decoration: "from-red-500/20 to-red-500/0",
  },
  green: {
    ring: "from-emerald-500/30 via-emerald-500/10 to-transparent",
    iconBg: "bg-emerald-500/15",
    iconText: "text-emerald-600 dark:text-emerald-400",
    valueText: "text-emerald-700 dark:text-emerald-300",
    decoration: "from-emerald-500/20 to-emerald-500/0",
  },
  violet: {
    ring: "from-violet-500/30 via-violet-500/10 to-transparent",
    iconBg: "bg-violet-500/15",
    iconText: "text-violet-600 dark:text-violet-400",
    valueText: "text-violet-700 dark:text-violet-300",
    decoration: "from-violet-500/20 to-violet-500/0",
  },
  neutral: {
    ring: "from-slate-500/20 via-slate-500/10 to-transparent",
    iconBg: "bg-slate-500/15",
    iconText: "text-slate-600 dark:text-slate-400",
    valueText: "text-slate-700 dark:text-slate-300",
    decoration: "from-slate-500/15 to-slate-500/0",
  },
};

export function SummaryCards({ summary }: SummaryCardsProps) {
  const flips = summary.decision_flips ?? {};
  const totalFlips = Object.values(flips).reduce((a, n) => a + n, 0);
  const totalLoans = summary.total_loans ?? 0;
  const affectedPct = totalLoans > 0 ? (totalFlips / totalLoans) * 100 : 0;

  // BREAK OUT each decision label rather than bundling APPROVED+FLAGGED
  // together — the previous "Net Approved" tile mixed FLAGGED loans
  // (manual review, NOT funded) with truly APPROVED loans, which hid
  // catastrophic rule misconfigurations like 0 actual approvals.
  const baseRej = summary.decision_distribution.base?.REJECTED ?? 0;
  const candRej = summary.decision_distribution.candidate?.REJECTED ?? 0;
  const rejDelta = candRej - baseRej;

  const baseAppr = summary.decision_distribution.base?.APPROVED ?? 0;
  const candAppr = summary.decision_distribution.candidate?.APPROVED ?? 0;
  const apprDelta = candAppr - baseAppr;

  const baseFlag = summary.decision_distribution.base?.FLAGGED ?? 0;
  const candFlag = summary.decision_distribution.candidate?.FLAGGED ?? 0;
  const flagDelta = candFlag - baseFlag;

  const cards: CardSpec[] = [
    {
      label: "Affected Loans",
      value: totalFlips.toLocaleString(),
      detail: `${affectedPct.toFixed(1)}% of ${totalLoans.toLocaleString()} loans`,
      icon: Users,
      tone: "blue",
    },
    {
      label: "Net Approved",
      value: `${apprDelta >= 0 ? "+" : ""}${apprDelta.toLocaleString()}`,
      detail:
        candAppr === 0 && baseAppr === 0
          ? "⚠ 0 loans approved — every loan hit a FLAG/REJECT rule"
          : `${baseAppr.toLocaleString()} → ${candAppr.toLocaleString()} (${totalLoans > 0 ? ((candAppr / totalLoans) * 100).toFixed(1) : "0"}% rate)`,
      icon: apprDelta >= 0 ? ArrowUpRight : ArrowDownRight,
      tone:
        candAppr === 0 && baseAppr === 0
          ? "red"
          : apprDelta > 0
            ? "green"
            : apprDelta < 0
              ? "red"
              : "neutral",
    },
    {
      label: "Net Flagged",
      value: `${flagDelta >= 0 ? "+" : ""}${flagDelta.toLocaleString()}`,
      detail: `${baseFlag.toLocaleString()} → ${candFlag.toLocaleString()} · queued for manual review`,
      icon: flagDelta >= 0 ? ArrowUpRight : ArrowDownRight,
      tone:
        flagDelta > 0 ? "violet" : flagDelta < 0 ? "neutral" : "neutral",
    },
    {
      label: "Net Rejected",
      value: `${rejDelta >= 0 ? "+" : ""}${rejDelta.toLocaleString()}`,
      detail: `${baseRej.toLocaleString()} → ${candRej.toLocaleString()}`,
      icon: rejDelta >= 0 ? ArrowDownRight : ArrowUpRight,
      tone: rejDelta > 0 ? "red" : rejDelta < 0 ? "green" : "neutral",
    },
  ];

  return (
    <StaggerContainer className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => {
        const tone = TONE_STYLES[card.tone];
        const Icon = card.icon;
        return (
          <StaggerItem key={card.label}>
            <Card
              className={cn(
                "card-elevated relative overflow-hidden border-border/50 p-5 transition-all duration-300",
                "hover:border-border hover:shadow-lg hover:-translate-y-0.5"
              )}
            >
              {/* Decorative gradient blob in the corner */}
              <div
                className={cn(
                  "pointer-events-none absolute -right-12 -top-12 h-32 w-32 rounded-full bg-gradient-to-br opacity-60 blur-2xl",
                  tone.decoration
                )}
                aria-hidden
              />
              <div className="relative space-y-3">
                <div className="flex items-start justify-between">
                  <div className="space-y-0.5">
                    <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      {card.label}
                    </p>
                  </div>
                  <div
                    className={cn(
                      "rounded-lg p-2 ring-1 ring-inset ring-border/40",
                      tone.iconBg
                    )}
                  >
                    <Icon className={cn("size-4", tone.iconText)} />
                  </div>
                </div>
                <div>
                  <div
                    className={cn(
                      "font-mono text-3xl font-bold leading-none tracking-tight",
                      tone.valueText
                    )}
                  >
                    {card.value}
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">
                    {card.detail}
                  </p>
                </div>
                {/* Bottom accent line */}
                <div
                  className={cn(
                    "absolute -bottom-px left-4 right-4 h-px bg-gradient-to-r",
                    tone.ring
                  )}
                  aria-hidden
                />
              </div>
            </Card>
          </StaggerItem>
        );
      })}
    </StaggerContainer>
  );
}
