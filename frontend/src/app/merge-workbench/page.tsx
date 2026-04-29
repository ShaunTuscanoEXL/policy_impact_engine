"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import api from "@/lib/api";
import type { BrdDocument, BrdWorkflow, MergeProposal } from "@/lib/types";
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
  GitMerge,
  ArrowRight,
  Loader2,
  AlertTriangle,
  FileText,
} from "lucide-react";

interface PendingProposalRow {
  proposalId: string;
  brdId: string;
  brdFilename: string;
  repositoryId: string;
  baseVersion: number;
  summary: string | null;
  counts_by_severity: Record<string, number>;
}

export default function MergeWorkbenchListPage() {
  const [rows, setRows] = useState<PendingProposalRow[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchPending = useCallback(async () => {
    setLoading(true);
    try {
      const { data: brds } = await api.get<BrdDocument[]>("/brds");

      const workflows = await Promise.all(
        brds.map(async (brd) => {
          try {
            const { data } = await api.get<BrdWorkflow>(
              `/brds/${brd.id}/workflow`
            );
            return { brd, workflow: data };
          } catch {
            return { brd, workflow: null };
          }
        })
      );

      const pending = workflows.filter(
        ({ workflow }) =>
          workflow?.merge_proposal &&
          workflow.merge_proposal.status === "PENDING"
      );

      // Fetch each proposal to get severity counts
      const detailed = await Promise.all(
        pending.map(async ({ brd, workflow }) => {
          const mp = workflow!.merge_proposal!;
          try {
            const { data } = await api.get<MergeProposal>(
              `/merge-proposal/${mp.id}`
            );
            return {
              proposalId: mp.id,
              brdId: brd.id,
              brdFilename: brd.filename,
              repositoryId: mp.repository_id,
              baseVersion: mp.base_version,
              summary: mp.summary,
              counts_by_severity: data.counts_by_severity,
            } as PendingProposalRow;
          } catch {
            return {
              proposalId: mp.id,
              brdId: brd.id,
              brdFilename: brd.filename,
              repositoryId: mp.repository_id,
              baseVersion: mp.base_version,
              summary: mp.summary,
              counts_by_severity: {},
            } as PendingProposalRow;
          }
        })
      );

      setRows(detailed);
    } catch {
      toast.error("Failed to load pending merge proposals.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPending();
  }, [fetchPending]);

  return (
    <PageTransition>
      <div className="space-y-8">
        <div>
          <p className="text-xs text-muted-foreground mb-4">
            Dashboard / Merge Workbench
          </p>
          <div className="flex items-center gap-3">
            <div className="icon-badge bg-violet-100 dark:bg-violet-900/30">
              <GitMerge className="size-5 text-violet-600 dark:text-violet-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight">
                <span className="text-gradient">Merge Workbench</span>
              </h1>
              <p className="text-sm text-muted-foreground">
                Pending merge proposals awaiting human-in-the-loop review.
              </p>
            </div>
          </div>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.1 }}
        >
          <Card className="card-elevated border-border/40">
            {loading ? (
              <div className="flex items-center justify-center py-16">
                <Loader2 className="size-6 animate-spin text-muted-foreground" />
              </div>
            ) : rows.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <GitMerge className="size-12 text-muted-foreground/20" />
                <p className="mt-3 text-sm text-muted-foreground">
                  No pending proposals.
                </p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-violet-500/20">
                      BRD
                    </TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-violet-500/20">
                      Repository
                    </TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-violet-500/20">
                      Base
                    </TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-violet-500/20">
                      Summary
                    </TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-violet-500/20">
                      Severity
                    </TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-violet-500/20 text-right">
                      Actions
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((row) => {
                    const hard = row.counts_by_severity.HARD || 0;
                    const soft = row.counts_by_severity.SOFT || 0;
                    const info = row.counts_by_severity.INFO || 0;
                    return (
                      <TableRow
                        key={row.proposalId}
                        className="group transition-colors duration-150 hover:bg-accent/50"
                      >
                        <TableCell>
                          <Link
                            href={`/brds/${row.brdId}`}
                            className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
                          >
                            <FileText className="size-4" />
                            {row.brdFilename}
                          </Link>
                        </TableCell>
                        <TableCell>
                          <Link
                            href={`/live-repo/${row.repositoryId}`}
                            className="text-xs font-mono text-primary hover:underline"
                          >
                            {row.repositoryId.slice(0, 8)}
                          </Link>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">v{row.baseVersion}</Badge>
                        </TableCell>
                        <TableCell className="max-w-md">
                          <span className="text-sm text-muted-foreground">
                            {row.summary || (
                              <span className="italic">No summary</span>
                            )}
                          </span>
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-wrap gap-1">
                            {hard > 0 && (
                              <Badge
                                variant="outline"
                                className="bg-red-500/10 text-red-600 border-red-500/20 dark:text-red-400"
                              >
                                <AlertTriangle className="size-3" />
                                {hard} HARD
                              </Badge>
                            )}
                            {soft > 0 && (
                              <Badge
                                variant="outline"
                                className="bg-amber-500/10 text-amber-600 border-amber-500/20 dark:text-amber-400"
                              >
                                {soft} SOFT
                              </Badge>
                            )}
                            {info > 0 && (
                              <Badge
                                variant="outline"
                                className="bg-slate-500/10 text-slate-600 border-slate-500/20 dark:text-slate-400"
                              >
                                {info} INFO
                              </Badge>
                            )}
                            {hard + soft + info === 0 && (
                              <span className="text-xs text-muted-foreground">
                                —
                              </span>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="default"
                            size="sm"
                            render={
                              <Link
                                href={`/merge-workbench/${row.proposalId}`}
                              />
                            }
                          >
                            Open
                            <ArrowRight className="size-3.5" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            )}
          </Card>
        </motion.div>
      </div>
    </PageTransition>
  );
}
