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

interface SegmentData {
  total: number;
  affected: number;
  affected_pct: number;
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
      <Card className="border-border/50 shadow-sm">
        <CardHeader>
          <CardTitle>Segment Breakdown</CardTitle>
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
    <Card className="border-border/50 shadow-sm">
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
                    <TableHead>Segment</TableHead>
                    <TableHead className="text-right">Total</TableHead>
                    <TableHead className="text-right">Affected</TableHead>
                    <TableHead className="text-right">Affected %</TableHead>
                    <TableHead className="text-right">Impact</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {Object.entries(segmentBreakdown[tab.key]).map(
                    ([segment, data]) => (
                      <TableRow key={segment}>
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
