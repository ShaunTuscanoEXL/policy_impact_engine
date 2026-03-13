"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import api from "@/lib/api";
import type { Dataset } from "@/lib/types";
import { toast } from "sonner";
import { DataProfile } from "@/components/datasets/data-profile";
import { SampleTable } from "@/components/datasets/sample-table";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Database,
  ArrowLeft,
  Loader2,
  FileSpreadsheet,
  BarChart3,
  Table2,
} from "lucide-react";

export default function DatasetDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchDataset() {
      try {
        const { data } = await api.get(`/datasets/${params.id}`);
        setDataset(data);
      } catch {
        toast.error("Failed to load dataset.");
        router.push("/datasets");
      } finally {
        setLoading(false);
      }
    }
    fetchDataset();
  }, [params.id, router]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!dataset) return null;

  const fileType = dataset.file_type.toUpperCase();
  const columnSchema = dataset.column_schema ?? {};
  const schemaEntries = Object.entries(columnSchema);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start gap-4">
        <Button
          variant="ghost"
          size="icon-sm"
          render={<Link href="/datasets" />}
        >
          <ArrowLeft className="size-4" />
        </Button>
        <div>
          <div className="flex items-center gap-3">
            <Database className="size-6 text-muted-foreground" />
            <h1 className="text-2xl font-bold tracking-tight">
              {dataset.name}
            </h1>
            <Badge variant={fileType.includes("CSV") ? "secondary" : "outline"}>
              {fileType.includes("CSV") ? "CSV" : "JSON"}
            </Badge>
          </div>
          {dataset.description && (
            <p className="mt-1 ml-10 text-sm text-muted-foreground">
              {dataset.description}
            </p>
          )}
          <div className="mt-1 ml-10 flex items-center gap-4 text-sm text-muted-foreground">
            <span>{dataset.row_count.toLocaleString()} rows</span>
            <Separator orientation="vertical" className="h-4" />
            <span>
              Uploaded{" "}
              {new Date(dataset.created_at).toLocaleDateString("en-US", {
                year: "numeric",
                month: "long",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="schema">
        <TabsList>
          <TabsTrigger value="schema">
            <FileSpreadsheet className="size-4" />
            Schema
          </TabsTrigger>
          <TabsTrigger value="profile">
            <BarChart3 className="size-4" />
            Data Profile
          </TabsTrigger>
          <TabsTrigger value="sample">
            <Table2 className="size-4" />
            Sample Data
          </TabsTrigger>
        </TabsList>

        {/* Schema Tab */}
        <TabsContent value="schema">
          <Card>
            {schemaEntries.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <FileSpreadsheet className="size-10 text-muted-foreground/40" />
                <p className="mt-3 text-sm text-muted-foreground">
                  No schema information available.
                </p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Column Name</TableHead>
                    <TableHead>Data Type</TableHead>
                    <TableHead className="text-right">Non-Null Count</TableHead>
                    <TableHead className="text-right">Null Count</TableHead>
                    <TableHead className="text-right">Unique Values</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {schemaEntries.map(([colName, meta]) => (
                    <TableRow key={colName}>
                      <TableCell className="font-medium font-mono text-sm">
                        {colName}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{meta?.dtype ?? meta?.type ?? "unknown"}</Badge>
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {meta?.non_null_count?.toLocaleString() ?? "-"}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {meta?.null_count?.toLocaleString() ?? "-"}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {meta?.unique_values?.toLocaleString() ?? meta?.unique?.toLocaleString() ?? "-"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </Card>
        </TabsContent>

        {/* Data Profile Tab */}
        <TabsContent value="profile">
          <DataProfile dataProfile={dataset.data_profile ?? {}} />
        </TabsContent>

        {/* Sample Data Tab */}
        <TabsContent value="sample">
          <SampleTable sampleData={dataset.sample_data ?? []} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
