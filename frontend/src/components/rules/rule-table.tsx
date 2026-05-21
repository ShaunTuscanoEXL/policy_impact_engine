"use client";

import { useMemo, useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  ChevronDown,
  ChevronRight,
  Edit,
  Trash2,
  AlertTriangle,
  Sparkles,
  Filter,
} from "lucide-react";
import type { Rule, Condition, Action } from "@/lib/types";
import {
  attentionForRule,
  compareByAttention,
  countRulesNeedingAttention,
  type AttentionInfo,
} from "@/lib/rule-attention";
import { cn } from "@/lib/utils";
import { FieldHelp } from "@/components/rules/field-help";

interface RuleTableProps {
  rules: Rule[];
  onEdit: (rule: Rule) => void;
  onDelete: (ruleId: string) => void;
}

type SortMode = "attention" | "id";
type FilterMode = "all" | "needs_attention";

const RULE_TYPE_COLORS: Record<string, string> = {
  ELIGIBILITY: "bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300",
  PRICING: "bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300",
  CAP: "bg-purple-100 text-purple-800 dark:bg-purple-900/50 dark:text-purple-300",
  THRESHOLD: "bg-orange-100 text-orange-800 dark:bg-orange-900/50 dark:text-orange-300",
  SCORING: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900/50 dark:text-cyan-300",
};

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color =
    pct >= 80
      ? "bg-green-500"
      : pct >= 60
      ? "bg-yellow-500"
      : "bg-red-500";

  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-16 rounded-full bg-muted">
        <div
          className={`h-2 rounded-full ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-muted-foreground">{pct}%</span>
    </div>
  );
}

function formatCondition(cond: Condition) {
  const val =
    typeof cond.value === "object"
      ? JSON.stringify(cond.value)
      : String(cond.value);
  return `${cond.field} ${cond.operator} ${val}`;
}

function formatAction(action: Action) {
  if (action.action_type === "REJECT") {
    return `REJECT ${action.target_field || "application"}`;
  }
  const val =
    typeof action.value === "object"
      ? JSON.stringify(action.value)
      : String(action.value ?? "");
  if (action.action_type === "SET") {
    return `SET ${action.target_field} = ${val}`;
  }
  if (action.action_type === "ADJUST") {
    return `ADJUST ${action.target_field} by ${val}`;
  }
  if (action.action_type === "FLAG") {
    return `FLAG ${action.target_field}${val ? `: ${val}` : ""}`;
  }
  return `${action.action_type} ${action.target_field} ${val}`;
}

const ACTION_TYPE_COLORS: Record<string, string> = {
  SET: "text-blue-600 dark:text-blue-400",
  REJECT: "text-red-600 dark:text-red-400",
  ADJUST: "text-orange-600 dark:text-orange-400",
  FLAG: "text-yellow-600 dark:text-yellow-400",
};

export function RuleTable({ rules, onEdit, onDelete }: RuleTableProps) {
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  // Slice 4: prioritization controls — default to "attention" sort so
  // the most-suspect rules surface at the top, and a filter that
  // hides the clean ones once the reviewer wants to focus.
  const [sortMode, setSortMode] = useState<SortMode>("attention");
  const [filterMode, setFilterMode] = useState<FilterMode>("all");

  const attentionCount = useMemo(
    () => countRulesNeedingAttention(rules),
    [rules],
  );

  const visibleRules = useMemo(() => {
    let arr = rules;
    if (filterMode === "needs_attention") {
      arr = arr.filter((r) => attentionForRule(r).score > 0);
    }
    if (sortMode === "attention") {
      arr = [...arr].sort(compareByAttention);
    } else {
      arr = [...arr].sort((a, b) => (a.rule_id || "").localeCompare(b.rule_id || ""));
    }
    return arr;
  }, [rules, sortMode, filterMode]);

  const toggleRow = (id: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleDelete = (ruleId: string) => {
    if (deleteConfirm === ruleId) {
      onDelete(ruleId);
      setDeleteConfirm(null);
    } else {
      setDeleteConfirm(ruleId);
    }
  };

  if (rules.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
        <p className="text-sm">No rules in this rule set yet.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Slice 4: prioritization controls + attention banner */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-1">
        <div className="flex items-center gap-2">
          {attentionCount > 0 ? (
            <button
              type="button"
              onClick={() =>
                setFilterMode((m) =>
                  m === "needs_attention" ? "all" : "needs_attention",
                )
              }
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wider ring-1 ring-inset transition",
                filterMode === "needs_attention"
                  ? "bg-amber-500/20 text-amber-800 ring-amber-500/40 dark:text-amber-200"
                  : "bg-amber-500/10 text-amber-700 ring-amber-500/30 hover:bg-amber-500/20 dark:text-amber-300",
              )}
              title={
                filterMode === "needs_attention"
                  ? "Show all rules"
                  : `Show only the ${attentionCount} rule${attentionCount !== 1 ? "s" : ""} flagged for review`
              }
            >
              <AlertTriangle className="size-3.5" />
              {attentionCount} rule{attentionCount !== 1 ? "s" : ""} need
              attention
              {filterMode === "needs_attention" && " (showing only these)"}
            </button>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-emerald-700 ring-1 ring-inset ring-emerald-500/30 dark:text-emerald-300">
              <Sparkles className="size-3.5" />
              All rules look healthy
            </span>
          )}
        </div>
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <Filter className="size-3.5" />
          Sort:
          <button
            type="button"
            onClick={() => setSortMode("attention")}
            className={cn(
              "rounded px-2 py-0.5 transition",
              sortMode === "attention"
                ? "bg-foreground/10 font-semibold text-foreground"
                : "hover:bg-muted",
            )}
          >
            Attention
          </button>
          <button
            type="button"
            onClick={() => setSortMode("id")}
            className={cn(
              "rounded px-2 py-0.5 transition",
              sortMode === "id"
                ? "bg-foreground/10 font-semibold text-foreground"
                : "hover:bg-muted",
            )}
          >
            Rule ID
          </button>
        </div>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-8 text-xs font-semibold uppercase tracking-wider border-b-2 border-indigo-500/20" />
            <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-indigo-500/20">Attention</TableHead>
            <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-indigo-500/20">Rule ID</TableHead>
            <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-indigo-500/20">Name</TableHead>
            <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-indigo-500/20">Type</TableHead>
            <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-indigo-500/20">Confidence</TableHead>
            <TableHead className="text-center text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-indigo-500/20">Priority</TableHead>
            <TableHead className="text-center text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-indigo-500/20">Conflicts</TableHead>
            <TableHead className="text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-indigo-500/20">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {visibleRules.map((rule) => {
            const isExpanded = expandedRows.has(rule.id);
            return (
              <ExpandableRuleRow
                key={rule.id}
                rule={rule}
                attention={attentionForRule(rule)}
                isExpanded={isExpanded}
                onToggle={() => toggleRow(rule.id)}
                onEdit={() => onEdit(rule)}
                onDelete={() => handleDelete(rule.id)}
                isDeleteConfirm={deleteConfirm === rule.id}
                onCancelDelete={() => setDeleteConfirm(null)}
              />
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

function AttentionPill({ attention }: { attention: AttentionInfo }) {
  if (attention.tier === "ok") {
    return <span className="text-xs text-muted-foreground">—</span>;
  }
  const tone =
    attention.tier === "critical"
      ? "bg-rose-500/15 text-rose-700 ring-rose-500/40 dark:text-rose-300"
      : attention.tier === "warn"
        ? "bg-amber-500/15 text-amber-700 ring-amber-500/40 dark:text-amber-300"
        : "bg-blue-500/15 text-blue-700 ring-blue-500/30 dark:text-blue-300";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ring-1 ring-inset",
        tone,
      )}
      title={attention.labels.join(" · ")}
    >
      <AlertTriangle className="size-3" />
      {attention.tier === "critical"
        ? "Critical"
        : attention.tier === "warn"
          ? "Review"
          : "Check"}
    </span>
  );
}

interface ExpandableRuleRowProps {
  rule: Rule;
  attention: AttentionInfo;
  isExpanded: boolean;
  onToggle: () => void;
  onEdit: () => void;
  onDelete: () => void;
  isDeleteConfirm: boolean;
  onCancelDelete: () => void;
}

function ExpandableRuleRow({
  rule,
  attention,
  isExpanded,
  onToggle,
  onEdit,
  onDelete,
  isDeleteConfirm,
  onCancelDelete,
}: ExpandableRuleRowProps) {
  const typeClass =
    RULE_TYPE_COLORS[rule.rule_type] || "bg-gray-100 text-gray-800";

  // Highlight the row's left edge when attention is non-zero so the
  // reviewer can scan the table for hot spots without reading every cell.
  const rowAccent =
    attention.tier === "critical"
      ? "border-l-4 border-l-rose-500"
      : attention.tier === "warn"
        ? "border-l-4 border-l-amber-500"
        : attention.tier === "info"
          ? "border-l-4 border-l-blue-400"
          : "border-l-4 border-l-transparent";

  return (
    <>
      <TableRow
        className={cn(
          "cursor-pointer hover:bg-muted/50 transition-colors",
          rowAccent,
        )}
        onClick={onToggle}
      >
        <TableCell>
          {isExpanded ? (
            <ChevronDown className="size-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="size-4 text-muted-foreground" />
          )}
        </TableCell>
        <TableCell>
          <AttentionPill attention={attention} />
        </TableCell>
        <TableCell className="font-mono text-xs">{rule.rule_id}</TableCell>
        <TableCell className="font-medium">{rule.rule_name}</TableCell>
        <TableCell>
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${typeClass}`}
          >
            {rule.rule_type}
          </span>
        </TableCell>
        <TableCell>
          <ConfidenceBar value={rule.confidence} />
        </TableCell>
        <TableCell className="text-center">{rule.priority}</TableCell>
        <TableCell className="text-center">
          {rule.has_conflicts ? (
            <span className="inline-flex items-center gap-1 text-red-500">
              <AlertTriangle className="size-3.5" />
            </span>
          ) : (
            <span className="text-xs text-muted-foreground">-</span>
          )}
        </TableCell>
        <TableCell className="text-right">
          <div
            className="flex items-center justify-end gap-1"
            onClick={(e) => e.stopPropagation()}
          >
            <Button variant="ghost" size="sm" onClick={onEdit}>
              <Edit className="size-3.5" />
            </Button>
            {isDeleteConfirm ? (
              <div className="flex items-center gap-1">
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={onDelete}
                >
                  Confirm
                </Button>
                <Button variant="ghost" size="sm" onClick={onCancelDelete}>
                  Cancel
                </Button>
              </div>
            ) : (
              <Button variant="ghost" size="sm" onClick={onDelete}>
                <Trash2 className="size-3.5 text-destructive" />
              </Button>
            )}
          </div>
        </TableCell>
      </TableRow>

      {isExpanded && (
        <TableRow>
          <TableCell colSpan={9} className="bg-muted/30 p-0">
            <div className="p-4 pl-12 space-y-4">
              {/* Description */}
              {rule.description && (
                <div>
                  <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    Description
                  </p>
                  <p className="mt-1 text-sm">{rule.description}</p>
                </div>
              )}

              {/* Conditions */}
              <div>
                <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Conditions
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  {rule.conditions.length === 0 ? (
                    <span className="text-xs text-muted-foreground italic">
                      No conditions defined
                    </span>
                  ) : (
                    rule.conditions.map((cond, i) => {
                      const valStr =
                        typeof cond.value === "object"
                          ? JSON.stringify(cond.value)
                          : String(cond.value);
                      return (
                        <span key={i} className="flex items-center gap-1.5">
                          {i > 0 && (
                            <Badge
                              variant="secondary"
                              className="text-[10px] px-1.5"
                            >
                              {cond.logic || "AND"}
                            </Badge>
                          )}
                          {/* Slice 5: hover the field name to see the
                              plain-English glossary entry. */}
                          <code className="rounded bg-muted px-2 py-0.5 text-xs">
                            <FieldHelp name={cond.field}>{cond.field}</FieldHelp>{" "}
                            {cond.operator} {valStr}
                          </code>
                        </span>
                      );
                    })
                  )}
                </div>
              </div>

              <Separator />

              {/* Actions */}
              <div>
                <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Actions
                </p>
                <div className="mt-2 space-y-1">
                  {rule.actions.length === 0 ? (
                    <span className="text-xs text-muted-foreground italic">
                      No actions defined
                    </span>
                  ) : (
                    rule.actions.map((action, i) => {
                      const valStr =
                        typeof action.value === "object"
                          ? JSON.stringify(action.value)
                          : String(action.value ?? "");
                      return (
                        <div key={i} className="flex items-center gap-2">
                          <code
                            className={`rounded bg-muted px-2 py-0.5 text-xs font-medium ${
                              ACTION_TYPE_COLORS[action.action_type] || ""
                            }`}
                          >
                            {action.action_type}{" "}
                            {action.target_field && (
                              <FieldHelp name={action.target_field}>
                                {action.target_field}
                              </FieldHelp>
                            )}
                            {valStr ? ` = ${valStr}` : ""}
                          </code>
                          {action.description && (
                            <span className="text-xs text-muted-foreground">
                              — {action.description}
                            </span>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>
              </div>

              {/* Source Section */}
              {rule.source_section && (
                <>
                  <Separator />
                  <div>
                    <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Source Reference
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {rule.source_section}
                    </p>
                  </div>
                </>
              )}

              {/* Slice 7: governance metadata */}
              {(rule.policy_intent || rule.regulatory_citation) && (
                <>
                  <Separator />
                  <div className="space-y-2">
                    {rule.policy_intent && (
                      <div>
                        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                          Policy Intent
                        </p>
                        <p className="mt-1 text-xs italic text-muted-foreground">
                          &ldquo;{rule.policy_intent}&rdquo;
                        </p>
                      </div>
                    )}
                    {rule.regulatory_citation && (
                      <div>
                        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                          Regulatory Citation
                        </p>
                        <p className="mt-1 text-xs font-mono text-muted-foreground">
                          {rule.regulatory_citation}
                        </p>
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}
