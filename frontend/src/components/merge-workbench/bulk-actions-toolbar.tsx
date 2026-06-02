"use client";

/**
 * BulkActionsToolbar — Slice 6 quick-action buttons for the merge
 * workbench. Lets a reviewer accept/reject whole groups of items in
 * one shot instead of clicking 50 dropdowns.
 *
 * Buttons are filter-driven; each calls the backend's
 * /merge-proposal/{id}/batch-update endpoint with the right
 * severity/category combo.
 *
 * Per-item user_actions already set are SKIPPED unless the reviewer
 * holds Shift to opt into overwrite_existing.
 */
import { useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  CheckCircle,
  Loader2,
  Trash2,
  Layers,
  XCircle,
  Sparkles,
} from "lucide-react";

interface Props {
  proposalId: string;
  /** Counts driven from the proposal so the toolbar can hide buttons
   *  whose target group is empty. */
  countsByCategory?: Record<string, number>;
  countsBySeverity?: Record<string, number>;
  /** Re-fetch the proposal after a successful batch update. */
  onApplied: () => void;
  /** Disable while the user has the workbench in read-only state. */
  disabled?: boolean;
}

type BatchPreset = {
  key: string;
  label: string;
  helper: string;
  user_action: string;
  severity?: string;
  category?: string;
  Icon: typeof CheckCircle;
  /** Tailwind color hint for the chip. */
  tone: "emerald" | "rose" | "slate" | "violet";
  /** Counts source: returns the eligible count, used both to show
   *  the chip count and to hide the chip when 0. */
  countFor: (cat?: Record<string, number>, sev?: Record<string, number>) => number;
};

const PRESETS: BatchPreset[] = [
  {
    key: "accept_info",
    label: "Accept all INFO",
    helper: "Accepts every informational item without changing HARD/SOFT items.",
    user_action: "ACCEPT",
    severity: "INFO",
    Icon: CheckCircle,
    tone: "emerald",
    countFor: (_c, sev) => sev?.INFO ?? 0,
  },
  {
    key: "accept_new",
    label: "Accept all NEW_RULE",
    helper: "Accepts every brand-new rule introduced by this BRD.",
    user_action: "ACCEPT",
    category: "NEW_RULE",
    Icon: Sparkles,
    tone: "emerald",
    countFor: (cat) => cat?.NEW_RULE ?? 0,
  },
  {
    key: "drop_dupes",
    label: "Drop EXACT_DUPLICATEs",
    helper: "Discards items the engine already recognised as identical to live.",
    user_action: "DROP",
    category: "EXACT_DUPLICATE",
    Icon: Trash2,
    tone: "slate",
    countFor: (cat) => cat?.EXACT_DUPLICATE ?? 0,
  },
  {
    key: "retire_removed",
    label: "Retire all REMOVED_RULEs",
    helper: "Marks live rules with no incoming counterpart as retired.",
    user_action: "RETIRE",
    category: "REMOVED_RULE",
    Icon: XCircle,
    tone: "rose",
    countFor: (cat) => cat?.REMOVED_RULE ?? 0,
  },
  {
    key: "supersede_tier",
    label: "Supersede TIERED_REPLACEMENTs",
    helper: "Replaces a live tier set entirely with the incoming tier set.",
    user_action: "SUPERSEDE_GROUP",
    category: "TIERED_REPLACEMENT",
    Icon: Layers,
    tone: "violet",
    countFor: (cat) => cat?.TIERED_REPLACEMENT ?? 0,
  },
];

const TONE_CLASSES = {
  emerald:
    "bg-emerald-500/10 text-emerald-700 ring-emerald-500/30 hover:bg-emerald-500/20 dark:text-emerald-300",
  rose: "bg-rose-500/10 text-rose-700 ring-rose-500/30 hover:bg-rose-500/20 dark:text-rose-300",
  slate:
    "bg-slate-500/10 text-slate-700 ring-slate-500/30 hover:bg-slate-500/20 dark:text-slate-300",
  violet:
    "bg-violet-500/10 text-violet-700 ring-violet-500/30 hover:bg-violet-500/20 dark:text-violet-300",
};

export function BulkActionsToolbar({
  proposalId,
  countsByCategory,
  countsBySeverity,
  onApplied,
  disabled,
}: Props) {
  const [busyKey, setBusyKey] = useState<string | null>(null);

  const visiblePresets = PRESETS.filter(
    (p) => p.countFor(countsByCategory, countsBySeverity) > 0,
  );

  if (visiblePresets.length === 0) {
    return null;
  }

  const apply = async (preset: BatchPreset, overwrite: boolean) => {
    setBusyKey(preset.key);
    try {
      const { data } = await api.post(
        `/merge-proposal/${proposalId}/batch-update`,
        {
          user_action: preset.user_action,
          severity: preset.severity ?? null,
          category: preset.category ?? null,
          overwrite_existing: overwrite,
        },
      );
      const skipped = data.skipped_existing ?? 0;
      const updated = data.updated ?? 0;
      if (updated === 0) {
        toast.info(
          skipped > 0
            ? `${skipped} item${skipped !== 1 ? "s" : ""} already had a decision — hold Shift to overwrite.`
            : "No items matched.",
        );
      } else {
        toast.success(
          `${preset.label}: ${updated} updated${
            skipped > 0 ? ` · ${skipped} skipped (already decided)` : ""
          }.`,
        );
      }
      onApplied();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Bulk update failed.");
    } finally {
      setBusyKey(null);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border/40 bg-muted/20 p-3">
      <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        <Layers className="size-3.5" />
        Bulk actions
      </div>
      {visiblePresets.map((preset) => {
        const count = preset.countFor(countsByCategory, countsBySeverity);
        const busy = busyKey === preset.key;
        return (
          <Button
            key={preset.key}
            variant="ghost"
            size="sm"
            disabled={disabled || busy}
            onClick={(e) => apply(preset, e.shiftKey)}
            title={`${preset.helper}\n\nHold Shift to also overwrite items that already have a decision.`}
            className={`gap-1.5 ring-1 ring-inset ${TONE_CLASSES[preset.tone]}`}
          >
            {busy ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <preset.Icon className="size-3.5" />
            )}
            {preset.label}
            <span className="rounded-full bg-background/60 px-1.5 text-[10px] font-mono">
              {count}
            </span>
          </Button>
        );
      })}
      <p className="ml-auto text-[10px] italic text-muted-foreground">
        Hold <kbd className="rounded bg-muted px-1">Shift</kbd> to overwrite
        items that already have a decision.
      </p>
    </div>
  );
}
