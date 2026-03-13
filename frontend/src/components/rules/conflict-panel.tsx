"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { AlertTriangle, ChevronDown, ChevronRight } from "lucide-react";
import type { Rule } from "@/lib/types";

interface ConflictPanelProps {
  rules: Rule[];
}

interface ConflictInfo {
  ruleId: string;
  ruleName: string;
  details: any;
}

export function ConflictPanel({ rules }: ConflictPanelProps) {
  const [expanded, setExpanded] = useState(false);

  const conflictingRules: ConflictInfo[] = rules
    .filter((r) => r.has_conflicts)
    .map((r) => ({
      ruleId: r.rule_id,
      ruleName: r.rule_name,
      details: r.conflict_details,
    }));

  if (conflictingRules.length === 0) return null;

  return (
    <Card className="border-amber-200 bg-amber-50 p-4 dark:border-amber-900/50 dark:bg-amber-950/20">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex size-8 items-center justify-center rounded-full bg-yellow-100 dark:bg-yellow-900/50">
            <AlertTriangle className="size-4 text-yellow-600 dark:text-yellow-400" />
          </div>
          <div>
            <p className="text-sm font-medium text-yellow-800 dark:text-yellow-200">
              {conflictingRules.length} Conflict{conflictingRules.length > 1 ? "s" : ""} Detected
            </p>
            <p className="text-xs text-yellow-600 dark:text-yellow-400">
              Review and resolve conflicts before approving
            </p>
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setExpanded(!expanded)}
          className="text-yellow-700 dark:text-yellow-300"
        >
          {expanded ? (
            <ChevronDown className="mr-1 size-4" />
          ) : (
            <ChevronRight className="mr-1 size-4" />
          )}
          {expanded ? "Hide" : "Show"} Details
        </Button>
      </div>

      {expanded && (
        <div className="mt-4 space-y-3">
          {conflictingRules.map((conflict) => (
            <div
              key={conflict.ruleId}
              className="rounded-lg border border-yellow-300/50 bg-white/60 p-3 dark:bg-black/20"
            >
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="border-yellow-500 text-yellow-700 dark:text-yellow-300">
                  {conflict.ruleId}
                </Badge>
                <span className="text-sm font-medium">{conflict.ruleName}</span>
              </div>
              {conflict.details && (
                <div className="mt-2 text-xs text-muted-foreground">
                  {typeof conflict.details === "string" ? (
                    <p>{conflict.details}</p>
                  ) : Array.isArray(conflict.details) ? (
                    <ul className="list-inside list-disc space-y-1">
                      {conflict.details.map((d: any, i: number) => (
                        <li key={i}>
                          {typeof d === "string"
                            ? d
                            : d.message || d.description || JSON.stringify(d)}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p>{conflict.details.message || conflict.details.description || JSON.stringify(conflict.details)}</p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
