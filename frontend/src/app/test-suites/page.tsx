"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import api from "@/lib/api";
import type { TestCaseSuiteListItem } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { FlaskConical, Loader2, AlertCircle, FileSpreadsheet, FileJson, FileText, CheckCircle, XCircle, Minus } from "lucide-react";
import { cn } from "@/lib/utils";
import { PageTransition } from "@/components/page-transition";
import { toast } from "sonner";

const CATEGORY_COLORS: Record<string, string> = {
  POSITIVE: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
  NEGATIVE: "bg-red-500/10 text-red-500 border-red-500/20",
  BOUNDARY: "bg-amber-500/10 text-amber-500 border-amber-500/20",
  EDGE: "bg-purple-500/10 text-purple-500 border-purple-500/20",
  INTERACTION: "bg-blue-500/10 text-blue-500 border-blue-500/20",
};

export default function TestSuitesListPage() {
  const [suites, setSuites] = useState<TestCaseSuiteListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchSuites() {
      try {
        const res = await api.get<TestCaseSuiteListItem[]>("/test-cases");
        setSuites(res.data);
      } catch (err: any) {
        setError(err?.response?.data?.detail || "Failed to load test case suites.");
      } finally {
        setLoading(false);
      }
    }
    fetchSuites();
  }, []);

  const handleExport = async (suiteId: string, format: "csv" | "json") => {
    try {
      const response = await api.get(`/test-cases/${suiteId}/export/${format}`, {
        responseType: "blob",
      });
      const blob = new Blob([response.data]);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `test_cases_${suiteId}.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success(`Test cases exported as ${format.toUpperCase()}`);
    } catch {
      toast.error(`Failed to export test cases as ${format.toUpperCase()}`);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <AlertCircle className="h-10 w-10 text-destructive" />
        <p className="text-lg text-muted-foreground">{error}</p>
      </div>
    );
  }

  return (
    <PageTransition>
      <div className="space-y-6">
        <p className="text-xs text-muted-foreground mb-4">Dashboard / Test Suites</p>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="icon-badge bg-purple-100 dark:bg-purple-900/30">
              <FlaskConical className="size-5 text-purple-600 dark:text-purple-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight">
                <span className="text-gradient">Test Suites</span>
              </h1>
              <p className="text-sm text-muted-foreground">
                All generated test case suites across BRDs and rule sets
              </p>
            </div>
          </div>
        </div>

        {suites.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-16 gap-3">
              <FlaskConical className="h-10 w-10 text-muted-foreground" />
              <p className="text-lg text-muted-foreground">No test suites yet</p>
              <p className="text-sm text-muted-foreground">
                Generate test cases from a BRD&apos;s rule set to see them here
              </p>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FlaskConical className="h-5 w-5" />
                {suites.length} Suite{suites.length !== 1 ? "s" : ""}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>BRD</TableHead>
                    <TableHead>Rule Set Name</TableHead>
                    <TableHead>Total Cases</TableHead>
                    <TableHead>Categories</TableHead>
                    <TableHead>Last Execution</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead className="text-right">Export</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {suites.map((suite) => (
                    <TableRow key={suite.id} className="cursor-pointer hover:bg-muted/50">
                      <TableCell>
                        {suite.brd_id ? (
                          <Link
                            href={`/brds/${suite.brd_id}`}
                            className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
                          >
                            <FileText className="h-3.5 w-3.5" />
                            {suite.brd_filename || "View BRD"}
                          </Link>
                        ) : (
                          <span className="text-muted-foreground text-sm">—</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Link
                            href={`/test-suites/${suite.id}`}
                            className="font-medium text-primary hover:underline"
                          >
                            {suite.rule_set_name || suite.rule_set_id.slice(0, 8)}
                          </Link>
                          {suite.is_stale && (
                            <span
                              title="The source rule_set has been edited after this suite was generated. Re-generate to refresh test cases."
                              className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-700 ring-1 ring-inset ring-amber-500/30 dark:text-amber-300"
                            >
                              <AlertCircle className="size-3" />
                              STALE
                            </span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary">{suite.total_cases} cases</Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
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
                      </TableCell>
                      <TableCell>
                        {suite.last_execution ? (
                          (() => {
                            const exec = suite.last_execution;
                            const pct = Math.round(exec.pass_rate * 100);
                            const isGood = pct >= 95;
                            const isMid = pct >= 80;
                            const tone = isGood
                              ? "bg-emerald-500/10 text-emerald-700 ring-emerald-500/30 dark:text-emerald-300"
                              : isMid
                                ? "bg-amber-500/10 text-amber-700 ring-amber-500/30 dark:text-amber-300"
                                : "bg-red-500/10 text-red-700 ring-red-500/30 dark:text-red-300";
                            const Icon = isGood ? CheckCircle : isMid ? AlertCircle : XCircle;
                            return (
                              <div className="space-y-0.5">
                                <span
                                  className={cn(
                                    "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ring-1 ring-inset",
                                    tone,
                                  )}
                                  title={`${exec.passing} / ${exec.total_assertions} assertions passing`}
                                >
                                  <Icon className="size-3" />
                                  {pct}% PASS
                                </span>
                                <div className="text-[10px] text-muted-foreground">
                                  vs v{exec.version_number} · {exec.passing}/
                                  {exec.total_assertions}
                                </div>
                              </div>
                            );
                          })()
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[10px] italic text-muted-foreground">
                            <Minus className="size-3" />
                            never executed
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {new Date(suite.created_at).toLocaleDateString("en-US", {
                          month: "short",
                          day: "numeric",
                          year: "numeric",
                        })}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleExport(suite.id, "csv");
                            }}
                            title="Export CSV"
                          >
                            <FileSpreadsheet className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleExport(suite.id, "json");
                            }}
                            title="Export JSON"
                          >
                            <FileJson className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </div>
    </PageTransition>
  );
}
