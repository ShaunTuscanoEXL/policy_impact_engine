"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import api from "@/lib/api";
import { ArrowLeft, FileText, ChevronRight, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { BrdDocument, BrdWorkflow } from "@/lib/types";

interface ContextBarStage {
  step: number;
  label: string;
  status: "completed" | "active" | "pending";
}

const STAGE_LABELS = [
  "Upload",
  "Extract",
  "Review",
  "Reconcile",
  "Impact",
  "Generate",
  "Execute",
  "Export",
];

/**
 * Sticky breadcrumb-style strip rendered at the top of any detail page
 * that was reached from a BRD pipeline (?from_brd=… in the URL). Shows:
 *   - "Back to <BRD filename> pipeline" jump link
 *   - The 8 stages with the current one highlighted, all clickable to
 *     return to the BRD hub at that anchor
 *
 * Renders nothing when there's no `from_brd` parameter, so direct visits
 * to the detail pages are unchanged.
 */
export function PipelineContextBar() {
  const params = useSearchParams();
  const brdId = params.get("from_brd");
  const stepRaw = params.get("step");
  const step = stepRaw ? parseInt(stepRaw, 10) : null;

  const [brd, setBrd] = useState<BrdDocument | null>(null);
  const [workflow, setWorkflow] = useState<BrdWorkflow | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!brdId) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const [brdRes, wfRes] = await Promise.allSettled([
          api.get<BrdDocument>(`/brds/${brdId}`),
          api.get<BrdWorkflow>(`/brds/${brdId}/workflow`),
        ]);
        if (cancelled) return;
        if (brdRes.status === "fulfilled") setBrd(brdRes.value.data);
        if (wfRes.status === "fulfilled") setWorkflow(wfRes.value.data);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [brdId]);

  if (!brdId) return null;

  // Compute stage statuses from the workflow snapshot — keep this in
  // sync with the Pipeline Hub's deriveStageStatuses logic.
  const stages: ContextBarStage[] = (() => {
    const arr: ContextBarStage["status"][] = Array(8).fill("pending");
    arr[0] = "completed"; // Upload
    if (workflow?.rule_set) arr[1] = "completed";
    if (workflow?.rule_set?.status === "APPROVED") arr[2] = "completed";
    if (
      workflow?.live_repo_version &&
      workflow.merge_proposal?.status === "APPLIED"
    )
      arr[3] = "completed";
    if (workflow?.impact_run?.status === "COMPLETED") arr[4] = "completed";
    if (workflow?.test_case_suite) arr[5] = "completed";
    const lastExec = workflow?.test_case_suite?.last_execution;
    if (lastExec && lastExec.cases_evaluated > 0) arr[6] = "completed";
    if (workflow?.test_case_suite) arr[7] = "active";
    // First non-completed stage becomes active (fallback)
    const firstIncomplete = arr.findIndex(
      (s) => s !== "completed" && s !== "active",
    );
    if (firstIncomplete !== -1) arr[firstIncomplete] = "active";

    // If the URL specifies a step, mark THAT step as the visually active
    // one (overrides the workflow-derived active). Lets the strip
    // accurately show "you are here" while detailing a specific stage.
    if (step !== null && step >= 1 && step <= 8) {
      arr.forEach((_, i) => {
        if (i + 1 === step && arr[i] !== "completed") arr[i] = "active";
      });
    }

    return arr.map((status, i) => ({
      step: i + 1,
      label: STAGE_LABELS[i],
      status,
    }));
  })();

  const hubHref = step
    ? `/brds/${brdId}#stage-${step}`
    : `/brds/${brdId}`;

  return (
    <div className="sticky top-12 z-30 -mx-10 mb-6 border-b border-border/50 bg-background/85 px-10 py-2.5 backdrop-blur-md">
      <div className="flex items-center gap-3 overflow-x-auto">
        {/* Back link */}
        <Link
          href={hubHref}
          className="group inline-flex shrink-0 items-center gap-2 rounded-lg border border-border/60 bg-card px-2.5 py-1.5 text-xs font-medium text-foreground transition-colors hover:border-foreground/40 hover:bg-accent"
          title="Return to the BRD pipeline hub"
        >
          <ArrowLeft className="size-3.5 transition-transform group-hover:-translate-x-0.5" />
          <FileText className="size-3.5 text-blue-500" />
          <span className="max-w-[28ch] truncate">
            {loading
              ? "Loading…"
              : brd
                ? brd.filename
                : "BRD pipeline"}
          </span>
          <span className="hidden text-muted-foreground sm:inline">
            pipeline
          </span>
        </Link>

        {/* Mini-stage strip */}
        <ol className="flex shrink-0 items-center gap-0.5 text-[10px]">
          {stages.map((s, idx) => {
            const isCurrent = s.step === step;
            const isCompleted = s.status === "completed";
            const isPending = s.status === "pending";
            return (
              <li key={s.step} className="flex items-center">
                <Link
                  href={`/brds/${brdId}#stage-${s.step}`}
                  className={cn(
                    "inline-flex items-center gap-1 rounded-md px-1.5 py-1 font-semibold uppercase tracking-wider transition-colors",
                    isCurrent &&
                      "bg-blue-500/10 text-blue-700 ring-1 ring-inset ring-blue-500/30 dark:text-blue-300",
                    !isCurrent && isCompleted && "text-emerald-600 hover:bg-emerald-500/10 dark:text-emerald-400",
                    !isCurrent && !isCompleted && isPending &&
                      "text-muted-foreground/60 hover:bg-accent",
                    !isCurrent && s.status === "active" &&
                      "text-foreground hover:bg-accent",
                  )}
                  title={`Stage ${s.step}: ${s.label}`}
                >
                  <span
                    className={cn(
                      "flex size-3.5 items-center justify-center rounded-full text-[8px] tabular-nums",
                      isCompleted
                        ? "bg-emerald-500 text-white"
                        : isCurrent
                          ? "bg-blue-500 text-white"
                          : "bg-muted/60 text-muted-foreground/70",
                    )}
                  >
                    {isCompleted ? "✓" : s.step}
                  </span>
                  <span className="hidden md:inline">{s.label}</span>
                </Link>
                {idx < stages.length - 1 && (
                  <ChevronRight className="size-3 shrink-0 text-muted-foreground/30" />
                )}
              </li>
            );
          })}
        </ol>

        {loading && (
          <Loader2 className="size-3.5 shrink-0 animate-spin text-muted-foreground" />
        )}
      </div>
    </div>
  );
}
