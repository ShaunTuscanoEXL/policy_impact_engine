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
  Settings2,
} from "lucide-react";
import { MappingForm } from "@/components/datasets/mapping-form";
import { PageTransition } from "@/components/page-transition";
import { motion } from "framer-motion";

export default function DatasetDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [loading, setLoading] = useState(true);
  const [detectedMapping, setDetectedMapping] = useState<Record<string, any> | null>(null);
  const [mappingLoading, setMappingLoading] = useState(false);
  const [saving, setSaving] = useState(false);

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

  async function fetchDetectedMapping() {
    setMappingLoading(true);
    try {
      const { data } = await api.get(`/datasets/${params.id}/detect-mapping`);
      setDetectedMapping(data);
    } catch {
      toast.error("Failed to detect column mapping.");
    } finally {
      setMappingLoading(false);
    }
  }

  async function handleSaveMapping(mapping: Record<string, any>, config: Record<string, any>) {
    setSaving(true);
    try {
      await api.put(`/datasets/${params.id}/mapping`, {
        column_mapping: mapping,
        baseline_config: config,
      });
      toast.success("Column mapping saved successfully.");
      // Refresh dataset to get updated mapping
      const { data } = await api.get(`/datasets/${params.id}`);
      setDataset(data);
    } catch {
      toast.error("Failed to save column mapping.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!dataset) return null;

  const fileType = (dataset.file_type ?? "unknown").toUpperCase();
  const columnSchema = dataset.column_schema ?? {};
  const schemaEntries = Object.entries(columnSchema);

  return (
    <PageTransition>
    <div className="space-y-8">
      <p className="text-xs text-muted-foreground mb-4">Dashboard / Datasets / Detail</p>
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
            <div className="icon-badge bg-emerald-100 dark:bg-emerald-900/30">
              <Database className="size-5 text-emerald-600 dark:text-emerald-400" />
            </div>
            <h1 className="text-2xl font-bold tracking-tight">
              <span className="text-gradient">{dataset.name}</span>
            </h1>
            <Badge variant={fileType.includes("CSV") ? "secondary" : "outline"}>
              {fileType.includes("CSV") ? "CSV" : "JSON"}
            </Badge>
            <Badge variant={dataset.column_mapping ? "default" : "outline"}
                   className={dataset.column_mapping ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400" : "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"}>
              {dataset.column_mapping ? "Mapped" : "Unmapped"}
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
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
      <Tabs defaultValue="schema" onValueChange={(v) => {
        if (v === "mapping" && !detectedMapping) fetchDetectedMapping();
      }}>
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
          <TabsTrigger value="mapping">
            <Settings2 className="size-4" />
            Column Mapping
          </TabsTrigger>
        </TabsList>

        {/* Schema Tab */}
        <TabsContent value="schema">
          <Card className="border-border/40 shadow-sm">
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

        {/* Column Mapping Tab */}
        <TabsContent value="mapping">
          {mappingLoading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="size-6 animate-spin text-muted-foreground" />
            </div>
          ) : detectedMapping ? (
            <MappingForm
              columns={Object.keys(dataset.column_schema ?? {})}
              detectedMapping={detectedMapping}
              savedMapping={dataset.column_mapping}
              savedConfig={dataset.baseline_config}
              onSave={handleSaveMapping}
              saving={saving}
            />
          ) : (
            <Card className="border-border/40 shadow-sm">
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <Settings2 className="size-10 text-muted-foreground/40" />
                <p className="mt-3 text-sm text-muted-foreground">
                  Click to auto-detect column mapping
                </p>
                <Button className="mt-4" onClick={fetchDetectedMapping}>
                  Detect Columns
                </Button>
              </div>
            </Card>
          )}
        </TabsContent>
      </Tabs>
      </motion.div>
    </div>
    </PageTransition>
  );
}
