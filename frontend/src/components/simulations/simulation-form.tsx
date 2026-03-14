"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/api";
import type { BrdDocument, Dataset, PipelineRunResponse } from "@/lib/types";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PlayCircle, Loader2, CheckCircle } from "lucide-react";

export function SimulationForm() {
  const router = useRouter();

  const [brds, setBrds] = useState<BrdDocument[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loadingBrds, setLoadingBrds] = useState(true);
  const [loadingDatasets, setLoadingDatasets] = useState(true);

  const [selectedBrdId, setSelectedBrdId] = useState<string>("");
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>("");
  const [scenarioName, setScenarioName] = useState("");
  const [autoApprove, setAutoApprove] = useState(true);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    async function fetchBrds() {
      try {
        const { data } = await api.get("/brds");
        setBrds(data);
      } catch {
        toast.error("Failed to load BRD documents.");
      } finally {
        setLoadingBrds(false);
      }
    }

    async function fetchDatasets() {
      try {
        const { data } = await api.get("/datasets");
        setDatasets(data);
      } catch {
        toast.error("Failed to load datasets.");
      } finally {
        setLoadingDatasets(false);
      }
    }

    fetchBrds();
    fetchDatasets();
  }, []);

  const handleRun = useCallback(async () => {
    if (!selectedBrdId) {
      toast.error("Please select a BRD document.");
      return;
    }
    if (!selectedDatasetId) {
      toast.error("Please select a dataset.");
      return;
    }
    if (!scenarioName.trim()) {
      toast.error("Please enter a scenario name.");
      return;
    }

    setRunning(true);
    try {
      const { data: result } = await api.post<PipelineRunResponse>(
        "/pipeline/run",
        {
          brd_id: selectedBrdId,
          dataset_id: selectedDatasetId,
          scenario_name: scenarioName.trim(),
          auto_approve: autoApprove,
        }
      );

      if (result.status === "COMPLETED") {
        toast.success("Simulation completed successfully!");
        router.push(`/simulations/${result.simulation_id}`);
      } else if (result.status === "AWAITING_REVIEW") {
        toast.info("Rules extracted. Redirecting to review...");
        router.push(`/rules/${result.rule_set_id}`);
      } else if (result.status === "FAILED") {
        toast.error(result.error || "Pipeline run failed.");
      } else {
        toast.info(`Pipeline status: ${result.status}`);
      }
    } catch (err: any) {
      const message =
        err?.response?.data?.detail || err?.message || "Pipeline run failed.";
      toast.error(message);
    } finally {
      setRunning(false);
    }
  }, [selectedBrdId, selectedDatasetId, scenarioName, autoApprove, router]);

  const isLoading = loadingBrds || loadingDatasets;

  return (
    <Card className="p-6 card-elevated border-border/40">
      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-semibold">Configure Simulation</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Select a BRD and dataset, then run the pipeline.
          </p>
        </div>

        <Separator />

        {/* BRD Select */}
        <div className="space-y-2">
          <label className="text-sm font-medium" htmlFor="brd-select">
            BRD Document
          </label>
          {loadingBrds ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" />
              Loading BRDs...
            </div>
          ) : brds.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No BRDs uploaded. Upload one first.
            </p>
          ) : (
            <Select
              value={selectedBrdId}
              onValueChange={(v) => setSelectedBrdId(v ?? "")}
            >
              <SelectTrigger className="w-full" id="brd-select">
                <SelectValue placeholder="Select a BRD document" />
              </SelectTrigger>
              <SelectContent>
                {brds.map((brd) => (
                  <SelectItem key={brd.id} value={brd.id}>
                    {brd.filename}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>

        {/* Dataset Select */}
        <div className="space-y-2">
          <label className="text-sm font-medium" htmlFor="dataset-select">
            Dataset
          </label>
          {loadingDatasets ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" />
              Loading datasets...
            </div>
          ) : datasets.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No datasets uploaded. Upload one first.
            </p>
          ) : (
            <Select
              value={selectedDatasetId}
              onValueChange={(v) => setSelectedDatasetId(v ?? "")}
            >
              <SelectTrigger className="w-full" id="dataset-select">
                <SelectValue placeholder="Select a dataset" />
              </SelectTrigger>
              <SelectContent>
                {datasets.map((ds) => (
                  <SelectItem key={ds.id} value={ds.id}>
                    {ds.name} ({ds.row_count.toLocaleString()} rows)
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>

        {/* Scenario Name */}
        <div className="space-y-2">
          <label className="text-sm font-medium" htmlFor="scenario-name">
            Scenario Name
          </label>
          <Input
            id="scenario-name"
            placeholder="e.g., Q1 Policy Update Impact"
            value={scenarioName}
            onChange={(e) => setScenarioName(e.target.value)}
          />
        </div>

        {/* Auto Approve */}
        <div className="flex items-center gap-3">
          <input
            id="auto-approve"
            type="checkbox"
            checked={autoApprove}
            onChange={(e) => setAutoApprove(e.target.checked)}
            className="size-4 rounded border-input accent-primary"
          />
          <label className="text-sm font-medium cursor-pointer" htmlFor="auto-approve">
            Auto-approve extracted rules
          </label>
        </div>

        <Separator />

        {/* Run Button */}
        <Button
          size="lg"
          disabled={running || isLoading}
          onClick={handleRun}
          className="w-full"
        >
          {running ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Running Pipeline...
            </>
          ) : (
            <>
              <PlayCircle className="size-4" />
              Run Simulation
            </>
          )}
        </Button>
      </div>
    </Card>
  );
}
