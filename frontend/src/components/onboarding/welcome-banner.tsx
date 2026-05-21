"use client";

/**
 * WelcomeBanner — Slice 8 dismissible "what is this thing" panel that
 * shows up on the dashboard until the user clicks "Got it". Persists
 * the dismissed state in localStorage so it doesn't follow them
 * around.
 *
 * Designed to be invisible after the first time so power users aren't
 * pestered. Includes a 5-step pipeline mini-tour matching the
 * BRD-pipeline phases (Upload → Extract → Approve → Merge → Validate).
 */
import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Sparkles,
  Upload,
  ScrollText,
  CheckCircle,
  GitMerge,
  ShieldCheck,
  X,
} from "lucide-react";

const STORAGE_KEY = "ruflo.welcome.dismissed.v1";

export function WelcomeBanner() {
  const [dismissed, setDismissed] = useState<boolean>(true); // start hidden to avoid SSR flash

  useEffect(() => {
    if (typeof window === "undefined") return;
    const value = window.localStorage.getItem(STORAGE_KEY);
    setDismissed(value === "1");
  }, []);

  const handleDismiss = () => {
    if (typeof window !== "undefined") {
      try {
        window.localStorage.setItem(STORAGE_KEY, "1");
      } catch {
        /* ignore quota / private mode */
      }
    }
    setDismissed(true);
  };

  if (dismissed) return null;

  const steps = [
    {
      Icon: Upload,
      title: "Upload",
      sub: "PDF / DOCX policy doc",
      tone: "text-blue-600 dark:text-blue-400 bg-blue-500/10",
    },
    {
      Icon: ScrollText,
      title: "Extract",
      sub: "AI distills rules",
      tone: "text-cyan-600 dark:text-cyan-400 bg-cyan-500/10",
    },
    {
      Icon: CheckCircle,
      title: "Approve",
      sub: "Reviewer signs off",
      tone: "text-emerald-600 dark:text-emerald-400 bg-emerald-500/10",
    },
    {
      Icon: GitMerge,
      title: "Merge",
      sub: "Reconcile w/ live repo",
      tone: "text-violet-600 dark:text-violet-400 bg-violet-500/10",
    },
    {
      Icon: ShieldCheck,
      title: "Validate",
      sub: "Impact + scenario tests",
      tone: "text-fuchsia-600 dark:text-fuchsia-400 bg-fuchsia-500/10",
    },
  ];

  return (
    <Card className="card-elevated relative overflow-hidden border-blue-500/30 bg-gradient-to-br from-blue-500/[0.04] to-violet-500/[0.04]">
      <button
        type="button"
        onClick={handleDismiss}
        aria-label="Dismiss welcome banner"
        className="absolute right-2 top-2 rounded-full p-1 text-muted-foreground hover:bg-muted/40 hover:text-foreground"
      >
        <X className="size-4" />
      </button>
      <CardContent className="space-y-4 p-5">
        <div className="flex items-start gap-3">
          <div className="rounded-lg bg-blue-500/15 p-2 ring-1 ring-inset ring-blue-500/30">
            <Sparkles className="size-5 text-blue-600 dark:text-blue-400" />
          </div>
          <div className="space-y-1">
            <h2 className="text-base font-semibold">
              Welcome to the Policy Impact Engine
            </h2>
            <p className="text-sm text-muted-foreground">
              This dashboard is your mission control for translating policy
              documents into live, validated lending rules. Every BRD flows
              through five stages — track it from upload to production
              without leaving this view.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          {steps.map((s, i) => (
            <div
              key={i}
              className="flex items-start gap-2 rounded-lg border border-border/50 bg-background/50 p-3"
            >
              <div className={`rounded-md p-1.5 ${s.tone}`}>
                <s.Icon className="size-3.5" />
              </div>
              <div className="space-y-0.5 min-w-0">
                <p className="text-xs font-semibold">
                  {i + 1}. {s.title}
                </p>
                <p className="truncate text-[10px] text-muted-foreground">
                  {s.sub}
                </p>
              </div>
            </div>
          ))}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
          <p className="text-[11px] italic text-muted-foreground">
            Tip: hover any field name in a rule (like{" "}
            <code className="rounded bg-muted px-1">bureau_score</code>) to see
            its plain-English definition and typical range.
          </p>
          <Button size="sm" variant="default" onClick={handleDismiss}>
            Got it
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
