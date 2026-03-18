"use client";

import Link from "next/link";
import { CheckCircle, Circle, Loader2, Play, ArrowRight, FlaskConical } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
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
}

function deriveSteps(
  workflow: BrdWorkflow | null,
  onRunPipeline: () => void,
  running: boolean,
  onRunSimulation?: () => void,
  simulationRunning?: boolean,
  onGenerateTestCases?: () => void,
  testCaseLoading?: boolean,
  testCaseSuiteId?: string | null,
  testCaseCount?: number
): Step[] {
  const rs = workflow?.rule_set;
  const sim = workflow?.simulation;

  const hasRuleSet = !!rs;
  const rulesApproved = rs?.status === "APPROVED";
  const simCompleted = sim?.status === "COMPLETED";
  const simRunning = sim?.status === "RUNNING";
  const awaitingReview = sim?.status === "AWAITING_REVIEW";

  // Step 1: Upload BRD — always completed
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
      description: "Run the pipeline to extract rules from the BRD",
      state: "pending",
      onAction: onRunPipeline,
      actionLabel: "Run Pipeline",
    });
  }

  // Step 3: Review Rules
  if (rulesApproved) {
    steps.push({
      label: "Review Rules",
      description: "Rules approved",
      state: "completed",
      href: `/rules/${rs!.id}`,
      actionLabel: "View Rules",
    });
  } else if (hasRuleSet && rs.status === "DRAFT") {
    steps.push({
      label: "Review Rules",
      description: `${rs.rules_count} rule${rs.rules_count !== 1 ? "s" : ""} ready for review`,
      state: "active",
      href: sim
        ? `/rules/${rs.id}?simulationId=${sim.id}`
        : `/rules/${rs.id}`,
      actionLabel: "Review Rules",
    });
  } else {
    steps.push({
      label: "Review Rules",
      description: "Review and approve extracted rules",
      state: "pending",
    });
  }

  // Step 4: Test Cases
  if (testCaseSuiteId) {
    steps.push({
      label: "Test Cases",
      description: `${testCaseCount ?? 0} test case${(testCaseCount ?? 0) !== 1 ? "s" : ""} generated`,
      state: "completed",
    });
  } else if (testCaseLoading) {
    steps.push({
      label: "Test Cases",
      description: "Generating test cases...",
      state: "active",
    });
  } else if (rulesApproved) {
    steps.push({
      label: "Test Cases",
      description: "Generate test cases from approved rules",
      state: "active",
      onAction: onGenerateTestCases,
      actionLabel: "Generate Test Cases",
      actionLoading: testCaseLoading,
    });
  } else {
    steps.push({
      label: "Test Cases",
      description: "Test cases generated after rules are approved",
      state: "pending",
    });
  }

  // Step 5: Run Simulation
  if (simCompleted) {
    steps.push({
      label: "Run Simulation",
      description: "Simulation completed",
      state: "completed",
    });
  } else if (simRunning || simulationRunning) {
    steps.push({
      label: "Run Simulation",
      description: "Simulation running...",
      state: "active",
    });
  } else if (rulesApproved) {
    steps.push({
      label: "Run Simulation",
      description: "Rules approved — ready to simulate",
      state: "active",
      onAction: onRunSimulation,
      actionLabel: "Run Simulation",
      actionLoading: simulationRunning,
    });
  } else {
    steps.push({
      label: "Run Simulation",
      description: "Simulation runs after rules are approved",
      state: "pending",
    });
  }

  // Step 5: View Results
  if (simCompleted && sim) {
    steps.push({
      label: "View Results",
      description: "Impact analysis ready",
      state: "completed",
      href: `/simulations/${sim.id}`,
      actionLabel: "View Results",
    });
  } else {
    steps.push({
      label: "View Results",
      description: "Results available after simulation completes",
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
  onRunSimulation?: () => void;
  simulationRunning?: boolean;
  onGenerateTestCases?: () => void;
  testCaseLoading?: boolean;
  testCaseSuiteId?: string | null;
  testCaseCount?: number;
}

export function WorkflowStepper({
  workflow,
  onRunPipeline,
  running,
  onRunSimulation,
  simulationRunning,
  onGenerateTestCases,
  testCaseLoading,
  testCaseSuiteId,
  testCaseCount,
}: WorkflowStepperProps) {
  const steps = deriveSteps(workflow, onRunPipeline, running, onRunSimulation, simulationRunning, onGenerateTestCases, testCaseLoading, testCaseSuiteId, testCaseCount);

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
