"use client";

/**
 * EmptyState — reusable "nothing here yet" panel for first-run UX.
 *
 * Use anywhere a list/table can be empty (no BRDs, no rule sets, no
 * impact runs, no test suites). Beats a blank screen because it tells
 * the user (a) why it's empty, (b) how to get unstuck.
 *
 *   <EmptyState
 *     icon={FileText}
 *     title="No BRDs uploaded yet"
 *     description="Upload a BRD (PDF or DOCX) to start the rule-extraction pipeline."
 *     primaryAction={{ label: "Upload BRD", onClick: openUploader }}
 *     secondaryAction={{ label: "View example", href: "/docs/example" }}
 *   />
 */
import type { LucideIcon } from "lucide-react";
import { type ReactNode } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface ActionLink {
  label: string;
  href?: string;
  onClick?: () => void;
}

interface Props {
  icon: LucideIcon;
  title: string;
  description?: string;
  primaryAction?: ActionLink;
  secondaryAction?: ActionLink;
  /** Optional bullet list of "what comes next" hints. */
  hints?: string[];
  className?: string;
  /** Render inline (no card chrome) for tight spaces. */
  variant?: "card" | "inline";
  /** Optional tone — picks the icon background colour. */
  tone?: "blue" | "violet" | "emerald" | "amber" | "rose" | "slate";
  /** Slot for ad-hoc rich content (a screenshot, a tutorial video, etc.). */
  children?: ReactNode;
}

const TONE_BG: Record<NonNullable<Props["tone"]>, string> = {
  blue: "bg-blue-500/10 ring-blue-500/30 text-blue-600 dark:text-blue-400",
  violet: "bg-violet-500/10 ring-violet-500/30 text-violet-600 dark:text-violet-400",
  emerald: "bg-emerald-500/10 ring-emerald-500/30 text-emerald-600 dark:text-emerald-400",
  amber: "bg-amber-500/10 ring-amber-500/30 text-amber-600 dark:text-amber-400",
  rose: "bg-rose-500/10 ring-rose-500/30 text-rose-600 dark:text-rose-400",
  slate: "bg-slate-500/10 ring-slate-500/30 text-slate-600 dark:text-slate-400",
};

function ActionButton({ action, primary }: { action: ActionLink; primary: boolean }) {
  if (action.href) {
    return (
      <Button
        variant={primary ? "default" : "outline"}
        size="sm"
        render={<Link href={action.href} />}
      >
        {action.label}
      </Button>
    );
  }
  return (
    <Button
      variant={primary ? "default" : "outline"}
      size="sm"
      onClick={action.onClick}
    >
      {action.label}
    </Button>
  );
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  primaryAction,
  secondaryAction,
  hints,
  className,
  variant = "card",
  tone = "slate",
  children,
}: Props) {
  const inner = (
    <div className="flex flex-col items-center text-center gap-4 py-10 px-4">
      <div
        className={cn(
          "flex size-14 items-center justify-center rounded-2xl ring-1 ring-inset",
          TONE_BG[tone],
        )}
      >
        <Icon className="size-7" />
      </div>
      <div className="space-y-1.5 max-w-md">
        <h3 className="text-base font-semibold">{title}</h3>
        {description && (
          <p className="text-sm text-muted-foreground">{description}</p>
        )}
      </div>

      {hints && hints.length > 0 && (
        <ul className="space-y-1 text-left text-xs text-muted-foreground max-w-md">
          {hints.map((h, i) => (
            <li key={i} className="flex items-start gap-2">
              <span className="mt-[5px] size-1 shrink-0 rounded-full bg-muted-foreground" />
              <span>{h}</span>
            </li>
          ))}
        </ul>
      )}

      {(primaryAction || secondaryAction) && (
        <div className="flex flex-wrap items-center justify-center gap-2 pt-1">
          {primaryAction && <ActionButton action={primaryAction} primary />}
          {secondaryAction && (
            <ActionButton action={secondaryAction} primary={false} />
          )}
        </div>
      )}

      {children}
    </div>
  );

  if (variant === "inline") {
    return <div className={className}>{inner}</div>;
  }
  return (
    <Card className={cn("card-elevated border-dashed border-border/50", className)}>
      <CardContent className="p-0">{inner}</CardContent>
    </Card>
  );
}
