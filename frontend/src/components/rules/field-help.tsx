"use client";

/**
 * FieldHelp — wrap any field-name token to add a hover tooltip with
 * the plain-English definition + sample range. No-op when the field
 * isn't in the glossary, so it's safe to wrap unknowns.
 *
 *   <FieldHelp name="bureau_score">bureau_score</FieldHelp>
 *
 * Uses Base UI's Popover (already in the design system) with hover-
 * trigger semantics so it Just Works on touch devices too.
 */
import { type ReactNode } from "react";
import { lookupField } from "@/lib/field-glossary";
import { cn } from "@/lib/utils";
import {
  Activity,
  Percent,
  DollarSign,
  Tag,
  ToggleRight,
  Gavel,
  Info,
} from "lucide-react";

interface Props {
  name: string;
  children: ReactNode;
  className?: string;
}

const KIND_ICON = {
  score: Activity,
  ratio: Percent,
  currency: DollarSign,
  categorical: Tag,
  boolean: ToggleRight,
  decision: Gavel,
} as const;

export function FieldHelp({ name, children, className }: Props) {
  const def = lookupField(name);
  if (!def) {
    return <span className={className}>{children}</span>;
  }
  const Icon = KIND_ICON[def.kind] ?? Info;

  // Native title= gives a free, accessible tooltip on every platform
  // without pulling in a heavy popover dependency. The visual
  // border-bottom marks the term as definable for the user. Built-in
  // tooltips truncate aggressively, so we encode the structured
  // sections as a plain-text block.
  const tooltip = [
    def.label,
    "",
    def.description,
    def.range ? `Range: ${def.range}` : "",
    def.source ? `Source: ${def.source}` : "",
  ]
    .filter(Boolean)
    .join("\n");

  return (
    <span
      className={cn(
        "group/fieldhelp inline-flex items-center gap-1 cursor-help border-b border-dashed border-foreground/30 hover:border-foreground/70",
        className,
      )}
      title={tooltip}
    >
      <Icon className="size-3 text-muted-foreground opacity-60 group-hover/fieldhelp:opacity-100" />
      {children}
    </span>
  );
}
