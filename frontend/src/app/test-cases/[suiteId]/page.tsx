"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import api from "@/lib/api";
import type { TestCaseSuite } from "@/lib/types";
import { buttonVariants } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ArrowLeft, Loader2, AlertCircle } from "lucide-react";
import { TestCaseTable } from "@/components/test-cases/test-case-table";
import { TestCaseExportPanel } from "@/components/test-cases/test-case-export-panel";
import { PageTransition } from "@/components/page-transition";

interface SuiteResponse extends TestCaseSuite {
  rule_set_name: string | null;
}

export default function TestCaseSuiteDetailPage() {
  const params = useParams<{ suiteId: string }>();
  const suiteId = params.suiteId;

  const [suite, setSuite] = useState<SuiteResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchSuite() {
      try {
        const res = await api.get<SuiteResponse>(`/test-cases/${suiteId}`);
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
        <Link href="/test-cases" className={buttonVariants({ variant: "outline" })}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Test Cases
        </Link>
      </div>
    );
  }

  return (
    <PageTransition>
      <div className="space-y-6">
        <p className="text-xs text-muted-foreground mb-4">
          Dashboard / <Link href="/test-cases" className="hover:underline">Test Cases</Link> / Detail
        </p>

        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold tracking-tight">
              <span className="text-gradient">
                {suite.rule_set_name || `Suite ${suiteId.slice(0, 8)}`}
              </span>
            </h1>
            <p className="text-sm text-muted-foreground">
              {suite.total_cases} test cases &middot; Created{" "}
              {new Date(suite.created_at).toLocaleDateString("en-US", {
                year: "numeric",
                month: "long",
                day: "numeric",
              })}
            </p>
          </div>
          <Link href="/test-cases" className={buttonVariants({ variant: "outline" })}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Test Cases
          </Link>
        </div>

        <Separator />

        {/* Export Panel */}
        <TestCaseExportPanel
          suiteId={suite.id}
          totalCases={suite.total_cases}
          casesByCategory={suite.cases_by_category}
        />

        {/* Test Case Table */}
        <TestCaseTable
          testCases={suite.test_cases}
          casesByCategory={suite.cases_by_category}
        />
      </div>
    </PageTransition>
  );
}
