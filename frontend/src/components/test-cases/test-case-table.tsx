"use client";

import { Fragment, useEffect, useState } from "react";
import Link from "next/link";
import api from "@/lib/api";
import type { MatchedCustomerPage, TestCase } from "@/lib/types";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronRight, FlaskConical, Loader2 } from "lucide-react";
import { toast } from "sonner";

interface TestCaseTableProps {
  suiteId: string;
  testCases: TestCase[];
  casesByCategory: Record<string, number>;
}

const CATEGORY_COLORS: Record<string, string> = {
  POSITIVE: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
  NEGATIVE: "bg-red-500/10 text-red-500 border-red-500/20",
  BOUNDARY: "bg-amber-500/10 text-amber-500 border-amber-500/20",
  EDGE: "bg-purple-500/10 text-purple-500 border-purple-500/20",
  INTERACTION: "bg-blue-500/10 text-blue-500 border-blue-500/20",
};

type CustomerPageState = MatchedCustomerPage & {
  loadingMore: boolean;
  error: string | null;
};

export function TestCaseTable({ suiteId, testCases, casesByCategory }: TestCaseTableProps) {
  const [filter, setFilter] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [customerPages, setCustomerPages] = useState<Record<string, CustomerPageState>>({});

  const filtered = filter
    ? (testCases ?? []).filter((tc) => tc.category === filter)
    : (testCases ?? []);

  useEffect(() => {
    const initialState: Record<string, CustomerPageState> = {};
    for (const tc of testCases ?? []) {
      const initialCustomers = tc.matched_customers ?? [];
      initialState[tc.id] = {
        items: initialCustomers,
        total: tc.match_count ?? initialCustomers.length,
        limit: initialCustomers.length || 10,
        offset: initialCustomers.length,
        has_more: initialCustomers.length < (tc.match_count ?? initialCustomers.length),
        loadingMore: false,
        error: null,
      };
    }
    setCustomerPages(initialState);
  }, [testCases]);

  const handleLoadMore = async (tc: TestCase) => {
    const current = customerPages[tc.id];
    if (!current || current.loadingMore || !current.has_more) {
      return;
    }

    setCustomerPages((prev) => ({
      ...prev,
      [tc.id]: {
        ...prev[tc.id],
        loadingMore: true,
        error: null,
      },
    }));

    try {
      const { data } = await api.get<MatchedCustomerPage>(
        `/test-cases/${suiteId}/cases/${tc.id}/matched-customers`,
        {
          params: {
            limit: current.limit || 10,
            offset: current.items.length,
          },
        },
      );

      setCustomerPages((prev) => {
        const existing = prev[tc.id];
        const items = [...(existing?.items ?? []), ...(data.items ?? [])];
        return {
          ...prev,
          [tc.id]: {
            items,
            total: data.total,
            limit: data.limit,
            offset: data.offset + data.items.length,
            has_more: data.has_more,
            loadingMore: false,
            error: null,
          },
        };
      });
    } catch {
      setCustomerPages((prev) => ({
        ...prev,
        [tc.id]: {
          ...prev[tc.id],
          loadingMore: false,
          error: "Failed to load more matched customers.",
        },
      }));
      toast.error("Failed to load more matched customers.");
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <FlaskConical className="h-5 w-5" />
            Test Cases ({testCases?.length ?? 0})
          </CardTitle>
        </div>
        <div className="flex flex-wrap gap-2 mt-2">
          <Badge
            variant="outline"
            className={`cursor-pointer ${!filter ? "bg-foreground/10" : ""}`}
            onClick={() => setFilter(null)}
          >
            All ({testCases.length})
          </Badge>
          {Object.entries(casesByCategory).map(([cat, count]) => (
            <Badge
              key={cat}
              variant="outline"
              className={`cursor-pointer ${CATEGORY_COLORS[cat] || ""} ${filter === cat ? "ring-1 ring-offset-1" : ""}`}
              onClick={() => setFilter(filter === cat ? null : cat)}
            >
              {cat} ({count})
            </Badge>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-8"></TableHead>
              <TableHead>Test Case ID</TableHead>
              <TableHead>Description</TableHead>
              <TableHead>Category</TableHead>
              <TableHead>Filter</TableHead>
              <TableHead>Match Count</TableHead>
              <TableHead>Expected Decision</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((tc) => {
              const page = customerPages[tc.id];
              const customers = page?.items ?? tc.matched_customers ?? [];
              const hasMore = page?.has_more ?? customers.length < (tc.match_count ?? customers.length);

              return (
                <Fragment key={tc.test_case_id}>
                  <TableRow
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => setExpandedId(expandedId === tc.test_case_id ? null : tc.test_case_id)}
                  >
                    <TableCell>
                      {expandedId === tc.test_case_id ? (
                        <ChevronDown className="h-4 w-4" />
                      ) : (
                        <ChevronRight className="h-4 w-4" />
                      )}
                    </TableCell>
                    <TableCell className="font-mono text-sm">{tc.test_case_id}</TableCell>
                    <TableCell className="max-w-[250px] truncate">{tc.description}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className={CATEGORY_COLORS[tc.category] || ""}>
                        {tc.category}
                      </Badge>
                    </TableCell>
                    <TableCell className="max-w-[200px] truncate text-xs text-muted-foreground">
                      {tc.filter_description || (tc.filter_logic?.length ? `${tc.filter_logic.length} condition(s)` : "N/A")}
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">{tc.match_count ?? 0}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={
                          tc.expected_outcome?.decision === "APPROVED"
                            ? "bg-emerald-500/10 text-emerald-500"
                            : "bg-red-500/10 text-red-500"
                        }
                      >
                        {tc.expected_outcome?.decision || "N/A"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                  {expandedId === tc.test_case_id && (
                    <TableRow>
                      <TableCell colSpan={7} className="bg-muted/30 p-4">
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <h4 className="font-semibold text-sm mb-2">Filter Conditions</h4>
                            <div className="space-y-1">
                              {(Array.isArray(tc.filter_logic) ? tc.filter_logic : []).map((f, idx) => {
                                let displayValue: string;
                                if (f.operator === "between" && Array.isArray(f.value) && f.value.length === 2) {
                                  displayValue = `${f.value[0]} - ${f.value[1]}`;
                                } else if ((f.operator === "in" || f.operator === "not_in") && Array.isArray(f.value)) {
                                  displayValue = `[${f.value.join(", ")}]`;
                                } else {
                                  displayValue = String(f.value);
                                }
                                return (
                                  <div key={idx} className="flex justify-between text-sm">
                                    <span className="text-muted-foreground">{f.field_name}:</span>
                                    <span className="font-mono">{f.operator} {displayValue}</span>
                                  </div>
                                );
                              })}
                              {(!tc.filter_logic || tc.filter_logic.length === 0) && (
                                <p className="text-xs text-muted-foreground">No filter conditions</p>
                              )}
                            </div>
                          </div>

                          <div>
                            <h4 className="font-semibold text-sm mb-2">Expected Outcome</h4>
                            <div className="space-y-1">
                              {Object.entries(tc.expected_outcome).map(([key, val]) => {
                                let display: string;
                                if (val === null || val === undefined) {
                                  display = "N/A";
                                } else if (Array.isArray(val)) {
                                  display = val.join(", ");
                                } else if (typeof val === "object") {
                                  display = Object.entries(val)
                                    .map(([k, v]) => `${k}: ${v}`)
                                    .join(", ");
                                } else {
                                  display = String(val);
                                }
                                return (
                                  <div key={key} className="flex justify-between text-sm gap-4">
                                    <span className="text-muted-foreground shrink-0">{key}:</span>
                                    <span className="font-mono text-right break-all">
                                      {display}
                                    </span>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        </div>

                        <div className="mt-4">
                          <h4 className="font-semibold text-sm mb-2">
                            Matched Customers ({customers.length}{tc.match_count != null ? ` / ${tc.match_count}` : ""})
                          </h4>
                          {customers.length > 0 ? (
                            <>
                              <Table>
                                <TableHeader>
                                  <TableRow>
                                    <TableHead>Loan Application ID</TableHead>
                                    <TableHead>Decision</TableHead>
                                    <TableHead>Bureau Score</TableHead>
                                    <TableHead>Monthly Income</TableHead>
                                    <TableHead>Match Reason</TableHead>
                                  </TableRow>
                                </TableHeader>
                                <TableBody>
                                  {customers.map((mc) => {
                                    const rp = mc.request_payload as any;
                                    const bureauScore =
                                      rp?.borrower_credit_model?.bureau_credits?.bureau_score ??
                                      rp?.bureau_score ??
                                      null;
                                    const monthlyIncome =
                                      rp?.borrower_credit_model?.customer_inputs?.monthly_income ??
                                      rp?.monthly_income ??
                                      null;
                                    return (
                                      <TableRow key={mc.id}>
                                        <TableCell>
                                          <Link
                                            href={`/loan-records/${mc.id}`}
                                            className="font-mono text-sm text-primary hover:underline"
                                            onClick={(e) => e.stopPropagation()}
                                          >
                                            {mc.loan_application_id}
                                          </Link>
                                        </TableCell>
                                        <TableCell>
                                          <Badge
                                            variant="outline"
                                            className={
                                              mc.response_payload?.decision_status === "APPROVED"
                                                ? "bg-emerald-500/10 text-emerald-500"
                                                : "bg-red-500/10 text-red-500"
                                            }
                                          >
                                            {mc.response_payload?.decision_status || "N/A"}
                                          </Badge>
                                        </TableCell>
                                        <TableCell className="font-mono text-sm">
                                          {bureauScore ?? "N/A"}
                                        </TableCell>
                                        <TableCell className="font-mono text-sm">
                                          {monthlyIncome != null
                                            ? `$${Number(monthlyIncome).toLocaleString()}`
                                            : "N/A"}
                                        </TableCell>
                                        <TableCell className="text-xs text-muted-foreground max-w-[200px] truncate">
                                          {mc.match_reason}
                                        </TableCell>
                                      </TableRow>
                                    );
                                  })}
                                </TableBody>
                              </Table>

                              {page?.error && (
                                <p className="mt-2 text-xs text-destructive">{page.error}</p>
                              )}

                              {hasMore && (
                                <div className="mt-3 flex items-center justify-between gap-3">
                                  <p className="text-xs text-muted-foreground">
                                    Showing {customers.length} of {tc.match_count ?? customers.length} matched customers
                                  </p>
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      void handleLoadMore(tc);
                                    }}
                                    disabled={page?.loadingMore}
                                  >
                                    {page?.loadingMore ? (
                                      <>
                                        <Loader2 className="mr-2 size-4 animate-spin" />
                                        Loading...
                                      </>
                                    ) : (
                                      "Load more"
                                    )}
                                  </Button>
                                </div>
                              )}
                            </>
                          ) : (
                            <p className="text-xs text-muted-foreground">No matched customers</p>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </Fragment>
              );
            })}
            {filtered.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                  No test cases found
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
