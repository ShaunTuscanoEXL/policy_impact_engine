"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import api from "@/lib/api";
import type {
  LiveRepositoryDetail,
  LiveVersionDetail,
  LiveVersionSummary,
} from "@/lib/types";
import { toast } from "sonner";
import { PageTransition } from "@/components/page-transition";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  GitBranch,
  ArrowLeft,
  Loader2,
  Download,
  Eye,
  FileCode,
} from "lucide-react";

const SUBSYSTEM_COLORS: Record<string, string> = {
  BUREAU_GATE: "bg-blue-500/10 text-blue-600 border-blue-500/20 dark:text-blue-400",
  INCOME_GATE: "bg-emerald-500/10 text-emerald-600 border-emerald-500/20 dark:text-emerald-400",
  DTI_GATE: "bg-amber-500/10 text-amber-600 border-amber-500/20 dark:text-amber-400",
  EMPLOYMENT_GATE: "bg-violet-500/10 text-violet-600 border-violet-500/20 dark:text-violet-400",
  BANKING_BEHAVIOR: "bg-cyan-500/10 text-cyan-600 border-cyan-500/20 dark:text-cyan-400",
  PRICING_TIER: "bg-pink-500/10 text-pink-600 border-pink-500/20 dark:text-pink-400",
  RATE_MODIFIER: "bg-rose-500/10 text-rose-600 border-rose-500/20 dark:text-rose-400",
  AMOUNT_CAP: "bg-orange-500/10 text-orange-600 border-orange-500/20 dark:text-orange-400",
  FRAUD_SIGNAL: "bg-red-500/10 text-red-600 border-red-500/20 dark:text-red-400",
  REGULATORY_FLOOR: "bg-indigo-500/10 text-indigo-600 border-indigo-500/20 dark:text-indigo-400",
  EXPOSURE_LIMIT: "bg-yellow-500/10 text-yellow-600 border-yellow-500/20 dark:text-yellow-400",
  SCORING_MODEL: "bg-purple-500/10 text-purple-600 border-purple-500/20 dark:text-purple-400",
  UNCLASSIFIED: "bg-slate-500/10 text-slate-600 border-slate-500/20 dark:text-slate-400",
};

function formatCondition(c: any): string {
  if (!c) return "";
  const field = c.field ?? "?";
  const op = c.operator ?? "?";
  const value = Array.isArray(c.value) ? `[${c.value.join(", ")}]` : c.value;
  return `${field} ${op} ${value ?? ""}`.trim();
}

function formatAction(a: any): string {
  if (!a) return "";
  const type = a.action_type ?? "";
  const target = a.target_field ?? "";
  const val = a.value !== undefined && a.value !== null ? ` = ${a.value}` : "";
  return `${type} ${target}${val}`.trim();
}

function buildExportUrl(repoId: string, versionNumber?: number): string {
  const base =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001/api/v1";
  if (typeof versionNumber === "number") {
    return `${base}/live-repo/${repoId}/version/${versionNumber}/export.py`;
  }
  return `${base}/live-repo/${repoId}/export.py`;
}

export default function LiveRepoDetailPage() {
  const params = useParams<{ repoId: string }>();
  const router = useRouter();
  const repoId = params.repoId;

  const [repo, setRepo] = useState<LiveRepositoryDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [versionDetail, setVersionDetail] =
    useState<LiveVersionDetail | null>(null);
  const [versionLoading, setVersionLoading] = useState(false);
  const [openVersion, setOpenVersion] = useState<number | null>(null);

  const fetchRepo = useCallback(async () => {
    try {
      const { data } = await api.get<LiveRepositoryDetail>(
        `/live-repo/${repoId}`
      );
      setRepo(data);
    } catch {
      toast.error("Failed to load repository.");
      router.push("/live-repo");
    } finally {
      setLoading(false);
    }
  }, [repoId, router]);

  useEffect(() => {
    fetchRepo();
  }, [fetchRepo]);

  const handleViewVersion = useCallback(
    async (versionNumber: number) => {
      setOpenVersion(versionNumber);
      setVersionLoading(true);
      setVersionDetail(null);
      try {
        const { data } = await api.get<LiveVersionDetail>(
          `/live-repo/${repoId}/version/${versionNumber}`
        );
        setVersionDetail(data);
      } catch {
        toast.error("Failed to load version snapshot.");
      } finally {
        setVersionLoading(false);
      }
    },
    [repoId]
  );

  const handleDownloadVersion = useCallback(
    (versionNumber: number) => {
      window.open(buildExportUrl(repoId, versionNumber), "_blank");
    },
    [repoId]
  );

  const handleDownloadHead = useCallback(() => {
    window.open(buildExportUrl(repoId), "_blank");
  }, [repoId]);

  const headSnapshot = useMemo<LiveVersionSummary | undefined>(() => {
    if (!repo) return undefined;
    return repo.versions.find(
      (v) => v.version_number === repo.current_version
    );
  }, [repo]);

  const [headRules, setHeadRules] = useState<Array<Record<string, any>> | null>(
    null
  );
  const [headLoading, setHeadLoading] = useState(false);

  const fetchHeadRules = useCallback(async () => {
    if (!repo || repo.current_version === 0) {
      setHeadRules([]);
      return;
    }
    setHeadLoading(true);
    try {
      const { data } = await api.get<LiveVersionDetail>(
        `/live-repo/${repoId}/version/${repo.current_version}`
      );
      setHeadRules(data.rule_snapshot || []);
    } catch {
      toast.error("Failed to load HEAD snapshot.");
      setHeadRules([]);
    } finally {
      setHeadLoading(false);
    }
  }, [repo, repoId]);

  useEffect(() => {
    if (repo) fetchHeadRules();
  }, [repo, fetchHeadRules]);

  const groupedHeadRules = useMemo(() => {
    if (!headRules) return {};
    const groups: Record<string, Array<Record<string, any>>> = {};
    for (const rule of headRules) {
      const key = (rule.subsystem as string) || "UNCLASSIFIED";
      if (!groups[key]) groups[key] = [];
      groups[key].push(rule);
    }
    return groups;
  }, [headRules]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!repo) return null;

  return (
    <PageTransition>
      <div className="space-y-8">
        <p className="text-xs text-muted-foreground mb-4">
          Dashboard /{" "}
          <Link href="/live-repo" className="hover:underline">
            Live Repo
          </Link>{" "}
          / {repo.name}
        </p>

        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-4">
            <Button
              variant="ghost"
              size="icon-sm"
              render={<Link href="/live-repo" />}
            >
              <ArrowLeft className="size-4" />
            </Button>
            <div>
              <div className="flex items-center gap-3">
                <GitBranch className="size-6 text-amber-500" />
                <h1 className="text-2xl font-bold tracking-tight">
                  <span className="text-gradient">{repo.name}</span>
                </h1>
                <Badge variant="outline">{repo.product}</Badge>
                <Badge variant="secondary">{repo.jurisdiction}</Badge>
                <Badge
                  variant="outline"
                  className="bg-amber-500/10 text-amber-600 border-amber-500/20 dark:text-amber-400"
                >
                  HEAD v{repo.current_version}
                </Badge>
              </div>
              {repo.description && (
                <p className="mt-1 ml-9 text-sm text-muted-foreground">
                  {repo.description}
                </p>
              )}
            </div>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={handleDownloadHead}
            disabled={repo.current_version === 0}
          >
            <Download className="size-4" />
            Download HEAD as Python
          </Button>
        </div>

        {/* Tabs */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.1 }}
        >
          <Tabs defaultValue="versions">
            <TabsList>
              <TabsTrigger value="versions">Versions</TabsTrigger>
              <TabsTrigger value="head">HEAD Snapshot</TabsTrigger>
            </TabsList>

            <TabsContent value="versions">
              <Card className="card-elevated border-border/40">
                {repo.versions.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-16 text-center">
                    <FileCode className="size-12 text-muted-foreground/20" />
                    <p className="mt-3 text-sm text-muted-foreground">
                      No versions yet. Apply a merge proposal from a BRD to
                      create version 1.
                    </p>
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-amber-500/20">
                          Version
                        </TableHead>
                        <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-amber-500/20">
                          Summary
                        </TableHead>
                        <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-amber-500/20">
                          Rules
                        </TableHead>
                        <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-amber-500/20">
                          Source BRD
                        </TableHead>
                        <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-amber-500/20">
                          Created By
                        </TableHead>
                        <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-amber-500/20">
                          Created At
                        </TableHead>
                        <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-amber-500/20 text-right">
                          Actions
                        </TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {[...repo.versions]
                        .sort((a, b) => b.version_number - a.version_number)
                        .map((v) => (
                          <TableRow
                            key={v.id}
                            className="group transition-colors duration-150 hover:bg-accent/50"
                          >
                            <TableCell>
                              <Badge
                                variant={
                                  v.version_number === repo.current_version
                                    ? "default"
                                    : "outline"
                                }
                              >
                                v{v.version_number}
                              </Badge>
                            </TableCell>
                            <TableCell className="max-w-xs">
                              <span className="text-sm">
                                {v.summary || (
                                  <span className="text-muted-foreground italic">
                                    No summary
                                  </span>
                                )}
                              </span>
                            </TableCell>
                            <TableCell className="text-muted-foreground">
                              {v.rule_count}
                            </TableCell>
                            <TableCell>
                              {v.source_brd_id ? (
                                <Link
                                  href={`/brds/${v.source_brd_id}`}
                                  className="text-xs font-mono text-primary hover:underline"
                                >
                                  {v.source_brd_id.slice(0, 8)}
                                </Link>
                              ) : (
                                <span className="text-xs text-muted-foreground">
                                  —
                                </span>
                              )}
                            </TableCell>
                            <TableCell className="text-muted-foreground text-sm">
                              {v.created_by || "—"}
                            </TableCell>
                            <TableCell className="text-muted-foreground text-sm">
                              {new Date(v.created_at).toLocaleDateString(
                                "en-US",
                                {
                                  year: "numeric",
                                  month: "short",
                                  day: "numeric",
                                  hour: "2-digit",
                                  minute: "2-digit",
                                }
                              )}
                            </TableCell>
                            <TableCell className="text-right">
                              <div className="flex items-center justify-end gap-1">
                                <Button
                                  variant="ghost"
                                  size="icon-sm"
                                  title="View snapshot"
                                  onClick={() =>
                                    handleViewVersion(v.version_number)
                                  }
                                >
                                  <Eye className="size-4" />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="icon-sm"
                                  title="Download .py"
                                  onClick={() =>
                                    handleDownloadVersion(v.version_number)
                                  }
                                >
                                  <Download className="size-4" />
                                </Button>
                              </div>
                            </TableCell>
                          </TableRow>
                        ))}
                    </TableBody>
                  </Table>
                )}
              </Card>
            </TabsContent>

            <TabsContent value="head">
              <Card className="card-elevated border-border/40 p-6">
                {headLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="size-6 animate-spin text-muted-foreground" />
                  </div>
                ) : !headSnapshot ? (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    <FileCode className="size-12 text-muted-foreground/20" />
                    <p className="mt-3 text-sm text-muted-foreground">
                      No HEAD snapshot available — repository is empty.
                    </p>
                  </div>
                ) : (headRules?.length ?? 0) === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    <FileCode className="size-12 text-muted-foreground/20" />
                    <p className="mt-3 text-sm text-muted-foreground">
                      HEAD version contains no rules.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-6">
                    <div className="text-sm text-muted-foreground">
                      Showing{" "}
                      <span className="font-medium text-foreground">
                        {headRules?.length ?? 0}
                      </span>{" "}
                      rules from HEAD v{repo.current_version}.
                    </div>

                    {Object.entries(groupedHeadRules)
                      .sort(([a], [b]) => a.localeCompare(b))
                      .map(([subsystem, rules]) => (
                        <div key={subsystem} className="space-y-2">
                          <div className="flex items-center gap-2 border-b border-border/40 pb-2">
                            <Badge
                              variant="outline"
                              className={
                                SUBSYSTEM_COLORS[subsystem] ||
                                SUBSYSTEM_COLORS.UNCLASSIFIED
                              }
                            >
                              {subsystem}
                            </Badge>
                            <span className="text-xs text-muted-foreground">
                              {rules.length} rule{rules.length !== 1 ? "s" : ""}
                            </span>
                          </div>

                          <div className="space-y-2">
                            {rules.map((rule, idx) => (
                              <Card
                                key={`${subsystem}-${idx}`}
                                size="sm"
                                className="border-border/40 p-3"
                              >
                                <div className="flex items-start justify-between gap-3">
                                  <div className="flex-1 space-y-1.5">
                                    <div className="flex items-center gap-2">
                                      <span className="font-mono text-xs text-muted-foreground">
                                        {rule.rule_id ?? "—"}
                                      </span>
                                      <span className="font-medium text-sm">
                                        {rule.rule_name ?? "Unnamed rule"}
                                      </span>
                                    </div>
                                    {Array.isArray(rule.conditions) &&
                                      rule.conditions.length > 0 && (
                                        <div className="text-xs text-muted-foreground">
                                          <span className="font-semibold">
                                            When:
                                          </span>{" "}
                                          {rule.conditions
                                            .map(formatCondition)
                                            .join(" AND ")}
                                        </div>
                                      )}
                                    {Array.isArray(rule.actions) &&
                                      rule.actions.length > 0 && (
                                        <div className="text-xs text-muted-foreground">
                                          <span className="font-semibold">
                                            Then:
                                          </span>{" "}
                                          {rule.actions
                                            .map(formatAction)
                                            .join("; ")}
                                        </div>
                                      )}
                                  </div>
                                  {rule.priority !== undefined && (
                                    <Badge variant="outline" className="text-xs">
                                      P{rule.priority}
                                    </Badge>
                                  )}
                                </div>
                              </Card>
                            ))}
                          </div>
                        </div>
                      ))}
                  </div>
                )}
              </Card>
            </TabsContent>
          </Tabs>
        </motion.div>

        {/* Version detail dialog */}
        <Dialog
          open={openVersion !== null}
          onOpenChange={(open) => {
            if (!open) {
              setOpenVersion(null);
              setVersionDetail(null);
            }
          }}
        >
          <DialogContent className="sm:max-w-3xl max-h-[85vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>
                Version {openVersion !== null ? `v${openVersion}` : ""} Snapshot
              </DialogTitle>
              <DialogDescription>
                {versionDetail?.summary || "Rule snapshot for this version."}
              </DialogDescription>
            </DialogHeader>

            {versionLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="size-6 animate-spin text-muted-foreground" />
              </div>
            ) : versionDetail ? (
              <div className="space-y-2">
                <div className="text-sm text-muted-foreground">
                  {versionDetail.rule_snapshot.length} rule
                  {versionDetail.rule_snapshot.length !== 1 ? "s" : ""} captured.
                </div>
                {versionDetail.rule_snapshot.length === 0 ? (
                  <p className="text-sm text-muted-foreground italic">
                    No rules in this version.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {versionDetail.rule_snapshot.map((rule, idx) => (
                      <Card
                        key={idx}
                        size="sm"
                        className="border-border/40 p-3"
                      >
                        <div className="space-y-1.5">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-mono text-xs text-muted-foreground">
                              {rule.rule_id ?? "—"}
                            </span>
                            <span className="font-medium text-sm">
                              {rule.rule_name ?? "Unnamed rule"}
                            </span>
                            {rule.subsystem && (
                              <Badge
                                variant="outline"
                                className={
                                  SUBSYSTEM_COLORS[rule.subsystem as string] ||
                                  SUBSYSTEM_COLORS.UNCLASSIFIED
                                }
                              >
                                {rule.subsystem}
                              </Badge>
                            )}
                          </div>
                          {Array.isArray(rule.conditions) &&
                            rule.conditions.length > 0 && (
                              <div className="text-xs text-muted-foreground">
                                <span className="font-semibold">When:</span>{" "}
                                {rule.conditions
                                  .map(formatCondition)
                                  .join(" AND ")}
                              </div>
                            )}
                          {Array.isArray(rule.actions) &&
                            rule.actions.length > 0 && (
                              <div className="text-xs text-muted-foreground">
                                <span className="font-semibold">Then:</span>{" "}
                                {rule.actions.map(formatAction).join("; ")}
                              </div>
                            )}
                        </div>
                      </Card>
                    ))}
                  </div>
                )}
              </div>
            ) : null}
          </DialogContent>
        </Dialog>
      </div>
    </PageTransition>
  );
}
