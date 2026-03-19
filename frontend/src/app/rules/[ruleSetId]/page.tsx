"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import api from "@/lib/api";
import type { RuleSet, Rule, TestCaseSuite } from "@/lib/types";
import {
  type TestCaseCounts,
  DEFAULT_TEST_CASE_COUNTS,
} from "@/components/brds/workflow-stepper";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  ArrowLeft,
  Loader2,
  Plus,
  CheckCircle,
  Shield,
  GitBranch,
  FlaskConical,
  ExternalLink,
} from "lucide-react";
import { RuleTable } from "@/components/rules/rule-table";
import {
  RuleEditorDialog,
  type RuleFormData,
} from "@/components/rules/rule-editor-dialog";
import { ConflictPanel } from "@/components/rules/conflict-panel";
import { TestCaseTable } from "@/components/test-cases/test-case-table";
import { TestCaseExportPanel } from "@/components/test-cases/test-case-export-panel";
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
  const router = useRouter();

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

  // Test case state
  const [testCaseSuite, setTestCaseSuite] = useState<TestCaseSuite | null>(null);
  const [testCaseLoading, setTestCaseLoading] = useState(false);
  const [testCaseCounts, setTestCaseCounts] = useState<TestCaseCounts>({
    ...DEFAULT_TEST_CASE_COUNTS,
  });


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

  const fetchTestCases = useCallback(async () => {
    try {
      const { data } = await api.get<TestCaseSuite>(`/test-cases/by-ruleset/${params.ruleSetId}`);
      setTestCaseSuite(data);
    } catch {
      // No test cases yet -- that's fine
    }
  }, [params.ruleSetId]);

  useEffect(() => {
    fetchRuleSet();
    fetchTestCases();
  }, [fetchRuleSet, fetchTestCases]);

  const handleGenerateTestCases = useCallback(async () => {
    setTestCaseLoading(true);
    try {
      const { data } = await api.post<TestCaseSuite>("/test-cases/generate", {
        rule_set_id: params.ruleSetId,
        counts: testCaseCounts,
      });
      setTestCaseSuite(data);
      toast.success(`${data.total_cases} test cases generated.`);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to generate test cases.");
    } finally {
      setTestCaseLoading(false);
    }
  }, [params.ruleSetId, testCaseCounts]);

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

  const handleApproveAndGenerateTests = useCallback(async () => {
    setRunningSimulation(true);
    try {
      // First approve the rule set
      await api.patch(`/rule-sets/${params.ruleSetId}/approve`);
      toast.success("Rules approved. You can now generate test cases.");
      await fetchRuleSet();
      // Auto-trigger test case generation
      await handleGenerateTestCases();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to approve rule set.");
    } finally {
      setRunningSimulation(false);
    }
  }, [params.ruleSetId, fetchRuleSet, handleGenerateTestCases]);

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

  const handleCountChange = useCallback(
    (category: keyof TestCaseCounts, value: number) => {
      setTestCaseCounts((prev) => ({ ...prev, [category]: value }));
    },
    []
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
          {ruleSet.status !== "APPROVED" ? (
            <Button
              onClick={handleApproveAndGenerateTests}
              disabled={runningSimulation}
            >
              {runningSimulation ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : (
                <FlaskConical className="mr-2 size-4" />
              )}
              Approve &amp; Generate Tests
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

      {/* Test Cases Section - Count Configuration */}
      {ruleSet.status === "APPROVED" && !testCaseSuite && (
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
          <Card className="card-elevated p-6 border-border/40">
            <div className="flex items-center gap-3 mb-4">
              <FlaskConical className="size-5 text-purple-500" />
              <div>
                <h2 className="text-sm font-semibold">Generate Test Cases</h2>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Configure counts per category and generate test cases from the approved rules
                </p>
              </div>
            </div>
            <div className="grid grid-cols-5 gap-3 mb-4">
              {(Object.keys(DEFAULT_TEST_CASE_COUNTS) as Array<keyof TestCaseCounts>).map((cat) => (
                <div key={cat} className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground uppercase">{cat}</label>
                  <Input
                    type="number"
                    min={0}
                    max={20}
                    value={testCaseCounts[cat]}
                    onChange={(e) => handleCountChange(cat, parseInt(e.target.value) || 0)}
                    className="h-9"
                  />
                </div>
              ))}
            </div>
            <Button onClick={handleGenerateTestCases} disabled={testCaseLoading}>
              {testCaseLoading ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : (
                <FlaskConical className="mr-2 size-4" />
              )}
              Generate Test Cases
            </Button>
          </Card>
        </motion.div>
      )}

      {testCaseSuite && (
        <>
          {/* View Full Suite Link */}
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                <span className="font-medium text-foreground">{testCaseSuite.total_cases}</span> test cases generated
              </p>
              <Button variant="outline" size="sm" render={<Link href={`/test-suites/${testCaseSuite.id}`} />}>
                <ExternalLink className="mr-1.5 size-3.5" />
                View Full Suite
              </Button>
            </div>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}>
            <TestCaseTable
              testCases={testCaseSuite.test_cases}
              casesByCategory={testCaseSuite.cases_by_category}
            />
          </motion.div>
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
            <TestCaseExportPanel
              suiteId={testCaseSuite.id}
              totalCases={testCaseSuite.total_cases}
              casesByCategory={testCaseSuite.cases_by_category}
            />
          </motion.div>
        </>
      )}

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
