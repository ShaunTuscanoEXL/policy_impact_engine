"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import api from "@/lib/api";
import type { RuleSet, Rule } from "@/lib/types";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  ArrowLeft,
  Loader2,
  Plus,
  CheckCircle,
  Shield,
  GitBranch,
  PlayCircle,
} from "lucide-react";
import { RuleTable } from "@/components/rules/rule-table";
import {
  RuleEditorDialog,
  type RuleFormData,
} from "@/components/rules/rule-editor-dialog";
import { ConflictPanel } from "@/components/rules/conflict-panel";
import { PageTransition } from "@/components/page-transition";
import { motion } from "framer-motion";

const STATUS_VARIANTS: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  DRAFT: "secondary",
  REVIEWED: "outline",
  APPROVED: "default",
  ARCHIVED: "destructive",
};

export default function RuleReviewPage() {
  const params = useParams<{ ruleSetId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const simulationId = searchParams.get("simulationId");

  const [ruleSet, setRuleSet] = useState<RuleSet | null>(null);
  const [loading, setLoading] = useState(true);

  // Editor dialog state
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<Rule | null>(null);
  const [saving, setSaving] = useState(false);

  // Action loading states
  const [approving, setApproving] = useState(false);
  const [creatingVersion, setCreatingVersion] = useState(false);
  const [runningSimulation, setRunningSimulation] = useState(false);

  const fetchRuleSet = useCallback(async () => {
    try {
      const { data } = await api.get(`/rule-sets/${params.ruleSetId}`);
      setRuleSet(data);
    } catch {
      toast.error("Failed to load rule set.");
      router.push("/brds");
    } finally {
      setLoading(false);
    }
  }, [params.ruleSetId, router]);

  useEffect(() => {
    fetchRuleSet();
  }, [fetchRuleSet]);

  const handleApproveAll = useCallback(async () => {
    setApproving(true);
    try {
      await api.patch(`/rule-sets/${params.ruleSetId}/approve`);
      toast.success("Rule set approved successfully.");
      fetchRuleSet();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to approve rule set.");
    } finally {
      setApproving(false);
    }
  }, [params.ruleSetId, fetchRuleSet]);

  const handleCreateVersion = useCallback(async () => {
    setCreatingVersion(true);
    try {
      const { data } = await api.post(
        `/rule-sets/${params.ruleSetId}/version`
      );
      toast.success(`New version v${data.version} created.`);
      // Navigate to the new version
      router.push(`/rules/${data.id}`);
    } catch (err: any) {
      toast.error(
        err?.response?.data?.detail || "Failed to create new version."
      );
    } finally {
      setCreatingVersion(false);
    }
  }, [params.ruleSetId, router]);

  const handleApproveAndRunSimulation = useCallback(async () => {
    if (!simulationId) return;
    setRunningSimulation(true);
    try {
      await api.post(`/pipeline/${simulationId}/approve`);
      toast.success("Rules approved and simulation completed.");
      router.push(`/simulations/${simulationId}`);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to approve and run simulation.");
    } finally {
      setRunningSimulation(false);
    }
  }, [simulationId, router]);

  const handleEditRule = useCallback((rule: Rule) => {
    setEditingRule(rule);
    setEditorOpen(true);
  }, []);

  const handleAddRule = useCallback(() => {
    setEditingRule(null);
    setEditorOpen(true);
  }, []);

  const handleDeleteRule = useCallback(
    async (ruleId: string) => {
      try {
        await api.delete(`/rules/${ruleId}`);
        toast.success("Rule deleted.");
        fetchRuleSet();
      } catch (err: any) {
        toast.error(err?.response?.data?.detail || "Failed to delete rule.");
      }
    },
    [fetchRuleSet]
  );

  const handleSaveRule = useCallback(
    async (formData: RuleFormData) => {
      setSaving(true);
      try {
        if (editingRule) {
          // Update existing rule
          await api.patch(`/rules/${editingRule.id}`, formData);
          toast.success("Rule updated.");
        } else {
          // Add new rule
          await api.post(
            `/rule-sets/${params.ruleSetId}/rules`,
            formData
          );
          toast.success("Rule added.");
        }
        setEditorOpen(false);
        setEditingRule(null);
        fetchRuleSet();
      } catch (err: any) {
        toast.error(err?.response?.data?.detail || "Failed to save rule.");
      } finally {
        setSaving(false);
      }
    },
    [editingRule, params.ruleSetId, fetchRuleSet]
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!ruleSet) return null;

  const conflictCount = ruleSet.rules.filter((r) => r.has_conflicts).length;

  return (
    <PageTransition>
    <div className="space-y-6">
      <p className="text-xs text-muted-foreground mb-4">Dashboard / Rules / Detail</p>
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
              <Shield className="size-6 text-indigo-500" />
              <h1 className="text-2xl font-bold tracking-tight">
                <span className="text-gradient">{ruleSet.name}</span>
              </h1>
              <Badge variant="outline">v{ruleSet.version}</Badge>
              <Badge variant={STATUS_VARIANTS[ruleSet.status] ?? "secondary"}>
                {ruleSet.status}
              </Badge>
            </div>
            {ruleSet.description && (
              <p className="mt-1 ml-10 text-sm text-muted-foreground">
                {ruleSet.description}
              </p>
            )}
            <p className="mt-0.5 ml-10 text-xs text-muted-foreground">
              {ruleSet.rules.length} rule{ruleSet.rules.length !== 1 ? "s" : ""}{" "}
              &middot; Created{" "}
              {new Date(ruleSet.created_at).toLocaleDateString("en-US", {
                year: "numeric",
                month: "short",
                day: "numeric",
              })}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={handleCreateVersion}
            disabled={creatingVersion}
          >
            {creatingVersion ? (
              <Loader2 className="mr-2 size-4 animate-spin" />
            ) : (
              <GitBranch className="mr-2 size-4" />
            )}
            Create New Version
          </Button>
          {simulationId && ruleSet.status !== "APPROVED" ? (
            <Button
              onClick={handleApproveAndRunSimulation}
              disabled={runningSimulation}
            >
              {runningSimulation ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : (
                <PlayCircle className="mr-2 size-4" />
              )}
              Approve &amp; Run Simulation
            </Button>
          ) : (
            <Button
              onClick={handleApproveAll}
              disabled={approving || ruleSet.status === "APPROVED"}
            >
              {approving ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : (
                <CheckCircle className="mr-2 size-4" />
              )}
              Approve All
            </Button>
          )}
        </div>
      </div>

      {/* Conflict Panel */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
      <ConflictPanel rules={ruleSet.rules} />
      </motion.div>

      {/* Rule Table */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
      <Card className="card-elevated p-0 overflow-hidden border-border/40">
        <div className="flex items-center justify-between border-b border-border/40 px-4 py-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Rules
          </h2>
          <Button size="sm" onClick={handleAddRule}>
            <Plus className="mr-1 size-3.5" />
            Add Rule
          </Button>
        </div>
        <RuleTable
          rules={ruleSet.rules}
          onEdit={handleEditRule}
          onDelete={handleDeleteRule}
        />
      </Card>
      </motion.div>

      {/* Editor Dialog */}
      <RuleEditorDialog
        open={editorOpen}
        onOpenChange={setEditorOpen}
        rule={editingRule}
        onSave={handleSaveRule}
        saving={saving}
      />
    </div>
    </PageTransition>
  );
}
