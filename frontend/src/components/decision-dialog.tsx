"use client";

/**
 * DecisionDialog — modal that captures `actor` + optional `rationale`
 * before any verb-button takes effect. Used by Approve / Apply Merge /
 * Promote / Run Impact / Execute Suite.
 *
 * The actor name persists across actions via localStorage so the user
 * doesn't retype it every time. The dialog can either be controlled
 * (via `open`/`onOpenChange`) or render its own trigger (via
 * `triggerLabel` + `triggerProps`).
 *
 * The caller owns the actual mutation — DecisionDialog only collects
 * the metadata and hands it back via `onConfirm({ actor, rationale })`.
 */
import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2 } from "lucide-react";
import { getStoredActor, setStoredActor } from "@/lib/actor-store";

export type DecisionPayload = {
  actor: string;
  rationale: string;
};

type Props = {
  open: boolean;
  onOpenChange: (next: boolean) => void;
  /** Header copy, e.g. "Approve rule set" or "Apply merge proposal". */
  title: string;
  /** Sub-copy describing exactly what will happen on confirm. */
  description?: string;
  /** Label for the confirm button — defaults to "Confirm". */
  confirmLabel?: string;
  /** Tailwind variant for the confirm button (e.g. "destructive"). */
  confirmVariant?:
    | "default"
    | "destructive"
    | "outline"
    | "secondary"
    | "ghost"
    | "link";
  /** Optional placeholder for the rationale textarea. */
  rationalePlaceholder?: string;
  /** Label that names the actor field — defaults to "Your name". */
  actorLabel?: string;
  /** When true the confirm button shows a spinner and disables itself. */
  loading?: boolean;
  /**
   * Receives the captured actor + rationale. The caller is responsible
   * for closing the dialog (typically by setting open=false in the
   * promise's `finally`) and surfacing toasts.
   */
  onConfirm: (payload: DecisionPayload) => void | Promise<void>;
};

export function DecisionDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Confirm",
  confirmVariant = "default",
  rationalePlaceholder = "Optional — capture why for the audit timeline.",
  actorLabel = "Your name",
  loading = false,
  onConfirm,
}: Props) {
  const [actor, setActor] = useState("");
  const [rationale, setRationale] = useState("");

  // Pre-fill actor from localStorage every time the dialog opens so the
  // user doesn't retype it for every action in the session.
  useEffect(() => {
    if (open) {
      setActor(getStoredActor());
      setRationale("");
    }
  }, [open]);

  const handleConfirm = async () => {
    const trimmedActor = actor.trim();
    if (!trimmedActor) return; // Button is disabled too; defense-in-depth.
    setStoredActor(trimmedActor);
    await onConfirm({
      actor: trimmedActor,
      rationale: rationale.trim(),
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>

        <div className="space-y-3">
          <div className="space-y-1.5">
            <label
              htmlFor="decision-dialog-actor"
              className="text-xs font-medium text-foreground"
            >
              {actorLabel} <span className="text-destructive">*</span>
            </label>
            <Input
              id="decision-dialog-actor"
              value={actor}
              onChange={(e) => setActor(e.target.value)}
              placeholder="e.g. anita.kapoor"
              maxLength={128}
              autoFocus
              disabled={loading}
            />
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="decision-dialog-rationale"
              className="text-xs font-medium text-foreground"
            >
              Reason{" "}
              <span className="text-muted-foreground font-normal">
                (optional — for the audit log)
              </span>
            </label>
            <textarea
              id="decision-dialog-rationale"
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
              placeholder={rationalePlaceholder}
              maxLength={2000}
              rows={3}
              disabled={loading}
              className="flex min-h-[60px] w-full rounded-lg border border-input bg-transparent px-3 py-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/20 disabled:cursor-not-allowed disabled:opacity-50"
            />
            <p className="text-[10px] text-muted-foreground">
              Your name persists across actions. The reason is shown in the
              per-BRD timeline and on the affected entity.
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="ghost"
            onClick={() => onOpenChange(false)}
            disabled={loading}
          >
            Cancel
          </Button>
          <Button
            variant={confirmVariant}
            onClick={handleConfirm}
            disabled={loading || !actor.trim()}
          >
            {loading && <Loader2 className="mr-2 size-3.5 animate-spin" />}
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
