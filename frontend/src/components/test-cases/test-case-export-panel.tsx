"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Download, FileJson, FileSpreadsheet } from "lucide-react";
import api from "@/lib/api";
import { toast } from "sonner";

interface TestCaseExportPanelProps {
  suiteId: string;
  totalCases: number;
  casesByCategory: Record<string, number>;
}

export function TestCaseExportPanel({ suiteId, totalCases, casesByCategory }: TestCaseExportPanelProps) {
  const handleExport = async (format: "csv" | "json") => {
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

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Download className="h-5 w-5" />
          Export Test Suite
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-4">
          <div className="text-sm text-muted-foreground">
            <span className="font-medium text-foreground">{totalCases}</span> test cases across{" "}
            {Object.keys(casesByCategory).length} categories ready for export.
          </div>
          <div className="flex gap-3">
            <Button variant="outline" onClick={() => handleExport("csv")} className="flex-1">
              <FileSpreadsheet className="h-4 w-4 mr-2" />
              Export CSV
            </Button>
            <Button variant="outline" onClick={() => handleExport("json")} className="flex-1">
              <FileJson className="h-4 w-4 mr-2" />
              Export JSON
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
