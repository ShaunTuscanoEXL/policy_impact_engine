"use client";

import { useCallback, useRef, useState } from "react";
import { FileUp, CheckCircle, Loader2, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

type DropzoneStatus = "idle" | "dragover" | "uploading" | "success" | "error";

interface UploadDropzoneProps {
  onUpload: (file: File) => Promise<void>;
  accept?: string;
}

export function UploadDropzone({
  onUpload,
  accept = ".pdf,.docx",
}: UploadDropzoneProps) {
  const [status, setStatus] = useState<DropzoneStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    async (file: File) => {
      const validTypes = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      ];
      const validExtensions = [".pdf", ".docx"];
      const ext = file.name.toLowerCase().slice(file.name.lastIndexOf("."));

      if (!validTypes.includes(file.type) && !validExtensions.includes(ext)) {
        setStatus("error");
        setErrorMessage("Only .pdf and .docx files are accepted.");
        return;
      }

      setStatus("uploading");
      setErrorMessage("");
      try {
        await onUpload(file);
        setStatus("success");
        setTimeout(() => setStatus("idle"), 3000);
      } catch (err: any) {
        setStatus("error");
        setErrorMessage(err?.message || "Upload failed. Please try again.");
      }
    },
    [onUpload]
  );

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setStatus("dragover");
  }, []);

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setStatus("idle");
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setStatus("idle");
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const onFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
      if (inputRef.current) inputRef.current.value = "";
    },
    [handleFile]
  );

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => status !== "uploading" && inputRef.current?.click()}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          if (status !== "uploading") inputRef.current?.click();
        }
      }}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      className={cn(
        "relative flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-10 text-center transition-colors cursor-pointer",
        status === "idle" &&
          "border-muted-foreground/25 hover:border-muted-foreground/50 hover:bg-muted/50",
        status === "dragover" && "border-primary bg-primary/5",
        status === "uploading" && "border-muted-foreground/25 bg-muted/30 cursor-wait",
        status === "success" && "border-green-500/50 bg-green-50 dark:bg-green-950/20",
        status === "error" && "border-destructive/50 bg-destructive/5"
      )}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        onChange={onFileSelect}
        className="hidden"
      />

      {status === "idle" && (
        <>
          <FileUp className="size-10 text-muted-foreground" />
          <div>
            <p className="text-sm font-medium">
              Drag & drop your BRD here or click to browse
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Supports PDF and DOCX files
            </p>
          </div>
        </>
      )}

      {status === "dragover" && (
        <>
          <FileUp className="size-10 text-primary" />
          <p className="text-sm font-medium text-primary">Drop your file here</p>
        </>
      )}

      {status === "uploading" && (
        <>
          <Loader2 className="size-10 text-primary animate-spin" />
          <p className="text-sm font-medium">Uploading...</p>
        </>
      )}

      {status === "success" && (
        <>
          <CheckCircle className="size-10 text-green-600 dark:text-green-400" />
          <p className="text-sm font-medium text-green-700 dark:text-green-300">
            Upload successful!
          </p>
        </>
      )}

      {status === "error" && (
        <>
          <AlertCircle className="size-10 text-destructive" />
          <div>
            <p className="text-sm font-medium text-destructive">Upload failed</p>
            {errorMessage && (
              <p className="mt-1 text-xs text-destructive/80">{errorMessage}</p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
