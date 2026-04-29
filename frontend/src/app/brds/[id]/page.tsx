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

        {/* Live Rule Repository linkage (Slice 4 wire-up) */}
        {(workflow?.merge_proposal || workflow?.live_repo_version) && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <Card className="card-elevated p-5 border-border/40">
              <div className="space-y-4">
                <div className="flex items-center gap-3">
                  <div className="icon-badge bg-violet-100 dark:bg-violet-900/30">
                    <GitMerge className="size-4 text-violet-600 dark:text-violet-400" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold">Live Rule Repository</p>
                    <p className="text-xs text-muted-foreground">
                      Status of this BRD's proposal against the live US-PERSONAL repo
                    </p>
                  </div>
                </div>

                {workflow.merge_proposal && (
                  <div className="flex flex-wrap items-center gap-3 rounded-md border border-border/40 bg-muted/30 p-3">
                    <div className="flex flex-1 flex-wrap items-center gap-2 text-xs">
                      <span className="text-muted-foreground">Proposal</span>
                      <Badge
                        variant={
                          workflow.merge_proposal.status === "APPLIED"
                            ? "default"
                            : workflow.merge_proposal.status === "PENDING"
                              ? "secondary"
                              : "outline"
                        }
                      >
                        {workflow.merge_proposal.status}
                      </Badge>
                      {workflow.merge_proposal.summary && (
                        <span className="text-muted-foreground">
                          · {workflow.merge_proposal.summary}
                        </span>
                      )}
                      <span className="text-muted-foreground">
                        · base v{workflow.merge_proposal.base_version}
                      </span>
                      {workflow.merge_proposal.decided_by && (
                        <span className="text-muted-foreground">
                          · decided by{" "}
                          <span className="font-medium text-foreground">
                            {workflow.merge_proposal.decided_by}
                          </span>
                        </span>
                      )}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      render={
                        <Link
                          href={`/merge-workbench/${workflow.merge_proposal.id}`}
                        />
                      }
                    >
                      Open Workbench
                      <ArrowRight className="ml-1.5 size-3.5" />
                    </Button>
                  </div>
                )}

                {workflow.live_repo_version && (
                  <div className="flex flex-wrap items-center gap-3 rounded-md border border-border/40 bg-muted/30 p-3">
                    <div className="flex flex-1 flex-wrap items-center gap-2 text-xs">
                      <GitBranch className="size-3.5 text-amber-500" />
                      <span className="text-muted-foreground">Applied as</span>
                      <Badge variant="default">
                        v{workflow.live_repo_version.version_number}
                      </Badge>
                      {workflow.live_repo_version.summary && (
                        <span className="text-muted-foreground">
                          · {workflow.live_repo_version.summary}
                        </span>
                      )}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      render={
                        <Link
                          href={`/live-repo/${workflow.live_repo_version.repository_id}`}
                        />
                      }
                    >
                      View Repository
                      <ArrowRight className="ml-1.5 size-3.5" />
                    </Button>
                  </div>
                )}
              </div>
            </Card>
          </motion.div>
        )}

      </div>
    </PageTransition>
  );
}
