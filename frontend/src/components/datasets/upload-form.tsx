"use client";

import { useCallback, useRef, useState } from "react";
import { toast } from "sonner";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Upload, Loader2 } from "lucide-react";

interface UploadFormProps {
  onUploadComplete: () => void;
}

export function UploadForm({ onUploadComplete }: UploadFormProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!name.trim()) {
        toast.error("Please enter a dataset name.");
        return;
      }
      if (!file) {
        toast.error("Please select a file.");
        return;
      }

      setUploading(true);
      try {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("name", name.trim());
        if (description.trim()) {
          formData.append("description", description.trim());
        }
        await api.post("/datasets/upload", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        toast.success(`Dataset "${name}" uploaded successfully.`);
        setName("");
        setDescription("");
        setFile(null);
        if (fileRef.current) fileRef.current.value = "";
        onUploadComplete();
      } catch (err: any) {
        toast.error(
          err?.response?.data?.detail || "Failed to upload dataset."
        );
      } finally {
        setUploading(false);
      }
    },
    [name, description, file, onUploadComplete]
  );

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
        <Upload className="size-4" />
        Upload Dataset
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <label htmlFor="ds-name" className="text-sm font-medium">
            Name <span className="text-destructive">*</span>
          </label>
          <Input
            id="ds-name"
            placeholder="e.g. Q1 Customer Data"
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={uploading}
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="ds-file" className="text-sm font-medium">
            File <span className="text-destructive">*</span>
          </label>
          <Input
            id="ds-file"
            ref={fileRef}
            type="file"
            accept=".csv,.json"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            disabled={uploading}
          />
        </div>
      </div>

      <div className="space-y-2">
        <label htmlFor="ds-desc" className="text-sm font-medium">
          Description{" "}
          <span className="text-muted-foreground font-normal">(optional)</span>
        </label>
        <textarea
          id="ds-desc"
          rows={2}
          placeholder="Brief description of this dataset..."
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          disabled={uploading}
          className="flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:border-ring disabled:cursor-not-allowed disabled:opacity-50"
        />
      </div>

      <div className="flex justify-end">
        <Button type="submit" disabled={uploading || !name.trim() || !file}>
          {uploading ? (
            <Loader2 className="mr-2 size-4 animate-spin" />
          ) : (
            <Upload className="mr-2 size-4" />
          )}
          Upload
        </Button>
      </div>
    </form>
  );
}
