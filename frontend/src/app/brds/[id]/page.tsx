"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import api from "@/lib/api";
import type { BrdDocument, BrdWorkflow, SuggestedCounts } from "@/lib/types";
import { toast } from "sonner";
import {
  PipelineHub,
  type TestCaseCounts,
  DEFAULT_TEST_CASE_COUNTS,
} from "@/components/brds/pipeline/pipeline-hub";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Loader2 } from "lucide-react";
import { PageTransition } from "@/components/page-transition";
import { DecisionDialog } from "@/components/decision-dialog";
import { AuditTimeline } from "@/components/audit/audit-timeline";

export default function BrdDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [brd, setBrd] = useState<BrdDocument | null>(null);
  const [loading, setLoading] = useState(true);

  const [extracting, setExtracting] = useState(false);

  // Workflow state
  const [workflow, setWorkflow] = useState<BrdWorkflow | null>(null);

  // Test case state
  const [testCaseSuiteId, setTestCaseSuiteId] = useState<string | null>(null);
  const [testCaseCount, setTestCaseCount] = useState<number>(0);
  const [testCaseLoading, setTestCaseLoading] = useState(false);
  const [testCaseCounts, setTestCaseCounts] = useState<TestCaseCounts>({
    ...DEFAULT_TEST_CASE_COUNTS,
  });
  const [maxMatches, setMaxMatches] = useState(10);

  const fetchSuggestedCounts = useCallback(async (ruleSetId: string) => {
    try {
      const { data } = await api.post<SuggestedCounts>(
        "/test-cases/suggest-counts",
        { rule_set_id: ruleSetId },
      );
      setTestCaseCounts({
        POSITIVE: data.positive,
        NEGATIVE: data.negative,
        BOUNDARY: data.boundary,
        EDGE: data.edge,
        INTERACTION: data.interaction,
      });
    } catch {
      // Fall back to zeros if suggest-counts fails
    }
  }, []);

  const fetchWorkflow = useCallback(async () => {
    try {
      const { data } = await api.get<BrdWorkflow>(`/brds/${params.id}/workflow`);
      setWorkflow(data);
      if (data.test_case_suite) {
        setTestCaseSuiteId(data.test_case_suite.id);
        setTestCaseCount(data.test_case_suite.total_cases);
      }
      if (data.rule_set?.status === "APPROVED" && !data.test_case_suite) {
        fetchSuggestedCounts(data.rule_set.id);
      }
    } catch {
      // Workflow endpoint may not exist yet for fresh BRDs
    }
  }, [params.id, fetchSuggestedCounts]);

  useEffect(() => {
    async function fetchBrd() {
      try {
        const { data } = await api.get(`/brds/${params.id}`);
        setBrd(data);
      } catch {
        toast.error("Failed to load BRD document.");
        router.push("/brds");
      } finally {
        setLoading(false);
      }
    }
    fetchBrd();
    fetchWorkflow();
  }, [params.id, router, fetchWorkflow]);

  // Auto-refresh the workflow whenever the tab regains focus or the
  // window becomes visible again. Catches the common cross-page flow:
  // user clicks into the merge workbench / impact run / suite execution
  // detail page, takes an action, returns to the BRD pipeline — without
  // this, the stage cards would still show the pre-action state until a
  // hard reload.
  useEffect(() => {
    const onFocus = () => {
      fetchWorkflow();
    };
    const onVisibility = () => {
      if (document.visibilityState === "visible") fetchWorkflow();
    };
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [fetchWorkflow]);

  const handleExtractRules = useCallback(async () => {
    setExtracting(true);
    try {
      const { data } = await api.post(`/brds/${params.id}/extract-rules`);
      toast.success(
        `${data.rules_count ?? data.rules_extracted ?? 0} rules extracted.`,
      );
      await fetchWorkflow();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Rule extraction failed.");
    } finally {
      setExtracting(false);
    }
  }, [params.id, fetchWorkflow]);

  const handleCountChange = useCallback(
    (category: keyof TestCaseCounts, value: number) => {
      setTestCaseCounts((prev) => ({ ...prev, [category]: value }));
    },
    [],
  );

  const handleGenerateTestCases = useCallback(async () => {
    if (!workflow?.rule_set) return;
    setTestCaseLoading(true);
    try {
      const { data } = await api.post("/test-cases/generate", {
        rule_set_id: workflow.rule_set.id,
        positive_count: testCaseCounts.POSITIVE,
        negative_count: testCaseCounts.NEGATIVE,
        boundary_count: testCaseCounts.BOUNDARY,
        edge_count: testCaseCounts.EDGE,
        interaction_count: testCaseCounts.INTERACTION,
        max_matches: maxMatches,
      });
      setTestCaseSuiteId(data.id);
      setTestCaseCount(data.total_cases);
      toast.success(`${data.total_cases} test cases generated.`);
      await fetchWorkflow();
    } catch (err: any) {
      toast.error(
        err?.response?.data?.detail || "Failed to generate test cases.",
      );
    } finally {
      setTestCaseLoading(false);
    }
  }, [workflow, testCaseCounts, maxMatches, fetchWorkflow]);

  const [suiteExecuting, setSuiteExecuting] = useState(false);
  const [executeDialogOpen, setExecuteDialogOpen] = useState(false);
  const handleExecuteSuiteConfirm = useCallback(
    async ({ actor, rationale }: { actor: string; rationale: string }) => {
      const suiteId = workflow?.test_case_suite?.id ?? testCaseSuiteId;
      const lv = workflow?.live_repo_version;
      if (!suiteId || !lv) return;
      setSuiteExecuting(true);
      try {
        const { data } = await api.post(`/test-cases/${suiteId}/execute`, {
          version_id: lv.version_id,
          executed_by: actor,
          rationale: rationale || null,
        });
        const passed = data.summary?.matches_expected ?? 0;
        const failed = data.summary?.deviates_from_expected ?? 0;
        toast.success(
          failed === 0
            ? `Executed by ${actor}: all ${passed.toLocaleString()} matched outcomes are as expected.`
            : `Executed by ${actor}: ${passed.toLocaleString()} matched, ${failed.toLocaleString()} deviated.`,
        );
        setExecuteDialogOpen(false);
        await fetchWorkflow();
      } catch (err: any) {
        toast.error(
          err?.response?.data?.detail || "Failed to execute test suite.",
        );
      } finally {
        setSuiteExecuting(false);
      }
    },
    [workflow, testCaseSuiteId, fetchWorkflow],
  );
  const handleExecuteSuite = useCallback(() => {
    setExecuteDialogOpen(true);
  }, []);

  const [impactRunning, setImpactRunning] = useState(false);
  const [impactDialogOpen, setImpactDialogOpen] = useState(false);
  const handleRunImpactConfirm = useCallback(
    async ({ actor, rationale }: { actor: string; rationale: string }) => {
      const lv = workflow?.live_repo_version;
      if (!lv) return;
      setImpactRunning(true);
      try {
        const payload: Record<string, any> = {
          repository_id: lv.repository_id,
          candidate_version_id: lv.version_id,
          created_by: actor,
          rationale: rationale || null,
        };
        if (lv.parent_version_id) {
          payload.base_version_id = lv.parent_version_id;
        }
        const { data } = await api.post("/impact-run", payload);
        toast.success(
          `Impact analysis ${data.status === "COMPLETED" ? "complete" : "started"} by ${actor}.`,
        );
        setImpactDialogOpen(false);
        await fetchWorkflow();
      } catch (err: any) {
        toast.error(
          err?.response?.data?.detail || "Failed to start impact run.",
        );
      } finally {
        setImpactRunning(false);
      }
    },
    [workflow, fetchWorkflow],
  );
  const handleRunImpact = useCallback(() => {
    setImpactDialogOpen(true);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!brd) return null;

  return (
    <PageTransition>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <p className="text-xs text-muted-foreground">
            Dashboard /{" "}
            <Link href="/brds" className="hover:underline">
              BRDs
            </Link>{" "}
            / {brd.filename}
          </p>
          <Button
            variant="ghost"
            size="sm"
            render={<Link href="/brds" />}
          >
            <ArrowLeft className="size-4" />
            All BRDs
          </Button>
        </div>

        <PipelineHub
          brd={brd}
          workflow={workflow}
          onExtractRules={handleExtractRules}
          extracting={extracting}
          onGenerateTestCases={handleGenerateTestCases}
          testCaseLoading={testCaseLoading}
          testCaseSuiteId={testCaseSuiteId}
          testCaseCount={testCaseCount}
          testCaseCounts={testCaseCounts}
          onCountChange={handleCountChange}
          maxMatches={maxMatches}
          onMaxMatchesChange={setMaxMatches}
          onRunImpact={handleRunImpact}
          impactRunning={impactRunning}
          onExecuteSuite={handleExecuteSuite}
          suiteExecuting={suiteExecuting}
        />

        {/* Slice 3 — chronological audit log of every action taken on
            this BRD: upload → extract → approve → merge → promote →
            impact → execute. Surfaces the actor + rationale captured
            by the DecisionDialog so reviewers can answer "who/why/when"
            without leaving the page. */}
        <AuditTimeline brdId={brd.id} title="BRD activity timeline" />
      </div>

      {/* Impact + Execute decision dialogs — capture actor + optional
          rationale so the audit timeline knows who/why. */}
      <DecisionDialog
        open={impactDialogOpen}
        onOpenChange={setImpactDialogOpen}
        title="Run impact analysis"
        description="Compares the candidate version against the baseline across the loan corpus and records the decision flips. The rationale shows up in the impact run summary + per-BRD audit timeline."
        confirmLabel="Run impact"
        rationalePlaceholder="e.g. pre-promotion regression check before approving v2 for production"
        loading={impactRunning}
        onConfirm={handleRunImpactConfirm}
      />
      <DecisionDialog
        open={executeDialogOpen}
        onOpenChange={setExecuteDialogOpen}
        title="Execute test suite"
        description="Runs every test case against the live rule version using the matched loans. Captures who validated and (optionally) why."
        confirmLabel="Execute suite"
        rationalePlaceholder="e.g. validating the new FICO floor before sign-off"
        loading={suiteExecuting}
        onConfirm={handleExecuteSuiteConfirm}
      />
    </PageTransition>
  );
}
