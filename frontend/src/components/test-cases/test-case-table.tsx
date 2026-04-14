"use client";

import { Fragment, useState } from "react";
import Link from "next/link";
import { TestCase } from "@/lib/types";
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
import { ChevronDown, ChevronRight, FlaskConical } from "lucide-react";

interface TestCaseTableProps {
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

export function TestCaseTable({ testCases, casesByCategory }: TestCaseTableProps) {
  const [filter, setFilter] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const filtered = filter
    ? (testCases ?? []).filter((tc) => tc.category === filter)
    : (testCases ?? []);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <FlaskConical className="h-5 w-5" />
            Test Cases ({testCases?.length ?? 0})
          </CardTitle>
        </div>
        {/* Category filter badges */}
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
            {filtered.map((tc) => (
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
                        {/* Left: Filter Conditions */}
                        <div>
                          <h4 className="font-semibold text-sm mb-2">Filter Conditions</h4>
                          <div className="space-y-1">
                            {(Array.isArray(tc.filter_logic) ? tc.filter_logic : []).map((f, idx) => {
                              let displayValue: string;
                              if (f.operator === "between" && Array.isArray(f.value) && f.value.length === 2) {
                                displayValue = `${f.value[0]} – ${f.value[1]}`;
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

                        {/* Right: Expected Outcome */}
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
                                // Render nested objects like rule_a/rule_b inline
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

                      {/* Below: Matched Customers */}
                      {tc.matched_customers && tc.matched_customers.length > 0 && (
                        <div className="mt-4">
                          <h4 className="font-semibold text-sm mb-2">
                            Matched Customers ({tc.matched_customers.length})
                          </h4>
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
                              {tc.matched_customers.map((mc) => (
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
                                    {mc.request_payload?.bureau_score ?? "N/A"}
                                  </TableCell>
                                  <TableCell className="font-mono text-sm">
                                    {mc.request_payload?.monthly_income != null
                                      ? `$${Number(mc.request_payload.monthly_income).toLocaleString()}`
                                      : "N/A"}
                                  </TableCell>
                                  <TableCell className="text-xs text-muted-foreground max-w-[200px] truncate">
                                    {mc.match_reason}
                                  </TableCell>
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                )}
              </Fragment>
            ))}
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
