"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import api from "@/lib/api";
import type { BrdDocument, BrdWorkflow, SuggestedCounts } from "@/lib/types";
import { toast } from "sonner";
import {
  WorkflowStepper,
  type TestCaseCounts,
  DEFAULT_TEST_CASE_COUNTS,
} from "@/components/brds/workflow-stepper";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { FileText, ArrowLeft, Loader2, GitMerge, GitBranch, ArrowRight } from "lucide-react";
import { PageTransition } from "@/components/page-transition";
import { motion } from "framer-motion";

export default function BrdDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [brd, setBrd] = useState<BrdDocument | null>(null);
  const [loading, setLoading] = useState(true);

  const [running, setRunning] = useState(false);

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
  const [countsLoaded, setCountsLoaded] = useState(false);

  const fetchSuggestedCounts = useCallback(async (ruleSetId: string) => {
    try {
      const { data } = await api.post<SuggestedCounts>("/test-cases/suggest-counts", {
        rule_set_id: ruleSetId,
      });
      setTestCaseCounts({
        POSITIVE: data.positive,
        NEGATIVE: data.negative,
        BOUNDARY: data.boundary,
        EDGE: data.edge,
        INTERACTION: data.interaction,
      });
      setCountsLoaded(true);
    } catch {
      // Fall back to zeros if suggest-counts fails
    }
  }, []);

  const fetchWorkflow = useCallback(async () => {
    try {
      const { data } = await api.get<BrdWorkflow>(
        `/brds/${params.id}/workflow`
      );
      setWorkflow(data);
      if (data.test_case_suite) {
        setTestCaseSuiteId(data.test_case_suite.id);
        setTestCaseCount(data.test_case_suite.total_cases);
      }
      // Auto-fetch suggested counts when rule set is approved
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

  const handleExtractRules = useCallback(async () => {
    setRunning(true);
    try {
      const { data } = await api.post(`/brds/${params.id}/extract-rules`);
      toast.success(
        `${data.rules_count ?? data.rules_extracted ?? 0} rules extracted.`
      );
      await fetchWorkflow();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Rule extraction failed.");
    } finally {
      setRunning(false);
    }
  }, [params.id, fetchWorkflow]);

  const handleCountChange = useCallback(
    (category: keyof TestCaseCounts, value: number) => {
      setTestCaseCounts((prev) => ({ ...prev, [category]: value }));
    },
    []
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
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to generate test cases.");
    } finally {
      setTestCaseLoading(false);
    }
  }, [workflow, testCaseCounts, maxMatches]);

  // ── Step 7 wire-up: execute the test suite against the live version ──
  const [suiteExecuting, setSuiteExecuting] = useState(false);
  const handleExecuteSuite = useCallback(async () => {
    const suiteId = workflow?.test_case_suite?.id ?? testCaseSuiteId;
    const lv = workflow?.live_repo_version;
    if (!suiteId || !lv) return;
    setSuiteExecuting(true);
    try {
      const { data } = await api.post(
        `/test-cases/${suiteId}/execute`,
        { version_id: lv.version_id },
      );
      const passed = data.summary?.matches_expected ?? 0;
      const failed = data.summary?.deviates_from_expected ?? 0;
      toast.success(
        failed === 0
          ? `Suite executed: all ${passed.toLocaleString()} matched outcomes are as expected.`
          : `Suite executed: ${passed.toLocaleString()} matched, ${failed.toLocaleString()} deviated.`
      );
      await fetchWorkflow();
    } catch (err: any) {
      toast.error(
        err?.response?.data?.detail || "Failed to execute test suite."
      );
    } finally {
      setSuiteExecuting(false);
    }
  }, [workflow, testCaseSuiteId, fetchWorkflow]);

  // ── Step 5 wire-up: kick off an impact run for this BRD's live version ──
  const [impactRunning, setImpactRunning] = useState(false);
  const handleRunImpact = useCallback(async () => {
    const lv = workflow?.live_repo_version;
    if (!lv) return;
    setImpactRunning(true);
    try {
      const payload: Record<string, any> = {
        repository_id: lv.repository_id,
        candidate_version_id: lv.version_id,
        created_by: "brd-pipeline",
      };
      if (lv.parent_version_id) {
        payload.base_version_id = lv.parent_version_id;
      }
      const { data } = await api.post("/impact-run", payload);
      toast.success(
        `Impact analysis ${data.status === "COMPLETED" ? "complete" : "started"}.`
      );
      // Re-fetch workflow so the stepper picks up the new impact_run
      await fetchWorkflow();
      // Deeplink straight into the impact analysis if it's done
      if (data.status === "COMPLETED" && data.id) {
        router.push(`/impact-runs/${data.id}`);
      }
    } catch (err: any) {
      toast.error(
        err?.response?.data?.detail || "Failed to start impact run."
      );
    } finally {
      setImpactRunning(false);
    }
  }, [workflow, fetchWorkflow, router]);

  // handleExtractRules is defined above

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!brd) return null;

  const fileType = brd.file_type.toUpperCase();

  return (
    <PageTransition>
      <div className="space-y-8">
        <p className="text-xs text-muted-foreground mb-4">
          Dashboard / BRDs / Detail
        </p>
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-4">
            <Button
              variant="ghost"
              size="icon-sm"
              render={<Link href="/brds" />}
            >
              <ArrowLeft className="size-4" />
            </Button>
            <div>
              <div className="flex items-center gap-3">
                <FileText className="size-6 text-blue-500" />
                <h1 className="text-2xl font-bold tracking-tight">
                  <span className="text-gradient">{brd.filename}</span>
                </h1>
                <Badge
                  variant={fileType.includes("PDF") ? "secondary" : "outline"}
                >
                  {fileType.includes("PDF") ? "PDF" : "DOCX"}
                </Badge>
              </div>
              <p className="mt-1 ml-10 text-sm text-muted-foreground">
                Uploaded{" "}
                {new Date(brd.created_at).toLocaleDateString("en-US", {
                  year: "numeric",
                  month: "long",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </p>
            </div>
          </div>
        </div>

        {/* Workflow Stepper */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <Card className="card-elevated p-6 border-border/40">
            <h2 className="mb-6 text-sm font-semibold uppercase tracking-wider text-muted-foreground border-b border-border/40 pb-3">
              Workflow
            </h2>
            <WorkflowStepper
              workflow={workflow}
              onRunPipeline={handleExtractRules}
              running={running}
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
          </Card>
        </motion.div>

        {/* Test Suite Link */}
        {testCaseSuiteId && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
          >
            <Card className="card-elevated p-4 border-border/40">
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  <span className="font-medium text-foreground">{testCaseCount}</span> test cases generated successfully.
                </p>
                <Button variant="outline" size="sm" render={<Link href={`/test-suites/${testCaseSuiteId}`} />}>
                  View Test Suite
                </Button>
              </div>
            </Card>
          </motion.div>
        )}

        {/* Live-repo linkage is now part of the WorkflowStepper above
            (Reconcile / Run Impact steps). The standalone card was
            redundant once the pipeline absorbed those phases. */}

      </div>
    </PageTransition>
  );
}
