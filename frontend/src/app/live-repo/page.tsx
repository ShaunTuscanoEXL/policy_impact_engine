"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import api from "@/lib/api";
import type { LiveRepository } from "@/lib/types";
import { toast } from "sonner";
import { PageTransition } from "@/components/page-transition";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
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
import { GitBranch, ArrowRight, Loader2, Sparkles } from "lucide-react";

export default function LiveRepoListPage() {
  const [repos, setRepos] = useState<LiveRepository[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);

  const [name, setName] = useState("");
  const [product, setProduct] = useState("");
  const [jurisdiction, setJurisdiction] = useState("");
  const [description, setDescription] = useState("");

  const fetchRepos = useCallback(async () => {
    try {
      const { data } = await api.get<LiveRepository[]>("/live-repo");
      setRepos(data);
    } catch {
      toast.error("Failed to load live repositories.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRepos();
  }, [fetchRepos]);

  const resetForm = () => {
    setName("");
    setProduct("");
    setJurisdiction("");
    setDescription("");
  };

  const handleCreate = useCallback(async () => {
    if (!name.trim() || !product.trim() || !jurisdiction.trim()) {
      toast.error("Name, product, and jurisdiction are required.");
      return;
    }
    setCreating(true);
    try {
      const { data } = await api.post<LiveRepository>("/live-repo", {
        name: name.trim(),
        product: product.trim(),
        jurisdiction: jurisdiction.trim(),
        description: description.trim() || null,
      });
      toast.success(`Repository "${data.name}" created.`);
      resetForm();
      setCreateOpen(false);
      fetchRepos();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to create repository.");
    } finally {
      setCreating(false);
    }
  }, [name, product, jurisdiction, description, fetchRepos]);

  return (
    <PageTransition>
      <div className="space-y-8">
        <div>
          <p className="text-xs text-muted-foreground mb-4">Dashboard / Live Repo</p>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="icon-badge bg-amber-100 dark:bg-amber-900/30">
                <GitBranch className="size-5 text-amber-600 dark:text-amber-400" />
              </div>
              <div>
                <h1 className="text-2xl font-bold tracking-tight">
                  <span className="text-gradient">Live Rule Repositories</span>
                </h1>
                <p className="text-sm text-muted-foreground">
                  Versioned policy repositories — one per product / jurisdiction.
                </p>
              </div>
            </div>

            <Dialog open={createOpen} onOpenChange={setCreateOpen}>
              <DialogTrigger render={<Button variant="default" />}>
                <Sparkles className="size-4" />
                Create Repository
              </DialogTrigger>
              <DialogContent className="sm:max-w-md">
                <DialogHeader>
                  <DialogTitle>Create Live Repository</DialogTitle>
                  <DialogDescription>
                    Define a new policy repository. The first BRD merged into it
                    will become version 1.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-3 py-2">
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium">Name</label>
                    <Input
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="e.g., US Personal Loans Live"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium">Product</label>
                      <Input
                        value={product}
                        onChange={(e) => setProduct(e.target.value)}
                        placeholder="e.g., personal_loan"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium">Jurisdiction</label>
                      <Input
                        value={jurisdiction}
                        onChange={(e) => setJurisdiction(e.target.value)}
                        placeholder="e.g., US"
                      />
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium">
                      Description{" "}
                      <span className="text-muted-foreground">(optional)</span>
                    </label>
                    <Input
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      placeholder="Short description of what this repo governs."
                    />
                  </div>
                </div>
                <DialogFooter>
                  <DialogClose render={<Button variant="outline" />}>
                    Cancel
                  </DialogClose>
                  <Button
                    variant="default"
                    onClick={handleCreate}
                    disabled={creating}
                  >
                    {creating && <Loader2 className="mr-2 size-4 animate-spin" />}
                    Create
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
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
            ) : repos.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <GitBranch className="size-12 text-muted-foreground/20" />
                <p className="mt-3 text-sm text-muted-foreground">
                  No repositories yet. Create one above to get started.
                </p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-amber-500/20">
                      Name
                    </TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-amber-500/20">
                      Product
                    </TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-amber-500/20">
                      Jurisdiction
                    </TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-amber-500/20">
                      Current Version
                    </TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-amber-500/20">
                      Updated
                    </TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-amber-500/20 text-right">
                      Actions
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {repos.map((repo) => (
                    <TableRow
                      key={repo.id}
                      className="group cursor-pointer transition-colors duration-150 hover:bg-accent/50"
                    >
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          <GitBranch className="size-4 text-amber-500" />
                          {repo.name}
                        </div>
                        {repo.description && (
                          <div className="text-xs text-muted-foreground mt-0.5 ml-6">
                            {repo.description}
                          </div>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{repo.product}</Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary">{repo.jurisdiction}</Badge>
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className="bg-amber-500/10 text-amber-600 border-amber-500/20 dark:text-amber-400"
                        >
                          v{repo.current_version}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {new Date(repo.updated_at).toLocaleDateString("en-US", {
                          year: "numeric",
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="default"
                          size="sm"
                          render={<Link href={`/live-repo/${repo.id}`} />}
                        >
                          View
                          <ArrowRight className="size-3.5" />
                        </Button>
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
