"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import api from "@/lib/api";
import type { TestCaseSuite } from "@/lib/types";
import { buttonVariants } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ArrowLeft, Loader2, AlertCircle } from "lucide-react";
import { TestCaseTable } from "@/components/test-cases/test-case-table";
import { TestCaseExportPanel } from "@/components/test-cases/test-case-export-panel";
import { SuiteExecutionPanel } from "@/components/test-cases/suite-execution-panel";
import { PageTransition } from "@/components/page-transition";
import { PipelineContextBar } from "@/components/brds/pipeline/pipeline-context-bar";

const CATEGORY_COLORS: Record<string, string> = {
  POSITIVE: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
  NEGATIVE: "bg-red-500/10 text-red-500 border-red-500/20",
  BOUNDARY: "bg-amber-500/10 text-amber-500 border-amber-500/20",
  EDGE: "bg-purple-500/10 text-purple-500 border-purple-500/20",
  INTERACTION: "bg-blue-500/10 text-blue-500 border-blue-500/20",
};

export default function TestSuiteDetailPage() {
  const params = useParams<{ suiteId: string }>();
  const suiteId = params.suiteId;

  const [suite, setSuite] = useState<TestCaseSuite | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchSuite() {
      try {
        const res = await api.get<TestCaseSuite>(`/test-cases/${suiteId}`);
        setSuite(res.data);
      } catch (err: any) {
        setError(err?.response?.data?.detail || "Failed to load test case suite.");
      } finally {
        setLoading(false);
      }
    }
    fetchSuite();
  }, [suiteId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !suite) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <AlertCircle className="h-10 w-10 text-destructive" />
        <p className="text-lg text-muted-foreground">{error || "Suite not found."}</p>
        <Link href="/test-suites" className={buttonVariants({ variant: "outline" })}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Test Suites
        </Link>
      </div>
    );
  }

  return (
    <PageTransition>
      <PipelineContextBar />
      <div className="space-y-6">
        <p className="text-xs text-muted-foreground mb-4">
          Dashboard / <Link href="/test-suites" className="hover:underline">Test Suites</Link> / Detail
        </p>

        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight">
                <span className="text-gradient">
                  {suite.rule_set_name || `Suite ${suiteId.slice(0, 8)}`}
                </span>
              </h1>
              {suite.is_stale && (
                <span
                  title="The source rule_set has been edited after this suite was generated. Re-generate to refresh test cases against the current rules."
                  className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-700 ring-1 ring-inset ring-amber-500/30 dark:text-amber-300"
                >
                  <AlertCircle className="size-3" />
                  STALE — rule_set changed
                </span>
              )}
            </div>
            <p className="text-sm text-muted-foreground">
              {suite.total_cases} test cases &middot; Created{" "}
              {new Date(suite.created_at).toLocaleDateString("en-US", {
                year: "numeric",
                month: "long",
                day: "numeric",
              })}
              {suite.is_stale && suite.rule_set_last_modified_at && (
                <>
                  {" "}&middot; <span className="text-amber-700 dark:text-amber-300">
                    Rule set last edited{" "}
                    {new Date(suite.rule_set_last_modified_at).toLocaleDateString("en-US", {
                      year: "numeric",
                      month: "long",
                      day: "numeric",
                    })}
                  </span>
                </>
              )}
            </p>
            <div className="flex flex-wrap gap-1 mt-2">
              {Object.entries(suite.cases_by_category).map(([cat, count]) => (
                <Badge
                  key={cat}
                  variant="outline"
                  className={`text-xs ${CATEGORY_COLORS[cat] || ""}`}
                >
                  {cat} ({count})
                </Badge>
              ))}
            </div>
          </div>
          <Link href="/test-suites" className={buttonVariants({ variant: "outline" })}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Test Suites
          </Link>
        </div>

        <Separator />

        {/* Export Panel */}
        <TestCaseExportPanel
          suiteId={suite.id}
          totalCases={suite.total_cases}
          casesByCategory={suite.cases_by_category}
        />

        {/* Latest scenario-test execution result, if any */}
        {suite.last_execution_report && (
          <SuiteExecutionPanel
            report={suite.last_execution_report}
            executedAt={suite.last_executed_at ?? null}
          />
        )}

        {/* Test Case Table */}
        <TestCaseTable
          testCases={suite.test_cases}
          casesByCategory={suite.cases_by_category}
        />
      </div>
    </PageTransition>
  );
}
