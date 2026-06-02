"use client";

import { cn } from "@/lib/utils";

interface ProgressRingProps {
  /** Completed count. */
  completed: number;
  /** Total stages. */
  total: number;
  /** Diameter in px. */
  size?: number;
  /** Stroke width in px. */
  stroke?: number;
  /** Optional className for the wrapping <div>. */
  className?: string;
}

/**
 * Concentric SVG rings showing pipeline completion at a glance:
 *  - Outer (background) ring is muted
 *  - Foreground arc fills clockwise as stages complete
 *  - Center shows "{completed}/{total}" stacked with the percentage
 *
 * The arc uses a vertical gradient (blue → emerald) so a pipeline going
 * from "just started" to "complete" reads as a transition from
 * exploration to validation.
 */
export function ProgressRing({
  completed,
  total,
  size = 88,
  stroke = 8,
  className,
}: ProgressRingProps) {
  const safeTotal = Math.max(total, 1);
  const pct = Math.min(1, Math.max(0, completed / safeTotal));
  const radius = (size - stroke) / 2;
  const circ = 2 * Math.PI * radius;
  const dash = circ * pct;

  return (
    <div className={cn("relative inline-flex", className)}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <defs>
          <linearGradient id="ring-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="hsl(220 70% 55%)" />
            <stop offset="100%" stopColor="hsl(160 70% 45%)" />
          </linearGradient>
        </defs>
        {/* track */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeOpacity={0.15}
          strokeWidth={stroke}
          className="text-muted-foreground"
        />
        {/* foreground arc */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="url(#ring-grad)"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circ - dash}`}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{
            transition: "stroke-dasharray 0.6s cubic-bezier(0.4, 0, 0.2, 1)",
          }}
        />
      </svg>
      {/* Center text */}
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-mono text-lg font-bold leading-none tabular-nums text-foreground">
          {completed}
          <span className="text-xs font-normal text-muted-foreground">
            /{total}
          </span>
        </span>
        <span className="mt-0.5 text-[9px] font-semibold uppercase tracking-wider text-muted-foreground">
          {Math.round(pct * 100)}% done
        </span>
      </div>
    </div>
  );
}
