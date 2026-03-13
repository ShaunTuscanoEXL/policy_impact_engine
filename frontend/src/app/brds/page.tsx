"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import api from "@/lib/api";
import type { BrdDocument } from "@/lib/types";
import { toast } from "sonner";
import { UploadDropzone } from "@/components/brds/upload-dropzone";
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
import { FileText, Eye, Trash2, Loader2 } from "lucide-react";

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
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">BRD Documents</h1>
        <p className="mt-2 text-muted-foreground">
          Upload and manage Business Requirements Documents.
        </p>
      </div>

      {/* Upload Section */}
      <Card className="p-6">
        <UploadDropzone onUpload={handleUpload} />
      </Card>

      {/* BRD List Section */}
      <Card>
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="size-6 animate-spin text-muted-foreground" />
          </div>
        ) : brds.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <FileText className="size-10 text-muted-foreground/40" />
            <p className="mt-3 text-sm text-muted-foreground">
              No BRD documents yet. Upload one above to get started.
            </p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Filename</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Uploaded At</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {brds.map((brd) => (
                <TableRow key={brd.id}>
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      <FileText className="size-4 text-muted-foreground" />
                      {brd.filename}
                    </div>
                  </TableCell>
                  <TableCell>{fileTypeBadge(brd.file_type)}</TableCell>
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
                    <div className="flex items-center justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        render={<Link href={`/brds/${brd.id}`} />}
                      >
                        <Eye className="size-4" />
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
    </div>
  );
}
