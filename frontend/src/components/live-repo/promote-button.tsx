"use client";

import { useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Rocket, CheckCircle2 } from "lucide-react";
import { DecisionDialog } from "@/components/decision-dialog";
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
 * "Promote to Production" CTA. Confirms via DecisionDialog so we capture
 * who promoted + (optionally) why before flipping the repo's
 * production_version_id pointer. Used on the version timeline,
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
  const isRollback =
    currentProductionVersionNumber != null &&
    versionNumber < currentProductionVersionNumber;
  const buttonLabel =
    label ??
    (isCurrentProduction
      ? "Currently Live"
      : isRollback
        ? "Roll Back to This Version"
        : "Promote to Production");

  const handlePromoteConfirm = async ({
    actor,
    rationale,
  }: {
    actor: string;
    rationale: string;
  }) => {
    setBusy(true);
    try {
      const { data } = await api.post<PromoteVersionResponse>(
        `/live-repo/${repoId}/promote`,
        {
          version_number: versionNumber,
          promoted_by: actor,
          rationale: rationale || null,
        },
      );
      toast.success(
        `v${data.production_version_number} is now live in production (promoted by ${actor}).`,
      );
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

  const description =
    currentProductionVersionNumber != null
      ? `Replaces v${currentProductionVersionNumber} as the live policy. Decisions made after this point will use v${versionNumber}.`
      : `This is the first version to be promoted. Decisions made after this point will use v${versionNumber}.`;

  return (
    <>
      <Button variant={variant} size={size} onClick={() => setOpen(true)}>
        <Rocket className="size-3.5" />
        {buttonLabel}
      </Button>
      <DecisionDialog
        open={open}
        onOpenChange={setOpen}
        title={`Promote v${versionNumber} to production?`}
        description={description}
        confirmLabel={`Promote v${versionNumber}`}
        confirmVariant={isRollback ? "destructive" : "default"}
        rationalePlaceholder="e.g. all 142 scenario tests pass + impact rate change within tolerance"
        loading={busy}
        onConfirm={handlePromoteConfirm}
      />
    </>
  );
}
