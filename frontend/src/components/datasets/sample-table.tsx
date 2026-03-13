"use client";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Table2 } from "lucide-react";

interface SampleTableProps {
  sampleData: Record<string, any>[];
}

export function SampleTable({ sampleData }: SampleTableProps) {
  if (!sampleData || sampleData.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <Table2 className="size-10 text-muted-foreground/40" />
        <p className="mt-3 text-sm text-muted-foreground">
          No sample data available for this dataset.
        </p>
      </div>
    );
  }

  const columns = Object.keys(sampleData[0]);
  const rows = sampleData.slice(0, 10);

  return (
    <div className="overflow-x-auto rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-12 text-center">#</TableHead>
            {columns.map((col) => (
              <TableHead key={col} className="whitespace-nowrap">
                {col}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row, i) => (
            <TableRow key={i}>
              <TableCell className="text-center text-muted-foreground">
                {i + 1}
              </TableCell>
              {columns.map((col) => (
                <TableCell key={col} className="whitespace-nowrap font-mono text-xs">
                  {row[col] === null || row[col] === undefined
                    ? <span className="text-muted-foreground italic">null</span>
                    : String(row[col])}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
