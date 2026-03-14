"use client";

import { CheckCircle, Loader2, Circle } from "lucide-react";
import { cn } from "@/lib/utils";

export type StepStatus = "completed" | "active" | "pending";

export interface PipelineStep {
  label: string;
  status: StepStatus;
}

const DEFAULT_STEPS: PipelineStep[] = [
  { label: "Upload", status: "pending" },
  { label: "Parsing", status: "pending" },
  { label: "Extracting Rules", status: "pending" },
  { label: "Validating", status: "pending" },
  { label: "Ready for Review", status: "pending" },
];

interface ProcessingStatusProps {
  steps?: PipelineStep[];
}

function StepIcon({ status }: { status: StepStatus }) {
  if (status === "completed") {
    return <CheckCircle className="size-5 text-emerald-500" />;
  }
  if (status === "active") {
    return <Loader2 className="size-5 text-primary animate-spin" />;
  }
  return <Circle className="size-5 text-muted-foreground/40" />;
}

export function ProcessingStatus({
  steps = DEFAULT_STEPS,
}: ProcessingStatusProps) {
  return (
    <div className="flex items-center gap-0">
      {steps.map((step, index) => (
        <div key={step.label} className="flex items-center">
          <div className="flex flex-col items-center gap-1.5">
            <StepIcon status={step.status} />
            <span
              className={cn(
                "text-xs whitespace-nowrap",
                step.status === "completed" &&
                  "font-medium text-emerald-500",
                step.status === "active" && "font-medium text-primary",
                step.status === "pending" && "text-muted-foreground"
              )}
            >
              {step.label}
            </span>
          </div>
          {index < steps.length - 1 && (
            <div
              className={cn(
                "mx-2 mt-[-1.25rem] h-px w-10 sm:w-16 transition-colors",
                step.status === "completed"
                  ? "bg-primary"
                  : "bg-muted-foreground/20"
              )}
            />
          )}
        </div>
      ))}
    </div>
  );
}
