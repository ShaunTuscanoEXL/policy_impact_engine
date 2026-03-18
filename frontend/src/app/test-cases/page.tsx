"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import api from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { FlaskConical, Loader2, AlertCircle } from "lucide-react";
import { PageTransition } from "@/components/page-transition";

interface TestCaseSuiteListItem {
  id: string;
  rule_set_id: string;
  rule_set_name: string | null;
  total_cases: number;
  cases_by_category: Record<string, number>;
  created_at: string;
}

const CATEGORY_COLORS: Record<string, string> = {
  POSITIVE: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
  NEGATIVE: "bg-red-500/10 text-red-500 border-red-500/20",
  BOUNDARY: "bg-amber-500/10 text-amber-500 border-amber-500/20",
  EDGE: "bg-purple-500/10 text-purple-500 border-purple-500/20",
  INTERACTION: "bg-blue-500/10 text-blue-500 border-blue-500/20",
};

export default function TestCasesListPage() {
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
        <p className="text-xs text-muted-foreground mb-4">Dashboard / Test Cases</p>

        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold tracking-tight">
              <span className="text-gradient">Test Case Suites</span>
            </h1>
            <p className="text-sm text-muted-foreground">
              All generated test case suites across BRDs and rule sets
            </p>
          </div>
        </div>

        {suites.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-16 gap-3">
              <FlaskConical className="h-10 w-10 text-muted-foreground" />
              <p className="text-lg text-muted-foreground">No test case suites yet</p>
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
                    <TableHead>Rule Set</TableHead>
                    <TableHead>Total Cases</TableHead>
                    <TableHead>Categories</TableHead>
                    <TableHead>Created</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {suites.map((suite) => (
                    <TableRow key={suite.id} className="cursor-pointer hover:bg-muted/50">
                      <TableCell>
                        <Link
                          href={`/test-cases/${suite.id}`}
                          className="font-medium text-primary hover:underline"
                        >
                          {suite.rule_set_name || suite.rule_set_id.slice(0, 8)}
                        </Link>
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
                      <TableCell className="text-muted-foreground">
                        {new Date(suite.created_at).toLocaleDateString("en-US", {
                          month: "short",
                          day: "numeric",
                          year: "numeric",
                        })}
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
