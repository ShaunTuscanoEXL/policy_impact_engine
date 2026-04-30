"use client";

import { useEffect, useMemo } from "react";
import Link from "next/link";
import {
  PipelineStageCard,
  StageMetric,
  type StageStatus,
  type StageAccent,
} from "./pipeline-stage-card";
import {
  PipelineProgressStrip,
  type ProgressStrip,
} from "./pipeline-progress-strip";
import { ProgressRing } from "./progress-ring";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Play,
  ArrowRight,
  Activity,
  GitMerge,
  FlaskConical,
  Download,
  Loader2,
  FileSpreadsheet,
  FileJson,
  FileCode2,
  CheckCircle2,
  XCircle,
  Sparkles,
  AlertTriangle,
  ArrowDown,
  Layers,
  GitBranch,
  ShieldCheck,
} from "lucide-react";
import type { BrdWorkflow, BrdDocument } from "@/lib/types";
import { cn } from "@/lib/utils";

export interface TestCaseCounts {
  POSITIVE: number;
  NEGATIVE: number;
  BOUNDARY: number;
  EDGE: number;
  INTERACTION: number;
}

export const DEFAULT_TEST_CASE_COUNTS: TestCaseCounts = {
  POSITIVE: 0,
  NEGATIVE: 0,
  BOUNDARY: 0,
  EDGE: 0,
  INTERACTION: 0,
};

interface PipelineHubProps {
  brd: BrdDocument;
  workflow: BrdWorkflow | null;
  // Action handlers / state
  onExtractRules: () => void;
  extracting: boolean;
  onGenerateTestCases: () => void;
  testCaseLoading: boolean;
  testCaseSuiteId: string | null;
  testCaseCount: number;
  testCaseCounts: TestCaseCounts;
  onCountChange: (cat: keyof TestCaseCounts, value: number) => void;
  maxMatches: number;
  onMaxMatchesChange: (v: number) => void;
  onRunImpact: () => void;
  impactRunning: boolean;
  onExecuteSuite: () => void;
  suiteExecuting: boolean;
}

interface DerivedStageBase {
  step: number;
  title: string;
  subtitle?: string;
  status: StageStatus;
  accent: StageAccent;
  anchorId: string;
}

const STAGE_ACCENTS: StageAccent[] = [
  "blue", // Upload
  "cyan", // Extract
  "violet", // Review
  "amber", // Reconcile
  "rose", // Impact
  "fuchsia", // Generate
  "emerald", // Execute
  "slate", // Export
];

/**
 * The new BRD Pipeline Hub. Orchestrates the eight-stage journey from
 * BRD upload through impact validation and export, with each stage
 * rendered as a rich, status-aware card. The active stage is auto-
 * expanded and visually highlighted; completed stages collapse to a
 * compact summary with reopen-on-click; pending stages stay subtle.
 *
 * The progress strip at the top mirrors the journey state at a glance
 * and lets the operator jump (smooth-scroll) to any stage.
 */
export function PipelineHub(props: PipelineHubProps) {
  const {
    brd,
    workflow,
    onExtractRules,
    extracting,
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
  } = props;

  // ── Compute every stage's status ────────────────────────────────────
  const rs = workflow?.rule_set;
  const mp = workflow?.merge_proposal;
  const lv = workflow?.live_repo_version;
  const ir = workflow?.impact_run;
  const lastExec = workflow?.test_case_suite?.last_execution;

  const hasRuleSet = !!rs;
  const rulesApproved = rs?.status === "APPROVED";
  const rulesDraft = rs?.status === "DRAFT";

  // Walk through and determine each stage's status. The "active" stage
  // is the first non-completed one; everything after stays pending.
  const stageStatuses: StageStatus[] = useMemo(() => {
    const arr: StageStatus[] = ["pending", "pending", "pending", "pending", "pending", "pending", "pending", "pending"];
    arr[0] = "completed"; // Upload always done

    if (extracting) arr[1] = "active";
    else if (hasRuleSet) arr[1] = "completed";

    if (rulesApproved) arr[2] = "completed";
    else if (rulesDraft) arr[2] = "active";

    if (lv && mp?.status === "APPLIED") arr[3] = "completed";
    else if (mp?.status === "PENDING") arr[3] = "active";

    if (ir?.status === "COMPLETED") arr[4] = "completed";
    else if (ir?.status === "RUNNING" || ir?.status === "PENDING" || impactRunning)
      arr[4] = "active";

    if (testCaseSuiteId) arr[5] = "completed";
    else if (testCaseLoading) arr[5] = "active";

    if (lastExec && lastExec.cases_evaluated > 0) arr[6] = "completed";
    else if (suiteExecuting) arr[6] = "active";

    if (testCaseSuiteId) arr[7] = "active"; // export available

    // First non-completed becomes active (if not already)
    const firstIncomplete = arr.findIndex(
      (s) => s !== "completed" && s !== "active",
    );
    if (firstIncomplete !== -1) {
      arr[firstIncomplete] = "active";
    }
    return arr;
  }, [
    extracting,
    hasRuleSet,
    rulesApproved,
    rulesDraft,
    lv,
    mp?.status,
    ir,
    impactRunning,
    testCaseSuiteId,
    testCaseLoading,
    lastExec,
    suiteExecuting,
  ]);

  const currentStep = stageStatuses.findIndex((s) => s === "active") + 1 || 8;
  const completedCount = stageStatuses.filter((s) => s === "completed").length;
  const totalLoanFlips = ir?.summary
    ? Object.entries(ir.summary.decision_flips ?? {}).reduce<number>(
        (acc, [k, v]) => (typeof v === "number" && k.includes("_to_") ? acc + v : acc),
        0,
      )
    : 0;

  // Auto-scroll to active stage on mount
  useEffect(() => {
    if (typeof document === "undefined") return;
    const id = `stage-${currentStep}`;
    const t = setTimeout(() => {
      const el = document.getElementById(id);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 400);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentStep]);

  // Smart deep-links: when a stage maps to a detail page (Rules /
  // Workbench / Live Repo / Impact / Suite), the strip pill links there
  // with ?from_brd=…&step=… so the destination's PipelineContextBar
  // shows the journey context. Otherwise pills smooth-scroll to the
  // stage anchor on this page.
  const stageDeepLinks: (string | undefined)[] = [
    undefined, // 1 Upload — stays on this page
    undefined, // 2 Extract — stays on this page
    rs ? `/rules/${rs.id}?from_brd=${brd.id}&step=3` : undefined,
    mp?.status === "PENDING"
      ? `/merge-workbench/${mp.id}?from_brd=${brd.id}&step=4`
      : lv
        ? `/live-repo/${lv.repository_id}?from_brd=${brd.id}&step=4`
        : undefined,
    ir?.status === "COMPLETED"
      ? `/impact-runs/${ir.id}?from_brd=${brd.id}&step=5`
      : undefined,
    testCaseSuiteId
      ? `/test-suites/${testCaseSuiteId}?from_brd=${brd.id}&step=6`
      : undefined,
    testCaseSuiteId
      ? `/test-suites/${testCaseSuiteId}?from_brd=${brd.id}&step=7`
      : undefined,
    testCaseSuiteId
      ? `/test-suites/${testCaseSuiteId}?from_brd=${brd.id}&step=8`
      : undefined,
  ];

  const stripSteps: ProgressStrip[] = [
    "Upload",
    "Extract",
    "Review",
    "Reconcile",
    "Impact",
    "Generate",
    "Execute",
    "Export",
  ].map((title, i) => ({
    stepNumber: i + 1,
    title,
    status: stageStatuses[i],
    accent: STAGE_ACCENTS[i],
    anchorId: `stage-${i + 1}`,
    deepLink: stageDeepLinks[i],
  }));

  // ── Hero status pill text ───────────────────────────────────────────
  const stagesLabels = [
    "Document uploaded",
    "Extract rules",
    "Review rules",
    "Reconcile with live repo",
    "Run impact analysis",
    "Generate test cases",
    "Execute test suite",
    "Export results",
  ];
  const heroStatusText =
    completedCount === stagesLabels.length
      ? "Pipeline complete"
      : `Stage ${currentStep} of ${stagesLabels.length} · ${stagesLabels[currentStep - 1]}`;

  const isComplete = completedCount === stagesLabels.length;
  const handleContinue = () => {
    if (typeof document === "undefined") return;
    const el = document.getElementById(`stage-${currentStep}`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  return (
    <div className="space-y-6">
      {/* ── Hero band ───────────────────────────────────────────────── */}
      <div className="relative overflow-hidden rounded-2xl border border-border/50 bg-gradient-to-br from-blue-500/[0.05] via-card to-violet-500/[0.05] p-6">
        {/* Decorative gradient blob */}
        <div className="pointer-events-none absolute -right-20 -top-20 size-64 rounded-full bg-gradient-to-br from-blue-500/15 to-violet-500/10 blur-3xl" />
        <div className="pointer-events-none absolute -left-20 -bottom-20 size-64 rounded-full bg-gradient-to-tr from-emerald-500/10 to-fuchsia-500/10 blur-3xl" />

        <div className="relative flex flex-wrap items-start justify-between gap-6">
          <div className="min-w-0 flex-1 space-y-2">
            <div className="flex items-center gap-2">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                BRD Pipeline
              </p>
              <span
                className={cn(
                  "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ring-1 ring-inset",
                  isComplete
                    ? "bg-emerald-500/10 text-emerald-700 ring-emerald-500/30 dark:text-emerald-300"
                    : "bg-blue-500/10 text-blue-700 ring-blue-500/30 dark:text-blue-300",
                )}
              >
                {isComplete ? (
                  <>
                    <CheckCircle2 className="size-3" /> Complete
                  </>
                ) : (
                  <>
                    <Sparkles className="size-3" /> In Progress
                  </>
                )}
              </span>
            </div>
            <h1 className="break-words text-2xl font-bold leading-tight tracking-tight">
              <span className="text-gradient">{brd.filename}</span>
            </h1>
            <div className="flex flex-wrap items-center gap-3 text-xs">
              <Badge
                variant="outline"
                className="bg-blue-500/10 text-blue-700 dark:text-blue-300"
              >
                {brd.file_type.toUpperCase().includes("PDF") ? "PDF" : "DOCX"}
              </Badge>
              <span className="text-muted-foreground">
                Uploaded{" "}
                {new Date(brd.created_at).toLocaleDateString("en-US", {
                  month: "long",
                  day: "numeric",
                  year: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            </div>
            {!isComplete && (
              <div className="!mt-4 flex flex-wrap items-center gap-2">
                <p className="text-sm text-muted-foreground">
                  Next:{" "}
                  <span className="font-semibold text-foreground">
                    {stagesLabels[currentStep - 1]}
                  </span>
                </p>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleContinue}
                  className="h-7"
                >
                  Continue to Stage {currentStep}
                  <ArrowDown className="size-3" />
                </Button>
              </div>
            )}
          </div>

          {/* Progress ring */}
          <div className="shrink-0">
            <ProgressRing
              completed={completedCount}
              total={stagesLabels.length}
              size={104}
              stroke={9}
            />
          </div>
        </div>

        {/* Pill strip */}
        <div className="relative mt-5">
          <PipelineProgressStrip steps={stripSteps} current={currentStep} />
        </div>
      </div>

      {/* ── Stage cards arranged on a vertical journey rail, grouped
              into three lifecycle phases (Capture / Apply / Validate). */}
      <div className="relative pl-8">
        {/* Vertical rail */}
        <div className="absolute left-[7px] top-0 bottom-0 w-0.5 bg-gradient-to-b from-blue-500/30 via-amber-500/30 to-emerald-500/30" />

        {/* Phase 1 — CAPTURE (Upload, Extract, Review) */}
        <PhaseLabel
          label="Capture"
          subtitle="Pull rules out of the document and approve them"
          icon={Layers}
          accent="blue"
        />
        <div className="mb-8 space-y-3">
          {/* Stage 1 — Upload */}
        <PipelineStageCard
          stepNumber={1}
          title="Upload BRD"
          subtitle="Document parsed and ready for extraction"
          status={stageStatuses[0]}
          accent={STAGE_ACCENTS[0]}
          anchorId="stage-1"
          metric={
            <StageMetric label={brd.file_type.toUpperCase()} tone="info" />
          }
        />

        {/* Stage 2 — Extract Rules */}
        <PipelineStageCard
          stepNumber={2}
          title="Extract Rules"
          subtitle={
            hasRuleSet
              ? `${rs!.rules_count} rule${rs!.rules_count !== 1 ? "s" : ""} extracted from the BRD`
              : "Pull policy rules from the document automatically"
          }
          status={stageStatuses[1]}
          accent={STAGE_ACCENTS[1]}
          anchorId="stage-2"
          pendingReason="Available right after upload"
          metric={
            hasRuleSet ? (
              <StageMetric label={`${rs!.rules_count} rules`} tone="info" />
            ) : null
          }
          cta={
            !hasRuleSet && !extracting ? (
              <Button onClick={onExtractRules}>
                <Play className="size-3.5" />
                Extract Rules from Document
              </Button>
            ) : extracting ? (
              <Button disabled>
                <Loader2 className="size-3.5 animate-spin" />
                Extracting…
              </Button>
            ) : null
          }
        >
          {extracting && (
            <p className="text-xs text-muted-foreground">
              Reading the BRD, identifying rule blocks, classifying subsystems…
            </p>
          )}
          {hasRuleSet && rulesDraft && (
            <p className="text-xs text-muted-foreground">
              Extraction succeeded. Rules are now in DRAFT status awaiting
              review and approval.
            </p>
          )}
          {hasRuleSet && rulesApproved && (
            <p className="text-xs text-muted-foreground">
              All {rs!.rules_count} extracted rules have been reviewed and
              approved — they're locked in for downstream stages.
            </p>
          )}
        </PipelineStageCard>

        {/* Stage 3 — Review & Approve Rules */}
        <PipelineStageCard
          stepNumber={3}
          title="Review & Approve Rules"
          subtitle={
            rulesApproved
              ? "All rules approved by the reviewer"
              : rulesDraft
                ? "Rules ready for human review and approval"
                : "Available after extraction"
          }
          status={stageStatuses[2]}
          accent={STAGE_ACCENTS[2]}
          anchorId="stage-3"
          pendingReason="Available after rules are extracted"
          metric={
            rs ? (
              <StageMetric
                label={rs.status}
                tone={
                  rulesApproved
                    ? "success"
                    : rulesDraft
                      ? "warning"
                      : "default"
                }
              />
            ) : null
          }
          cta={
            rs ? (
              <Button
                variant={rulesDraft ? "default" : "outline"}
                render={
                  <Link
                    href={`/rules/${rs.id}?from_brd=${brd.id}&step=3`}
                  />
                }
              >
                {rulesDraft ? "Open Rule Reviewer" : "View Rules"}
                <ArrowRight className="size-3.5" />
              </Button>
            ) : null
          }
        >
          {rs && (
            <p className="text-xs text-muted-foreground">
              {rs.rules_count} rule{rs.rules_count !== 1 ? "s" : ""} extracted
              from <span className="font-medium">{brd.filename}</span>.{" "}
              {rulesDraft
                ? "Open the reviewer to inspect each rule's conditions, actions, and subsystem before approving."
                : "All rules are approved and locked in for downstream stages."}
            </p>
          )}
        </PipelineStageCard>
        </div>

        {/* Phase 2 — APPLY (Reconcile, Impact) */}
        <PhaseLabel
          label="Apply"
          subtitle="Merge into the live repo and measure the impact on real loans"
          icon={GitBranch}
          accent="amber"
        />
        <div className="mb-8 space-y-3">

        {/* Stage 4 — Reconcile with Live Repo */}
        <PipelineStageCard
          stepNumber={4}
          title="Reconcile with Live Repo"
          subtitle={
            lv && mp?.status === "APPLIED"
              ? `Applied as v${lv.version_number} of the live repository`
              : mp?.status === "PENDING"
                ? "Merge proposal awaiting your review"
                : "Diff and merge approved rules into the production policy repo"
          }
          status={stageStatuses[3]}
          accent={STAGE_ACCENTS[3]}
          anchorId="stage-4"
          pendingReason="Available after rules are approved"
          metric={
            lv && mp?.status === "APPLIED" ? (
              <StageMetric label={`v${lv.version_number}`} tone="success" />
            ) : mp?.status === "PENDING" ? (
              <StageMetric label="ACTION REQUIRED" tone="warning" />
            ) : null
          }
          cta={
            mp?.status === "PENDING" ? (
              <Button
                render={
                  <Link
                    href={`/merge-workbench/${mp.id}?from_brd=${brd.id}&step=4`}
                  />
                }
              >
                <GitMerge className="size-3.5" />
                Open Merge Workbench
                <ArrowRight className="size-3.5" />
              </Button>
            ) : lv ? (
              <Button
                variant="outline"
                render={
                  <Link
                    href={`/live-repo/${lv.repository_id}?from_brd=${brd.id}&step=4`}
                  />
                }
              >
                View in Live Repo
                <ArrowRight className="size-3.5" />
              </Button>
            ) : null
          }
        >
          {mp?.summary && (
            <div className="rounded-md bg-muted/30 p-3">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">
                Outcome
              </p>
              <p className="text-xs text-foreground">{mp.summary}</p>
            </div>
          )}
          {mp?.status === "PENDING" && (
            <p className="text-xs text-muted-foreground">
              The reviewer needs to make a decision on each conflicting item
              (accept, reject, supersede, or coexist) before the version can
              be applied.
            </p>
          )}
        </PipelineStageCard>

        {/* Stage 5 — Run Impact Analysis */}
        <PipelineStageCard
          stepNumber={5}
          title="Run Impact Analysis"
          subtitle={
            ir?.status === "COMPLETED"
              ? totalLoanFlips > 0
                ? `${totalLoanFlips.toLocaleString()} loan${totalLoanFlips !== 1 ? "s" : ""} changed decision`
                : "No decision changes — candidate matches baseline"
              : ir?.status === "RUNNING" || impactRunning
                ? "Comparing candidate version against baseline…"
                : lv
                  ? `Compare ${lv.parent_version_number != null ? `v${lv.parent_version_number} → v${lv.version_number}` : `empty baseline → v${lv.version_number}`} on the loan corpus`
                  : "Available after rules are applied to the live repo"
          }
          status={stageStatuses[4]}
          accent={STAGE_ACCENTS[4]}
          anchorId="stage-5"
          pendingReason="Available after the BRD is applied to the live repo"
          metric={
            ir?.status === "COMPLETED" && ir.summary ? (
              <StageMetric
                label={`${((totalLoanFlips / (ir.summary.total_loans || 1)) * 100).toFixed(1)}% flips`}
                tone={
                  totalLoanFlips === 0
                    ? "success"
                    : totalLoanFlips / (ir.summary.total_loans || 1) > 0.2
                      ? "danger"
                      : "warning"
                }
              />
            ) : null
          }
          cta={
            ir?.status === "COMPLETED" ? (
              <Button
                variant="outline"
                render={
                  <Link
                    href={`/impact-runs/${ir.id}?from_brd=${brd.id}&step=5`}
                  />
                }
              >
                <Activity className="size-3.5" />
                View Full Impact Report
                <ArrowRight className="size-3.5" />
              </Button>
            ) : lv && mp?.status === "APPLIED" ? (
              <Button onClick={onRunImpact} disabled={impactRunning}>
                {impactRunning ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <Activity className="size-3.5" />
                )}
                {impactRunning ? "Running impact…" : "Run Impact Analysis"}
              </Button>
            ) : null
          }
        >
          {ir?.status === "COMPLETED" && ir.summary && (
            <div className="space-y-2">
              <div className="grid grid-cols-3 gap-2 text-xs">
                <div className="rounded-md bg-muted/30 p-2">
                  <div className="text-[10px] uppercase text-muted-foreground">
                    Loans evaluated
                  </div>
                  <div className="font-mono font-bold tabular-nums">
                    {ir.summary.total_loans?.toLocaleString() ?? 0}
                  </div>
                </div>
                <div className="rounded-md bg-rose-500/10 p-2">
                  <div className="text-[10px] uppercase text-rose-700 dark:text-rose-300">
                    Decision flips
                  </div>
                  <div className="font-mono font-bold tabular-nums text-rose-700 dark:text-rose-300">
                    {totalLoanFlips.toLocaleString()}
                  </div>
                </div>
                <div className="rounded-md bg-blue-500/10 p-2">
                  <div className="text-[10px] uppercase text-blue-700 dark:text-blue-300">
                    Top driver
                  </div>
                  <div className="font-mono text-[11px] font-bold text-blue-700 dark:text-blue-300 truncate">
                    {Object.entries(ir.summary.by_subsystem ?? {})
                      .sort((a: any, b: any) => (b[1]?.flips_caused ?? 0) - (a[1]?.flips_caused ?? 0))[0]?.[0] ?? "—"}
                  </div>
                </div>
              </div>
            </div>
          )}
        </PipelineStageCard>
        </div>

        {/* Phase 3 — VALIDATE (Generate, Execute, Export) */}
        <PhaseLabel
          label="Validate"
          subtitle="Generate scenarios, execute the test suite, and ship the results"
          icon={ShieldCheck}
          accent="emerald"
        />
        <div className="space-y-3">

        {/* Stage 6 — Generate Test Cases */}
        <PipelineStageCard
          stepNumber={6}
          title="Generate Test Cases"
          subtitle={
            testCaseSuiteId
              ? `${testCaseCount} test case${testCaseCount !== 1 ? "s" : ""} generated`
              : rulesApproved
                ? "Configure counts per category and generate"
                : "Available after rules are approved"
          }
          status={stageStatuses[5]}
          accent={STAGE_ACCENTS[5]}
          anchorId="stage-6"
          pendingReason="Available after rules are approved"
          metric={
            testCaseSuiteId ? (
              <StageMetric label={`${testCaseCount} cases`} tone="info" />
            ) : null
          }
          cta={
            testCaseSuiteId ? (
              <Button
                variant="outline"
                render={
                  <Link
                    href={`/test-suites/${testCaseSuiteId}?from_brd=${brd.id}&step=6`}
                  />
                }
              >
                <FlaskConical className="size-3.5" />
                Open Test Suite
                <ArrowRight className="size-3.5" />
              </Button>
            ) : rulesApproved ? (
              <Button
                onClick={onGenerateTestCases}
                disabled={testCaseLoading}
              >
                {testCaseLoading ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <Sparkles className="size-3.5" />
                )}
                {testCaseLoading ? "Generating…" : "Generate Test Cases"}
              </Button>
            ) : null
          }
        >
          {rulesApproved && !testCaseSuiteId && (
            <div className="space-y-3">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Cases per category
              </p>
              <div className="grid grid-cols-5 gap-2">
                {(Object.keys(DEFAULT_TEST_CASE_COUNTS) as Array<keyof TestCaseCounts>).map(
                  (cat) => (
                    <div key={cat} className="space-y-1">
                      <label className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                        {cat}
                      </label>
                      <Input
                        type="number"
                        min={0}
                        value={testCaseCounts[cat]}
                        onChange={(e) =>
                          onCountChange(cat, parseInt(e.target.value) || 0)
                        }
                        className="h-8 text-sm"
                      />
                    </div>
                  ),
                )}
              </div>
              <div className="flex items-center gap-3">
                <div className="space-y-1">
                  <label className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Max matches per case
                  </label>
                  <Input
                    type="number"
                    min={1}
                    max={50}
                    value={maxMatches}
                    onChange={(e) =>
                      onMaxMatchesChange(parseInt(e.target.value) || 10)
                    }
                    className="h-8 w-24 text-sm"
                  />
                </div>
                <p className="mt-4 text-[10px] text-muted-foreground">
                  loans matched per generated test case
                </p>
              </div>
            </div>
          )}
          {testCaseSuiteId && workflow?.test_case_suite?.cases_by_category && (
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(workflow.test_case_suite.cases_by_category).map(
                ([cat, count]) => (
                  <span
                    key={cat}
                    className="inline-flex items-center gap-1 rounded-full bg-muted/40 px-2 py-0.5 text-[10px] font-mono"
                  >
                    <span className="font-semibold">{cat}</span>
                    <span className="text-muted-foreground">{count}</span>
                  </span>
                ),
              )}
            </div>
          )}
        </PipelineStageCard>

        {/* Stage 7 — Execute Test Suite */}
        <PipelineStageCard
          stepNumber={7}
          title="Execute Test Suite"
          subtitle={
            lastExec && lastExec.cases_evaluated > 0
              ? lastExec.deviates_from_expected === 0
                ? `All ${lastExec.matches_expected.toLocaleString()} loans matched expectations`
                : `${lastExec.matches_expected.toLocaleString()} matched · ${lastExec.deviates_from_expected.toLocaleString()} deviated`
              : testCaseSuiteId && lv && mp?.status === "APPLIED"
                ? `Run the ${testCaseCount} generated cases against live v${lv.version_number}`
                : "Available after test cases are generated and rules are applied"
          }
          status={stageStatuses[6]}
          accent={STAGE_ACCENTS[6]}
          anchorId="stage-7"
          pendingReason="Available after test cases are generated and rules are applied"
          metric={
            lastExec && lastExec.cases_evaluated > 0
              ? (() => {
                  const total =
                    lastExec.matches_expected + lastExec.deviates_from_expected;
                  const pct = total
                    ? Math.round((lastExec.matches_expected / total) * 100)
                    : 0;
                  return (
                    <StageMetric
                      label={`${pct}% pass`}
                      tone={
                        pct === 100
                          ? "success"
                          : pct >= 90
                            ? "warning"
                            : "danger"
                      }
                    />
                  );
                })()
              : null
          }
          cta={
            lastExec && lastExec.cases_evaluated > 0 ? (
              <Button
                variant="outline"
                render={
                  <Link
                    href={`/test-suites/${testCaseSuiteId}?from_brd=${brd.id}&step=7`}
                  />
                }
              >
                <FlaskConical className="size-3.5" />
                View Detailed Results
                <ArrowRight className="size-3.5" />
              </Button>
            ) : testCaseSuiteId && lv && mp?.status === "APPLIED" ? (
              <Button onClick={onExecuteSuite} disabled={suiteExecuting}>
                {suiteExecuting ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <FlaskConical className="size-3.5" />
                )}
                {suiteExecuting ? "Executing…" : "Execute Suite"}
              </Button>
            ) : null
          }
        >
          {lastExec && lastExec.cases_evaluated > 0 && (
            <div className="grid grid-cols-3 gap-2 text-xs">
              <div className="rounded-md bg-emerald-500/10 p-2">
                <div className="flex items-center gap-1 text-[10px] uppercase text-emerald-700 dark:text-emerald-300">
                  <CheckCircle2 className="size-3" />
                  Passing
                </div>
                <div className="font-mono font-bold tabular-nums text-emerald-700 dark:text-emerald-300">
                  {lastExec.matches_expected.toLocaleString()}
                </div>
              </div>
              <div className="rounded-md bg-rose-500/10 p-2">
                <div className="flex items-center gap-1 text-[10px] uppercase text-rose-700 dark:text-rose-300">
                  <XCircle className="size-3" />
                  Deviated
                </div>
                <div className="font-mono font-bold tabular-nums text-rose-700 dark:text-rose-300">
                  {lastExec.deviates_from_expected.toLocaleString()}
                </div>
              </div>
              <div className="rounded-md bg-muted/30 p-2">
                <div className="text-[10px] uppercase text-muted-foreground">
                  Versus version
                </div>
                <div className="font-mono font-bold tabular-nums">
                  v{lastExec.version_number}
                </div>
              </div>
            </div>
          )}
        </PipelineStageCard>

        {/* Stage 8 — Export / Download */}
        <PipelineStageCard
          stepNumber={8}
          title="Export / Download"
          subtitle={
            testCaseSuiteId
              ? "Test cases ready for download in CSV, JSON, or Python"
              : "Available after test cases are generated"
          }
          status={stageStatuses[7]}
          accent={STAGE_ACCENTS[7]}
          anchorId="stage-8"
          pendingReason="Available after test cases are generated"
        >
          {testCaseSuiteId ? (
            <div className="grid gap-2 sm:grid-cols-3">
              <a
                href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001/api/v1"}/test-cases/${testCaseSuiteId}/export/csv`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 rounded-lg border border-border/60 bg-card/40 px-3 py-2 text-sm transition-colors hover:bg-card hover:shadow-sm"
              >
                <FileSpreadsheet className="size-4 text-emerald-600 dark:text-emerald-400" />
                <div className="flex-1 min-w-0">
                  <div className="font-medium">Test Cases (CSV)</div>
                  <div className="text-[10px] text-muted-foreground">
                    Spreadsheet-friendly
                  </div>
                </div>
                <Download className="size-3.5 text-muted-foreground" />
              </a>
              <a
                href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001/api/v1"}/test-cases/${testCaseSuiteId}/export/json`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 rounded-lg border border-border/60 bg-card/40 px-3 py-2 text-sm transition-colors hover:bg-card hover:shadow-sm"
              >
                <FileJson className="size-4 text-amber-600 dark:text-amber-400" />
                <div className="flex-1 min-w-0">
                  <div className="font-medium">Test Cases (JSON)</div>
                  <div className="text-[10px] text-muted-foreground">
                    Machine-readable
                  </div>
                </div>
                <Download className="size-3.5 text-muted-foreground" />
              </a>
              {lv && (
                <a
                  href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001/api/v1"}/live-repo/${lv.repository_id}/version/${lv.version_number}/export.py`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 rounded-lg border border-border/60 bg-card/40 px-3 py-2 text-sm transition-colors hover:bg-card hover:shadow-sm"
                >
                  <FileCode2 className="size-4 text-blue-600 dark:text-blue-400" />
                  <div className="flex-1 min-w-0">
                    <div className="font-medium">Rules v{lv.version_number} (Python)</div>
                    <div className="text-[10px] text-muted-foreground">
                      Engine-ready module
                    </div>
                  </div>
                  <Download className="size-3.5 text-muted-foreground" />
                </a>
              )}
            </div>
          ) : (
            <p className="text-xs italic text-muted-foreground">
              Generate test cases first, then download in your preferred format.
            </p>
          )}
        </PipelineStageCard>
        </div>
      </div>

      {/* Pipeline complete celebration */}
      {completedCount === stagesLabels.length && (
        <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/[0.04] p-5">
          <div className="flex items-center gap-3">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-emerald-500/15 ring-1 ring-inset ring-emerald-500/30">
              <CheckCircle2 className="size-5 text-emerald-600 dark:text-emerald-400" />
            </div>
            <div className="flex-1">
              <p className="text-sm font-semibold">Pipeline complete</p>
              <p className="text-xs text-muted-foreground">
                Every stage of the BRD journey has been completed and validated.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Phase label ─────────────────────────────────────────────────────────

const PHASE_ACCENT_BG: Record<string, string> = {
  blue: "bg-blue-500/10 ring-blue-500/30 text-blue-700 dark:text-blue-300",
  amber: "bg-amber-500/10 ring-amber-500/30 text-amber-700 dark:text-amber-300",
  emerald:
    "bg-emerald-500/10 ring-emerald-500/30 text-emerald-700 dark:text-emerald-300",
};

const PHASE_ICON_COLOR: Record<string, string> = {
  blue: "text-blue-600 dark:text-blue-400",
  amber: "text-amber-600 dark:text-amber-400",
  emerald: "text-emerald-600 dark:text-emerald-400",
};

interface PhaseLabelProps {
  label: string;
  subtitle: string;
  icon: React.ComponentType<{ className?: string }>;
  accent: "blue" | "amber" | "emerald";
}

/**
 * Subtle phase divider sitting on the journey rail. Three phases
 * group the eight stages: Capture (1-3), Apply (4-5), Validate (6-8).
 * The label appears as a chip floating to the left of the rail.
 */
function PhaseLabel({ label, subtitle, icon: Icon, accent }: PhaseLabelProps) {
  return (
    <div className="relative mb-3 mt-1">
      {/* Chip that overlays the rail */}
      <div className="absolute left-[-26px] top-0 z-10 flex items-center gap-2">
        <span
          className={cn(
            "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.14em] ring-1 ring-inset",
            PHASE_ACCENT_BG[accent],
          )}
        >
          <Icon className={cn("size-3", PHASE_ICON_COLOR[accent])} />
          {label}
        </span>
        <span className="hidden text-xs italic text-muted-foreground/70 sm:inline">
          {subtitle}
        </span>
      </div>
      {/* spacer so the next stage card starts below the chip */}
      <div className="h-7" />
    </div>
  );
}
