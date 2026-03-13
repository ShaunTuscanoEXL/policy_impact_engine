"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import api from "@/lib/api";
import type { BrdDocument, Dataset, PipelineRunResponse } from "@/lib/types";
import { toast } from "sonner";
import {
  ProcessingStatus,
  type PipelineStep,
} from "@/components/brds/processing-status";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogClose,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  FileText,
  ArrowLeft,
  Loader2,
  Play,
} from "lucide-react";
import { PageTransition } from "@/components/page-transition";
import { motion } from "framer-motion";

export default function BrdDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [brd, setBrd] = useState<BrdDocument | null>(null);
  const [loading, setLoading] = useState(true);

  // Pipeline dialog state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<string>("");
  const [autoApprove, setAutoApprove] = useState(false);
  const [running, setRunning] = useState(false);
  const [pipelineResult, setPipelineResult] =
    useState<PipelineRunResponse | null>(null);

  // Pipeline steps
  const [pipelineSteps, setPipelineSteps] = useState<PipelineStep[]>([
    { label: "Upload", status: "completed" },
    { label: "Parsing", status: "pending" },
    { label: "Extracting Rules", status: "pending" },
    { label: "Validating", status: "pending" },
    { label: "Ready for Review", status: "pending" },
  ]);

  useEffect(() => {
    async function fetchBrd() {
      try {
        const { data } = await api.get(`/brds/${params.id}`);
        setBrd(data);
      } catch {
        toast.error("Failed to load BRD document.");
        router.push("/brds");
      } finally {
        setLoading(false);
      }
    }
    fetchBrd();
  }, [params.id, router]);

  const loadDatasets = useCallback(async () => {
    try {
      const { data } = await api.get("/datasets");
      setDatasets(data);
    } catch {
      toast.error("Failed to load datasets.");
    }
  }, []);

  const handleOpenDialog = useCallback(() => {
    loadDatasets();
    setDialogOpen(true);
  }, [loadDatasets]);

  const updateSteps = useCallback(
    (activeIndex: number) => {
      setPipelineSteps((prev) =>
        prev.map((step, i) => ({
          ...step,
          status:
            i < activeIndex
              ? "completed"
              : i === activeIndex
              ? "active"
              : "pending",
        }))
      );
    },
    []
  );

  const handleRunPipeline = useCallback(async () => {
    if (!selectedDataset) {
      toast.error("Please select a dataset.");
      return;
    }

    setRunning(true);
    setPipelineResult(null);
    setDialogOpen(false);

    try {
      // Simulate step progression
      updateSteps(1); // Parsing
      await new Promise((r) => setTimeout(r, 500));

      updateSteps(2); // Extracting Rules

      const { data } = await api.post("/pipeline/run", {
        brd_id: params.id,
        dataset_id: selectedDataset,
        auto_approve: autoApprove,
      });

      updateSteps(3); // Validating
      await new Promise((r) => setTimeout(r, 500));

      updateSteps(4); // Ready for Review
      setPipelineResult(data);
      toast.success(
        `Pipeline completed. ${data.rules_extracted ?? 0} rules extracted.`
      );
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Pipeline run failed.");
      setPipelineSteps((prev) =>
        prev.map((step) =>
          step.status === "active" ? { ...step, status: "pending" } : step
        )
      );
    } finally {
      setRunning(false);
    }
  }, [selectedDataset, autoApprove, params.id, updateSteps]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!brd) return null;

  const fileType = brd.file_type.toUpperCase();

  return (
    <PageTransition>
    <div className="space-y-8">
      <p className="text-xs text-muted-foreground mb-4">Dashboard / BRDs / Detail</p>
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-4">
          <Button
            variant="ghost"
            size="icon-sm"
            render={<Link href="/brds" />}
          >
            <ArrowLeft className="size-4" />
          </Button>
          <div>
            <div className="flex items-center gap-3">
              <FileText className="size-6 text-muted-foreground" />
              <h1 className="text-2xl font-semibold tracking-tight">
                {brd.filename}
              </h1>
              <Badge variant={fileType.includes("PDF") ? "secondary" : "outline"}>
                {fileType.includes("PDF") ? "PDF" : "DOCX"}
              </Badge>
            </div>
            <p className="mt-1 ml-10 text-sm text-muted-foreground">
              Uploaded{" "}
              {new Date(brd.created_at).toLocaleDateString("en-US", {
                year: "numeric",
                month: "long",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </p>
          </div>
        </div>

        {/* Run Pipeline Button */}
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger
            render={
              <Button disabled={running} onClick={handleOpenDialog} />
            }
          >
            {running ? (
              <Loader2 className="mr-2 size-4 animate-spin" />
            ) : (
              <Play className="mr-2 size-4" />
            )}
            Run Pipeline
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Run Pipeline</DialogTitle>
              <DialogDescription>
                Select a dataset and configure options to run the extraction
                pipeline on this BRD.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-2">
              <div className="space-y-2">
                <label className="text-sm font-medium">Dataset</label>
                <Select
                  value={selectedDataset}
                  onValueChange={(val) => setSelectedDataset(val ?? "")}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select a dataset..." />
                  </SelectTrigger>
                  <SelectContent>
                    {datasets.length === 0 ? (
                      <SelectItem value="_none" disabled>
                        No datasets available
                      </SelectItem>
                    ) : (
                      datasets.map((ds) => (
                        <SelectItem key={ds.id} value={ds.id}>
                          {ds.name}
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="auto-approve"
                  checked={autoApprove}
                  onChange={(e) => setAutoApprove(e.target.checked)}
                  className="size-4 rounded border-input"
                />
                <label htmlFor="auto-approve" className="text-sm">
                  Auto-approve extracted rules
                </label>
              </div>
            </div>

            <DialogFooter>
              <DialogClose render={<Button variant="outline" />}>
                Cancel
              </DialogClose>
              <Button onClick={handleRunPipeline} disabled={!selectedDataset}>
                <Play className="mr-2 size-4" />
                Run
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Pipeline Status */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
      <Card className="p-6 border-border/50 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Pipeline Status
        </h2>
        <ProcessingStatus steps={pipelineSteps} />
      </Card>
      </motion.div>

      {/* Pipeline Result Summary */}
      {pipelineResult && (
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
        <Card className="p-6 border-border/50 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Pipeline Result
          </h2>
          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <p className="text-xs text-muted-foreground">Status</p>
              <p className="mt-1 text-sm font-medium">{pipelineResult.status}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Rules Extracted</p>
              <p className="mt-1 text-sm font-medium">
                {pipelineResult.rules_extracted ?? 0}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Simulation ID</p>
              <p className="mt-1 text-sm font-mono text-xs">
                {pipelineResult.simulation_id}
              </p>
            </div>
          </div>
          {pipelineResult.error && (
            <div className="mt-4 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
              {pipelineResult.error}
            </div>
          )}
        </Card>
        </motion.div>
      )}
    </div>
    </PageTransition>
  );
}
