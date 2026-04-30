"use client";

import { useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
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
import { Loader2, Rocket, CheckCircle2 } from "lucide-react";
import type { PromoteVersionResponse } from "@/lib/types";

interface PromoteToProductionButtonProps {
  repoId: string;
  versionNumber: number;
  /** Currently-live version number — used to render the right copy
   *  (Promote vs Re-promote vs disabled). */
  currentProductionVersionNumber?: number | null;
  /** Optional label ("Promote to Production" by default; pass "Roll Back"
   *  when promoting an older version). */
  label?: string;
  size?: "default" | "sm" | "icon" | "icon-sm";
  variant?: "default" | "outline" | "ghost" | "secondary";
  onPromoted?: (response: PromoteVersionResponse) => void;
}

/**
 * "Promote to Production" CTA. Confirms via dialog before flipping the
 * repo's production_version_id pointer. Used on the version timeline,
 * impact-run detail, and validate-version pages.
 */
export function PromoteToProductionButton({
  repoId,
  versionNumber,
  currentProductionVersionNumber,
  label,
  size = "sm",
  variant = "outline",
  onPromoted,
}: PromoteToProductionButtonProps) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const isCurrentProduction = currentProductionVersionNumber === versionNumber;
  const buttonLabel =
    label ??
    (isCurrentProduction
      ? "Currently Live"
      : currentProductionVersionNumber != null && versionNumber < currentProductionVersionNumber
        ? "Roll Back to This Version"
        : "Promote to Production");

  const handlePromote = async () => {
    setBusy(true);
    try {
      const { data } = await api.post<PromoteVersionResponse>(
        `/live-repo/${repoId}/promote`,
        { version_number: versionNumber },
      );
      toast.success(`v${data.production_version_number} is now live in production.`);
      setOpen(false);
      onPromoted?.(data);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Promotion failed.");
    } finally {
      setBusy(false);
    }
  };

  if (isCurrentProduction) {
    return (
      <Button variant="ghost" size={size} disabled className="gap-1.5">
        <CheckCircle2 className="size-3.5 text-emerald-600 dark:text-emerald-400" />
        {buttonLabel}
      </Button>
    );
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button variant={variant} size={size} />}>
        <Rocket className="size-3.5" />
        {buttonLabel}
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Promote v{versionNumber} to production?</DialogTitle>
          <DialogDescription>
            {currentProductionVersionNumber != null ? (
              <>
                This will replace v{currentProductionVersionNumber} as the live
                policy. Decisions made after this point will use v{versionNumber}.
              </>
            ) : (
              <>
                This is the first version to be promoted. Decisions made after
                this point will use v{versionNumber}.
              </>
            )}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose render={<Button variant="outline" />}>Cancel</DialogClose>
          <Button onClick={handlePromote} disabled={busy}>
            {busy && <Loader2 className="mr-2 size-4 animate-spin" />}
            Promote v{versionNumber}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
