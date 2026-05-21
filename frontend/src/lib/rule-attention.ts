/**
 * rule-attention — Slice 4 helper that computes a "needs reviewer
 * attention" score for each rule, using ONLY data already exposed on
 * RuleResponse (no backend changes needed).
 *
 * Signals (each adds to the score):
 *   - confidence < 0.7 (extractor was unsure)         → +3
 *   - has_conflicts (overlaps with another rule)      → +4
 *   - subsystem == UNCLASSIFIED (couldn't categorize) → +2
 *   - canonical_key missing or contains "unknown"     → +3
 *   - empty conditions (gate-style or extraction bug) → +1
 *   - empty actions (broken rule)                     → +5
 *
 * The reviewer table sorts by score desc and surfaces the count of
 * rules with score > 0 in a banner ("X rules need attention").
 */
import type { Rule } from "@/lib/types";

export type AttentionReason =
  | "low_confidence"
  | "has_conflicts"
  | "unclassified"
  | "missing_canonical_key"
  | "no_conditions"
  | "no_actions";

const REASON_WEIGHTS: Record<AttentionReason, number> = {
  low_confidence: 3,
  has_conflicts: 4,
  unclassified: 2,
  missing_canonical_key: 3,
  no_conditions: 1,
  no_actions: 5,
};

const REASON_LABELS: Record<AttentionReason, string> = {
  low_confidence: "Low confidence",
  has_conflicts: "Has conflicts",
  unclassified: "Unclassified subsystem",
  missing_canonical_key: "Missing canonical key",
  no_conditions: "No conditions (always-fires)",
  no_actions: "No actions (no-op)",
};

export interface AttentionInfo {
  score: number;
  reasons: AttentionReason[];
  /** Human-readable list, ready to render in a tooltip. */
  labels: string[];
  /** Highest tier: "critical" (score>=5), "warn" (3-4), "info" (1-2),
   *  "ok" (0). Lets the UI pick a single colour without re-computing. */
  tier: "critical" | "warn" | "info" | "ok";
}

export function attentionForRule(rule: Rule): AttentionInfo {
  const reasons: AttentionReason[] = [];
  if (typeof rule.confidence === "number" && rule.confidence < 0.7) {
    reasons.push("low_confidence");
  }
  if (rule.has_conflicts) {
    reasons.push("has_conflicts");
  }
  if (!rule.subsystem || rule.subsystem === "UNCLASSIFIED") {
    reasons.push("unclassified");
  }
  if (
    !rule.canonical_key ||
    rule.canonical_key.includes("unknown") ||
    rule.canonical_key.includes("UNK")
  ) {
    reasons.push("missing_canonical_key");
  }
  if (!rule.conditions || rule.conditions.length === 0) {
    reasons.push("no_conditions");
  }
  if (!rule.actions || rule.actions.length === 0) {
    reasons.push("no_actions");
  }

  const score = reasons.reduce((s, r) => s + REASON_WEIGHTS[r], 0);
  const tier: AttentionInfo["tier"] =
    score >= 5 ? "critical" : score >= 3 ? "warn" : score >= 1 ? "info" : "ok";

  return {
    score,
    reasons,
    labels: reasons.map((r) => REASON_LABELS[r]),
    tier,
  };
}

/** Sort key — higher attention first; ties broken by rule_id ASC so
 *  the order is stable across renders. */
export function compareByAttention(a: Rule, b: Rule): number {
  const sa = attentionForRule(a).score;
  const sb = attentionForRule(b).score;
  if (sa !== sb) return sb - sa;
  return (a.rule_id || "").localeCompare(b.rule_id || "");
}

/** Aggregate count for the banner — how many rules have score > 0. */
export function countRulesNeedingAttention(rules: Rule[]): number {
  return rules.reduce(
    (n, r) => (attentionForRule(r).score > 0 ? n + 1 : n),
    0,
  );
}
