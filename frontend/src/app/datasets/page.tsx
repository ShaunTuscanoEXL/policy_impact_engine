"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import api from "@/lib/api";
import type { Dataset } from "@/lib/types";
import { toast } from "sonner";
import { UploadForm } from "@/components/datasets/upload-form";
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
import { Database, Eye, Trash2, Loader2 } from "lucide-react";

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const fetchDatasets = useCallback(async () => {
    try {
      const { data } = await api.get("/datasets");
      setDatasets(data);
    } catch {
      toast.error("Failed to load datasets.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDatasets();
  }, [fetchDatasets]);

  const handleDelete = useCallback(async (id: string) => {
    setDeleting(true);
    try {
      await api.delete(`/datasets/${id}`);
      toast.success("Dataset deleted.");
      setDatasets((prev) => prev.filter((d) => d.id !== id));
    } catch {
      toast.error("Failed to delete dataset.");
    } finally {
      setDeleting(false);
      setDeleteId(null);
    }
  }, []);

  const fileTypeBadge = (type: string) => {
    const upper = type.toUpperCase();
    if (upper.includes("CSV")) {
      return <Badge variant="secondary">CSV</Badge>;
    }
    if (upper.includes("JSON")) {
      return <Badge variant="outline">JSON</Badge>;
    }
    return <Badge variant="outline">{upper}</Badge>;
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Datasets</h1>
        <p className="mt-2 text-muted-foreground">
          Upload and manage customer datasets for simulation.
        </p>
      </div>

      {/* Upload Section */}
      <Card className="p-6">
        <UploadForm onUploadComplete={fetchDatasets} />
      </Card>

      {/* Dataset List */}
      <Card>
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="size-6 animate-spin text-muted-foreground" />
          </div>
        ) : datasets.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <Database className="size-10 text-muted-foreground/40" />
            <p className="mt-3 text-sm text-muted-foreground">
              No datasets yet. Upload one above to get started.
            </p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Type</TableHead>
                <TableHead className="text-right">Rows</TableHead>
                <TableHead>Created At</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {datasets.map((ds) => (
                <TableRow key={ds.id}>
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      <Database className="size-4 text-muted-foreground" />
                      {ds.name}
                    </div>
                  </TableCell>
                  <TableCell>{fileTypeBadge(ds.file_type)}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {ds.row_count.toLocaleString()}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(ds.created_at).toLocaleDateString("en-US", {
                      year: "numeric",
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        render={<Link href={`/datasets/${ds.id}`} />}
                      >
                        <Eye className="size-4" />
                      </Button>

                      <Dialog
                        open={deleteId === ds.id}
                        onOpenChange={(open) =>
                          setDeleteId(open ? ds.id : null)
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
                            <DialogTitle>Delete Dataset</DialogTitle>
                            <DialogDescription>
                              Are you sure you want to delete &ldquo;
                              {ds.name}&rdquo;? This action cannot be undone.
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
                              onClick={() => handleDelete(ds.id)}
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
    </div>
  );
}
