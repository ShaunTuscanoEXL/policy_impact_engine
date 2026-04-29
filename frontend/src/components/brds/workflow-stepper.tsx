"use client";

import Link from "next/link";
import {
  CheckCircle,
  Circle,
  Loader2,
  Play,
  ArrowRight,
  Download,
  GitMerge,
  Activity,
  AlertTriangle,
  FlaskConical,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import type { BrdWorkflow } from "@/lib/types";

type StepState = "completed" | "active" | "pending";

interface Step {
  label: string;
  description: string;
  state: StepState;
  href?: string;
  actionLabel?: string;
  onAction?: () => void;
  actionDisabled?: boolean;
  actionLoading?: boolean;
  customContent?: React.ReactNode;
}

export interface TestCaseCounts {
  POSITIVE: number;
  NEGATIVE: number;
  BOUNDARY: number;
  EDGE: number;
  INTERACTION: number;
}

/** Fallback only — the real defaults come from POST /test-cases/suggest-counts */
export const DEFAULT_TEST_CASE_COUNTS: TestCaseCounts = {
  POSITIVE: 0,
  NEGATIVE: 0,
  BOUNDARY: 0,
  EDGE: 0,
  INTERACTION: 0,
};

function deriveSteps(
  workflow: BrdWorkflow | null,
  onRunPipeline: () => void,
  running: boolean,
  onGenerateTestCases?: () => void,
  testCaseLoading?: boolean,
  testCaseSuiteId?: string | null,
  testCaseCount?: number,
  testCaseCounts?: TestCaseCounts,
  onCountChange?: (category: keyof TestCaseCounts, value: number) => void,
  maxMatches?: number,
  onMaxMatchesChange?: (value: number) => void,
  onRunImpact?: () => void,
  impactRunning?: boolean,
  onExecuteSuite?: () => void,
  suiteExecuting?: boolean,
): Step[] {
  const rs = workflow?.rule_set;
  const mp = workflow?.merge_proposal;
  const lv = workflow?.live_repo_version;
  const ir = workflow?.impact_run;

  const hasRuleSet = !!rs;
  const rulesApproved = rs?.status === "APPROVED";

  // Step 1: Upload BRD -- always completed
  const steps: Step[] = [
    {
      label: "Upload BRD",
      description: "Document uploaded",
      state: "completed",
    },
  ];

  // Step 2: Extract Rules
  if (running) {
    steps.push({
      label: "Extract Rules",
      description: "Pipeline running...",
      state: "active",
    });
  } else if (hasRuleSet) {
    steps.push({
      label: "Extract Rules",
      description: `${rs.rules_count} rule${rs.rules_count !== 1 ? "s" : ""} extracted`,
      state: "completed",
    });
  } else {
    steps.push({
      label: "Extract Rules",
      description: "Extract rules directly from the BRD document",
      state: "pending",
      onAction: onRunPipeline,
      actionLabel: "Extract Rules",
    });
  }

  // Step 3: Review & Approve Rules
  if (rulesApproved) {
    steps.push({
      label: "Review & Approve Rules",
      description: "Rules approved",
      state: "completed",
      href: `/rules/${rs!.id}`,
      actionLabel: "View Rules",
    });
  } else if (hasRuleSet && rs.status === "DRAFT") {
    steps.push({
      label: "Review & Approve Rules",
      description: `${rs.rules_count} rule${rs.rules_count !== 1 ? "s" : ""} ready for review`,
      state: "active",
      href: `/rules/${rs.id}`,
      actionLabel: "Review Rules",
    });
  } else {
    steps.push({
      label: "Review & Approve Rules",
      description: "Review and approve extracted rules",
      state: "pending",
    });
  }

  // ── Step 4: Reconcile with Live Repo (Merge Workbench) ──────────────
  // Auto-baselined repo (first BRD): merge_proposal.status === "APPLIED" + live_repo_version exists
  // Subsequent BRDs land as "PENDING" → user opens workbench to resolve
  if (lv && mp?.status === "APPLIED") {
    const isBaseline = lv.parent_version_number === null || lv.parent_version_number === 0;
    steps.push({
      label: "Reconcile with Live Repo",
      description: isBaseline
        ? `Auto-baselined as v${lv.version_number} (first BRD against this repo)`
        : `Applied as v${lv.version_number}${
            mp.decided_by ? ` by ${mp.decided_by}` : ""
          }`,
      state: "completed",
      href: `/live-repo/${lv.repository_id}`,
      actionLabel: "View Repository",
      customContent: mp.summary ? (
        <p className="mt-1.5 text-[11px] text-muted-foreground">
          <span className="font-medium text-foreground">Outcome:</span>{" "}
          {mp.summary}
        </p>
      ) : null,
    });
  } else if (mp?.status === "PENDING") {
    // PENDING proposal — user needs to review in the workbench
    steps.push({
      label: "Reconcile with Live Repo",
      description:
        mp.summary ?? `Pending review against base v${mp.base_version}`,
      state: "active",
      href: `/merge-workbench/${mp.id}`,
      actionLabel: "Open Merge Workbench",
      customContent: (
        <div className="mt-1.5 inline-flex items-center gap-1.5">
          <Badge
            variant="outline"
            className="bg-amber-500/10 text-amber-600 border-amber-500/20 dark:text-amber-400 text-[10px]"
          >
            <AlertTriangle className="size-3" />
            Action required
          </Badge>
        </div>
      ),
    });
  } else if (rulesApproved || hasRuleSet) {
    steps.push({
      label: "Reconcile with Live Repo",
      description: "Merge proposal will be created automatically after extraction",
      state: "pending",
    });
  } else {
    steps.push({
      label: "Reconcile with Live Repo",
      description:
        "Diff this BRD against the live US-PERSONAL repo for review and apply",
      state: "pending",
    });
  }

  // ── Step 5: Run Impact Analysis ─────────────────────────────────────
  if (ir && ir.status === "COMPLETED") {
    const summary = ir.summary;
    const totalFlips = summary
      ? Object.values(summary.decision_flips ?? {}).reduce(
          (a, n) => a + n,
          0
        )
      : 0;
    steps.push({
      label: "Run Impact Analysis",
      description:
        totalFlips > 0
          ? `${totalFlips.toLocaleString()} loan${
              totalFlips !== 1 ? "s" : ""
            } changed decision (${(summary?.total_loans ?? 0).toLocaleString()} evaluated)`
          : `No decisions changed across ${(summary?.total_loans ?? 0).toLocaleString()} loans`,
      state: "completed",
      href: `/impact-runs/${ir.id}`,
      actionLabel: "View Impact",
    });
  } else if (ir && (ir.status === "RUNNING" || ir.status === "PENDING")) {
    steps.push({
      label: "Run Impact Analysis",
      description: "Impact run in progress…",
      state: "active",
    });
  } else if (lv && mp?.status === "APPLIED" && onRunImpact) {
    const baseLabel =
      lv.parent_version_number !== null && lv.parent_version_number !== undefined
        ? `v${lv.parent_version_number} → v${lv.version_number}`
        : `empty baseline → v${lv.version_number}`;
    steps.push({
      label: "Run Impact Analysis",
      description: `Compare ${baseLabel} against the loan-record corpus`,
      state: "active",
      onAction: onRunImpact,
      actionLabel: impactRunning ? "Running…" : "Run Impact",
      actionLoading: impactRunning,
    });
  } else {
    steps.push({
      label: "Run Impact Analysis",
      description:
        "Available once the BRD is applied to the live repository",
      state: "pending",
    });
  }

  // Step 6: Generate Test Cases (with configurable counts)
  if (testCaseSuiteId) {
    steps.push({
      label: "Generate Test Cases",
      description: `${testCaseCount ?? 0} test case${(testCaseCount ?? 0) !== 1 ? "s" : ""} generated`,
      state: "completed",
      href: `/test-suites/${testCaseSuiteId}`,
      actionLabel: "View Test Suite",
    });
  } else if (testCaseLoading) {
    steps.push({
      label: "Generate Test Cases",
      description: "Generating test cases...",
      state: "active",
    });
  } else if (rulesApproved) {
    const countsForm = testCaseCounts && onCountChange ? (
      <div className="mt-3 space-y-3">
        <p className="text-xs font-medium text-muted-foreground mb-1">Cases per category:</p>
        <div className="grid grid-cols-5 gap-2">
          {(Object.keys(DEFAULT_TEST_CASE_COUNTS) as Array<keyof TestCaseCounts>).map((cat) => (
            <div key={cat} className="space-y-1">
              <label className="text-[10px] font-medium text-muted-foreground uppercase">{cat}</label>
              <Input
                type="number"
                min={0}
                value={testCaseCounts[cat]}
                onChange={(e) => onCountChange(cat, parseInt(e.target.value) || 0)}
                className="h-8 text-sm"
              />
            </div>
          ))}
        </div>
        {onMaxMatchesChange && (
          <div className="flex items-center gap-3">
            <div className="space-y-1">
              <label className="text-[10px] font-medium text-muted-foreground uppercase">Max Matches</label>
              <Input
                type="number"
                min={1}
                max={50}
                value={maxMatches ?? 10}
                onChange={(e) => onMaxMatchesChange(parseInt(e.target.value) || 10)}
                className="h-8 text-sm w-24"
              />
            </div>
            <p className="text-[10px] text-muted-foreground mt-4">customers per test case</p>
          </div>
        )}
      </div>
    ) : null;

    steps.push({
      label: "Generate Test Cases",
      description: "Configure counts and generate test cases from approved rules",
      state: "active",
      onAction: onGenerateTestCases,
      actionLabel: "Generate",
      actionLoading: testCaseLoading,
      customContent: countsForm,
    });
  } else {
    steps.push({
      label: "Generate Test Cases",
      description: "Test cases generated after rules are approved",
      state: "pending",
    });
  }

  // ── Step 7: Execute Test Suite — scenario testing against the live
  // version (per-test-case PASS/FAIL). Distinct from impact analysis,
  // which is corpus-wide decision flips between two versions.
  const lastExec = workflow?.test_case_suite?.last_execution;
  if (lastExec && lastExec.cases_evaluated > 0) {
    const passed = lastExec.matches_expected;
    const failed = lastExec.deviates_from_expected;
    steps.push({
      label: "Execute Test Suite",
      description: failed === 0
        ? `All ${passed.toLocaleString()} matched-loan outcome${passed !== 1 ? "s" : ""} matched expectations${
            lastExec.version_number ? ` (against v${lastExec.version_number})` : ""
          }`
        : `${passed.toLocaleString()} matched · ${failed.toLocaleString()} deviated${
            lastExec.version_number ? ` (against v${lastExec.version_number})` : ""
          }`,
      state: "completed",
      href: testCaseSuiteId ? `/test-suites/${testCaseSuiteId}` : undefined,
      actionLabel: "View Results",
    });
  } else if (testCaseSuiteId && lv && mp?.status === "APPLIED" && onExecuteSuite) {
    steps.push({
      label: "Execute Test Suite",
      description: `Run the ${testCaseCount ?? 0} generated test case${
        (testCaseCount ?? 0) !== 1 ? "s" : ""
      } against live v${lv.version_number} loans`,
      state: "active",
      onAction: onExecuteSuite,
      actionLabel: suiteExecuting ? "Executing…" : "Execute Suite",
      actionLoading: suiteExecuting,
    });
  } else if (testCaseSuiteId && (!lv || mp?.status !== "APPLIED")) {
    steps.push({
      label: "Execute Test Suite",
      description: "Available once the BRD is applied to the live repository",
      state: "pending",
    });
  } else {
    steps.push({
      label: "Execute Test Suite",
      description: "Scenario testing — runs each test case against live rules",
      state: "pending",
    });
  }

  // Step 8: Export / Download
  if (testCaseSuiteId) {
    steps.push({
      label: "Export / Download",
      description: "Test suite ready for export",
      state: "active",
      href: `/test-suites/${testCaseSuiteId}`,
      actionLabel: "Export Suite",
    });
  } else {
    steps.push({
      label: "Export / Download",
      description: "Export test suite after generation",
      state: "pending",
    });
  }

  return steps;
}

function StepIcon({ state }: { state: StepState }) {
  if (state === "completed") {
    return <CheckCircle className="size-6 text-emerald-500" />;
  }
  if (state === "active") {
    return (
      <div className="flex size-6 items-center justify-center rounded-full border-2 border-blue-500 bg-blue-50 dark:bg-blue-950">
        <Circle className="size-2.5 fill-blue-500 text-blue-500" />
      </div>
    );
  }
  return <Circle className="size-6 text-muted-foreground/30" />;
}

interface WorkflowStepperProps {
  workflow: BrdWorkflow | null;
  onRunPipeline: () => void;
  running: boolean;
  onGenerateTestCases?: () => void;
  testCaseLoading?: boolean;
  testCaseSuiteId?: string | null;
  testCaseCount?: number;
  testCaseCounts?: TestCaseCounts;
  onCountChange?: (category: keyof TestCaseCounts, value: number) => void;
  maxMatches?: number;
  onMaxMatchesChange?: (value: number) => void;
  onRunImpact?: () => void;
  impactRunning?: boolean;
  onExecuteSuite?: () => void;
  suiteExecuting?: boolean;
}

export function WorkflowStepper({
  workflow,
  onRunPipeline,
  running,
  onGenerateTestCases,
  testCaseLoading,
  testCaseSuiteId,
  testCaseCount,
  testCaseCounts,
  onCountChange,
  maxMatches,
  onMaxMatchesChange,
  onRunImpact,
  impactRunning,
  onExecuteSuite,
  suiteExecuting,
}: WorkflowStepperProps) {
  const steps = deriveSteps(
    workflow,
    onRunPipeline,
    running,
    onGenerateTestCases,
    testCaseLoading,
    testCaseSuiteId,
    testCaseCount,
    testCaseCounts,
    onCountChange,
    maxMatches,
    onMaxMatchesChange,
    onRunImpact,
    impactRunning,
    onExecuteSuite,
    suiteExecuting,
  );

  return (
    <div className="space-y-0">
      {steps.map((step, index) => (
        <div key={step.label} className="flex gap-4">
          {/* Icon + line column */}
          <div className="flex flex-col items-center">
            <StepIcon state={step.state} />
            {index < steps.length - 1 && (
              <div
                className={cn(
                  "w-px flex-1 min-h-8",
                  step.state === "completed"
                    ? "bg-emerald-300 dark:bg-emerald-700"
                    : "bg-border"
                )}
              />
            )}
          </div>

          {/* Content */}
          <div className={cn("pb-8", index === steps.length - 1 && "pb-0")}>
            <p
              className={cn(
                "text-sm font-medium leading-6",
                step.state === "completed" && "text-foreground",
                step.state === "active" && "text-blue-600 dark:text-blue-400",
                step.state === "pending" && "text-muted-foreground"
              )}
            >
              {step.label}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              {step.description}
            </p>

            {/* Custom content (e.g. count configuration form) */}
            {step.customContent}

            {/* Action button */}
            {step.onAction && (
              <Button
                size="sm"
                className="mt-2"
                onClick={step.onAction}
                disabled={step.actionDisabled || step.actionLoading}
              >
                {step.actionLoading ? (
                  <Loader2 className="mr-1.5 size-3.5 animate-spin" />
                ) : step.label.includes("Export") ? (
                  <Download className="mr-1.5 size-3.5" />
                ) : step.label.includes("Impact") ? (
                  <Activity className="mr-1.5 size-3.5" />
                ) : step.label.includes("Execute") ? (
                  <FlaskConical className="mr-1.5 size-3.5" />
                ) : (
                  <Play className="mr-1.5 size-3.5" />
                )}
                {step.actionLabel}
              </Button>
            )}

            {/* Link button */}
            {step.href && step.actionLabel && !step.onAction && (
              <Button
                variant={step.state === "active" ? "default" : "outline"}
                size="sm"
                className="mt-2"
                render={<Link href={step.href} />}
              >
                {step.label.includes("Workbench")
                  ? <GitMerge className="mr-1.5 size-3.5" />
                  : step.label.includes("Impact")
                    ? <Activity className="mr-1.5 size-3.5" />
                    : null}
                {step.actionLabel}
                <ArrowRight className="ml-1.5 size-3.5" />
              </Button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
