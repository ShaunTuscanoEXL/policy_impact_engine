"use client";

import { useState } from "react";
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
} from "lucide-react";
import type { Rule, Condition, Action } from "@/lib/types";

interface RuleTableProps {
  rules: Rule[];
  onEdit: (rule: Rule) => void;
  onDelete: (ruleId: string) => void;
}

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
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-8 text-xs uppercase tracking-wider" />
          <TableHead className="text-xs uppercase tracking-wider">Rule ID</TableHead>
          <TableHead className="text-xs uppercase tracking-wider">Name</TableHead>
          <TableHead className="text-xs uppercase tracking-wider">Type</TableHead>
          <TableHead className="text-xs uppercase tracking-wider">Confidence</TableHead>
          <TableHead className="text-center text-xs uppercase tracking-wider">Priority</TableHead>
          <TableHead className="text-center text-xs uppercase tracking-wider">Conflicts</TableHead>
          <TableHead className="text-right text-xs uppercase tracking-wider">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rules.map((rule) => {
          const isExpanded = expandedRows.has(rule.id);
          return (
            <ExpandableRuleRow
              key={rule.id}
              rule={rule}
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
  );
}

interface ExpandableRuleRowProps {
  rule: Rule;
  isExpanded: boolean;
  onToggle: () => void;
  onEdit: () => void;
  onDelete: () => void;
  isDeleteConfirm: boolean;
  onCancelDelete: () => void;
}

function ExpandableRuleRow({
  rule,
  isExpanded,
  onToggle,
  onEdit,
  onDelete,
  isDeleteConfirm,
  onCancelDelete,
}: ExpandableRuleRowProps) {
  const typeClass =
    RULE_TYPE_COLORS[rule.rule_type] || "bg-gray-100 text-gray-800";

  return (
    <>
      <TableRow className="cursor-pointer hover:bg-muted/50 transition-colors" onClick={onToggle}>
        <TableCell>
          {isExpanded ? (
            <ChevronDown className="size-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="size-4 text-muted-foreground" />
          )}
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
          <TableCell colSpan={8} className="bg-muted/30 p-0">
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
                    rule.conditions.map((cond, i) => (
                      <span key={i} className="flex items-center gap-1.5">
                        {i > 0 && (
                          <Badge
                            variant="secondary"
                            className="text-[10px] px-1.5"
                          >
                            {cond.logic || "AND"}
                          </Badge>
                        )}
                        <code className="rounded bg-muted px-2 py-0.5 text-xs">
                          {formatCondition(cond)}
                        </code>
                      </span>
                    ))
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
                    rule.actions.map((action, i) => (
                      <div key={i} className="flex items-center gap-2">
                        <code
                          className={`rounded bg-muted px-2 py-0.5 text-xs font-medium ${
                            ACTION_TYPE_COLORS[action.action_type] || ""
                          }`}
                        >
                          {formatAction(action)}
                        </code>
                        {action.description && (
                          <span className="text-xs text-muted-foreground">
                            — {action.description}
                          </span>
                        )}
                      </div>
                    ))
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
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}
