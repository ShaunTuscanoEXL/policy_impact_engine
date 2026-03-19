"use client";

import { Fragment, useState } from "react";
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
    ? testCases.filter((tc) => tc.category === filter)
    : testCases;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <FlaskConical className="h-5 w-5" />
            Test Cases ({testCases.length})
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
              <TableHead>Source Rules</TableHead>
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
                  <TableCell className="max-w-[300px] truncate">{tc.description}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className={CATEGORY_COLORS[tc.category] || ""}>
                      {tc.category}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {tc.source_rule_ids.join(", ")}
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
                    <TableCell colSpan={6} className="bg-muted/30 p-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <h4 className="font-semibold text-sm mb-2">Filter Conditions</h4>
                          <div className="space-y-1">
                            {(Array.isArray(tc.filter_logic) ? tc.filter_logic : []).map((f: any, idx: number) => (
                              <div key={idx} className="flex justify-between text-sm">
                                <span className="text-muted-foreground">{f.field_name}:</span>
                                <span className="font-mono">{f.operator} {String(f.value)}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                        <div>
                          <h4 className="font-semibold text-sm mb-2">Expected Outcome</h4>
                          <div className="space-y-1">
                            {Object.entries(tc.expected_outcome).map(([key, val]) => (
                              <div key={key} className="flex justify-between text-sm">
                                <span className="text-muted-foreground">{key}:</span>
                                <span className="font-mono">
                                  {Array.isArray(val) ? val.join(", ") : String(val)}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    </TableCell>
                  </TableRow>
                )}
              </Fragment>
            ))}
            {filtered.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
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
