"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PieChart } from "lucide-react";

interface SegmentData {
  total: number;
  affected: number;
  affected_pct: number;
  exposure_delta?: number;
  interest_income_delta?: number;
}

interface SegmentBreakdown {
  [segment: string]: SegmentData;
}

interface SegmentTableProps {
  segmentBreakdown: Record<string, SegmentBreakdown>;
}

const SEGMENT_TABS: { key: string; label: string }[] = [
  { key: "by_bureau_score", label: "Bureau Score" },
  { key: "by_income", label: "Income" },
  { key: "by_city_tier", label: "City Tier" },
  { key: "by_employment_type", label: "Employment Type" },
];

export function SegmentTable({ segmentBreakdown }: SegmentTableProps) {
  const availableTabs = SEGMENT_TABS.filter(
    (tab) => segmentBreakdown[tab.key] && Object.keys(segmentBreakdown[tab.key]).length > 0
  );

  if (availableTabs.length === 0) {
    return (
      <Card className="card-elevated border-border/40">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <PieChart className="size-5 text-violet-500" />
            Segment Breakdown
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            No segment breakdown data available.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="card-elevated border-border/40">
      <CardHeader>
        <CardTitle>Segment Breakdown</CardTitle>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue={availableTabs[0].key}>
          <TabsList>
            {availableTabs.map((tab) => (
              <TabsTrigger key={tab.key} value={tab.key}>
                {tab.label}
              </TabsTrigger>
            ))}
          </TabsList>
          {availableTabs.map((tab) => (
            <TabsContent key={tab.key} value={tab.key}>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-violet-500/20">Segment</TableHead>
                    <TableHead className="text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-violet-500/20">Total</TableHead>
                    <TableHead className="text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-violet-500/20">Affected</TableHead>
                    <TableHead className="text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-violet-500/20">Affected %</TableHead>
                    <TableHead className="text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-violet-500/20">Exposure Δ</TableHead>
                    <TableHead className="text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-violet-500/20">Interest Δ</TableHead>
                    <TableHead className="text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-violet-500/20">Impact</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {Object.entries(segmentBreakdown[tab.key]).map(
                    ([segment, data]) => (
                      <TableRow key={segment} className="cursor-pointer transition-colors duration-150 hover:bg-accent/50">
                        <TableCell className="font-medium">{segment}</TableCell>
                        <TableCell className="text-right">
                          {data.total}
                        </TableCell>
                        <TableCell className="text-right">
                          {data.affected}
                        </TableCell>
                        <TableCell className="text-right">
                          {(data.affected_pct ?? 0).toFixed(1)}%
                        </TableCell>
                        <TableCell className="text-right">
                          <span className={
                            (data.exposure_delta ?? 0) > 0
                              ? "text-green-600"
                              : (data.exposure_delta ?? 0) < 0
                                ? "text-red-600"
                                : "text-muted-foreground"
                          }>
                            {formatCompact(data.exposure_delta ?? 0)}
                          </span>
                        </TableCell>
                        <TableCell className="text-right">
                          <span className={
                            (data.interest_income_delta ?? 0) > 0
                              ? "text-green-600"
                              : (data.interest_income_delta ?? 0) < 0
                                ? "text-red-600"
                                : "text-muted-foreground"
                          }>
                            {formatCompact(data.interest_income_delta ?? 0)}
                          </span>
                        </TableCell>
                        <TableCell className="text-right">
                          <span
                            className={
                              data.affected_pct > 30
                                ? "text-red-600"
                                : data.affected_pct > 0
                                  ? "text-amber-600"
                                  : "text-muted-foreground"
                            }
                          >
                            {data.affected_pct > 30 ? "High" : data.affected_pct > 0 ? "Medium" : "None"}
                          </span>
                        </TableCell>
                      </TableRow>
                    )
                  )}
                </TableBody>
              </Table>
            </TabsContent>
          ))}
        </Tabs>
      </CardContent>
    </Card>
  );
}

function formatCompact(value: number): string {
  const abs = Math.abs(value);
  const prefix = value >= 0 ? "+" : "-";
  if (abs >= 1_000_000) return `${prefix}$${(abs / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${prefix}$${(abs / 1_000).toFixed(1)}K`;
  if (abs === 0) return "$0";
  return `${prefix}$${abs.toFixed(0)}`;
}
