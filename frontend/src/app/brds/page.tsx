"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import api from "@/lib/api";
import type { BrdDocument } from "@/lib/types";
import { toast } from "sonner";
import { UploadDropzone } from "@/components/brds/upload-dropzone";
import { PageTransition } from "@/components/page-transition";
import { EmptyState } from "@/components/empty-state";
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogClose,
} from "@/components/ui/dialog";
import { FileText, ArrowRight, Trash2, Loader2 } from "lucide-react";
import { DownstreamFlowChips } from "@/components/brds/downstream-flow-chips";

export default function BrdsPage() {
  const [brds, setBrds] = useState<BrdDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const fetchBrds = useCallback(async () => {
    try {
      const { data } = await api.get("/brds");
      setBrds(data);
    } catch {
      toast.error("Failed to load BRD documents.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBrds();
  }, [fetchBrds]);

  const handleUpload = useCallback(
    async (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      await api.post("/brds/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success(`"${file.name}" uploaded successfully.`);
      fetchBrds();
    },
    [fetchBrds]
  );

  const handleDelete = useCallback(
    async (id: string) => {
      setDeleting(true);
      try {
        await api.delete(`/brds/${id}`);
        toast.success("BRD deleted.");
        setBrds((prev) => prev.filter((b) => b.id !== id));
      } catch {
        toast.error("Failed to delete BRD.");
      } finally {
        setDeleting(false);
        setDeleteId(null);
      }
    },
    []
  );

  const fileTypeBadge = (type: string) => {
    const upper = type.toUpperCase();
    if (upper.includes("PDF")) {
      return <Badge variant="secondary">PDF</Badge>;
    }
    if (upper.includes("DOCX") || upper.includes("WORD")) {
      return <Badge variant="outline">DOCX</Badge>;
    }
    return <Badge variant="outline">{upper}</Badge>;
  };

  return (
    <PageTransition>
      <div className="space-y-8">
        <div>
          <p className="text-xs text-muted-foreground mb-4">Dashboard / BRD Documents</p>
          <div className="flex items-center gap-3">
            <div className="icon-badge bg-blue-100 dark:bg-blue-900/30">
              <FileText className="size-5 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight"><span className="text-gradient">BRD Documents</span></h1>
              <p className="text-sm text-muted-foreground">
                Upload and manage Business Requirements Documents.
              </p>
            </div>
          </div>
        </div>

        {/* Upload Section */}
        <Card className="card-elevated card-glow p-6 border-border/40">
          <UploadDropzone onUpload={handleUpload} />
        </Card>

        {/* BRD List Section */}
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
            ) : brds.length === 0 ? (
              <EmptyState
                variant="inline"
                tone="blue"
                icon={FileText}
                title="No BRD documents yet"
                description="Upload a Business Requirements Document (PDF or DOCX) and the AI will extract structured rules you can review, merge, and validate against the live policy repo."
                hints={[
                  "PDFs and DOCX files are supported. Anything with tabular thresholds works best.",
                  "Once uploaded, click the BRD to start the 5-stage pipeline.",
                  "Each rule gets a confidence score so you know which to spot-check first.",
                ]}
              />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-blue-500/20">Filename</TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-blue-500/20">Type</TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-blue-500/20">Rules</TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-blue-500/20">Pipeline</TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-blue-500/20">Uploaded At</TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-blue-500/20 text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {brds.map((brd) => (
                    <TableRow key={brd.id} className="group cursor-pointer transition-colors duration-150 hover:bg-accent/50">
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          <FileText className="size-4 text-blue-500" />
                          {brd.filename}
                        </div>
                      </TableCell>
                      <TableCell>{fileTypeBadge(brd.file_type)}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {(brd.total_rules ?? 0) > 0 ? (
                          <span className="font-mono font-semibold text-foreground">
                            {brd.total_rules}
                          </span>
                        ) : (
                          <span className="italic">none</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <DownstreamFlowChips
                          hasRules={(brd.total_rules ?? 0) > 0}
                          hasMergeProposal={brd.has_merge_proposal ?? false}
                          isMergedIntoRepo={brd.is_merged_into_repo ?? false}
                          hasTestSuite={brd.has_test_suite ?? false}
                          hasExecutedTestSuite={brd.has_executed_test_suite ?? false}
                        />
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {new Date(brd.created_at).toLocaleDateString("en-US", {
                          year: "numeric",
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            variant="default"
                            size="sm"
                            render={<Link href={`/brds/${brd.id}`} />}
                          >
                            View Details
                            <ArrowRight className="size-3.5" />
                          </Button>

                          <Dialog
                            open={deleteId === brd.id}
                            onOpenChange={(open) =>
                              setDeleteId(open ? brd.id : null)
                            }
                          >
                            <DialogTrigger
                              render={
                                <Button variant="ghost" size="icon-sm" />
                              }
                            >
                              <Trash2 className="size-4 text-destructive" />
                            </DialogTrigger>
                            <DialogContent>
                              <DialogHeader>
                                <DialogTitle>Delete BRD</DialogTitle>
                                <DialogDescription>
                                  Are you sure you want to delete &ldquo;
                                  {brd.filename}&rdquo;? This action cannot be
                                  undone.
                                </DialogDescription>
                              </DialogHeader>
                              <DialogFooter>
                                <DialogClose
                                  render={<Button variant="outline" />}
                                >
                                  Cancel
                                </DialogClose>
                                <Button
                                  variant="destructive"
                                  disabled={deleting}
                                  onClick={() => handleDelete(brd.id)}
                                >
                                  {deleting && (
                                    <Loader2 className="mr-2 size-4 animate-spin" />
                                  )}
                                  Delete
                                </Button>
                              </DialogFooter>
                            </DialogContent>
                          </Dialog>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </Card>
        </motion.div>
      </div>
    </PageTransition>
  );
}
