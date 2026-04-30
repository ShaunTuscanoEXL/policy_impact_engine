"use client";

import { useEffect, useState, useMemo, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import api from "@/lib/api";
import { Bell, Search, GitMerge, AlertCircle, X, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";
import type {
  DashboardActivityEvent,
  DashboardStats,
  BrdDocument,
  LiveRepository,
} from "@/lib/types";

interface CmdItem {
  key: string;
  title: string;
  subtitle?: string;
  href: string;
  group: "Pages" | "BRDs" | "Repos" | "Recent";
}

const STATIC_PAGES: CmdItem[] = [
  { key: "p:dash", title: "Dashboard", subtitle: "Mission control", href: "/", group: "Pages" },
  { key: "p:brds", title: "BRDs", subtitle: "Upload + manage business requirements", href: "/brds", group: "Pages" },
  { key: "p:loans", title: "Loan Records", subtitle: "Browse the loan corpus", href: "/loan-records", group: "Pages" },
  { key: "p:tests", title: "Test Suites", subtitle: "Generated scenario tests", href: "/test-suites", group: "Pages" },
  { key: "p:repo", title: "Live Repo", subtitle: "Versioned policy repositories", href: "/live-repo", group: "Pages" },
  { key: "p:merge", title: "Merge Workbench", subtitle: "Resolve merge proposals", href: "/merge-workbench", group: "Pages" },
  { key: "p:impact", title: "Impact Runs", subtitle: "Compare versions on the loan corpus", href: "/impact-runs", group: "Pages" },
];

/**
 * Sticky topbar — search CTA on the left (opens Cmd+K palette) and a
 * notifications bell on the right (live count of pending merges + recent
 * activity). Sits above every page next to the sidebar.
 */
export function TopBar() {
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [bellOpen, setBellOpen] = useState(false);

  // Stats for the bell badge
  const [pendingCount, setPendingCount] = useState(0);
  const [activity, setActivity] = useState<DashboardActivityEvent[]>([]);

  // Load command palette data sources
  const [brds, setBrds] = useState<BrdDocument[]>([]);
  const [repos, setRepos] = useState<LiveRepository[]>([]);

  const loadAmbient = useCallback(async () => {
    try {
      const [statsRes, actRes, brdRes, repoRes] = await Promise.allSettled([
        api.get<DashboardStats>("/dashboard"),
        api.get<DashboardActivityEvent[]>("/dashboard/activity?limit=8"),
        api.get<BrdDocument[]>("/brds"),
        api.get<LiveRepository[]>("/live-repo"),
      ]);
      if (statsRes.status === "fulfilled") {
        setPendingCount(statsRes.value.data.pending_merge_queue?.count ?? 0);
      }
      if (actRes.status === "fulfilled") {
        setActivity(actRes.value.data);
      }
      if (brdRes.status === "fulfilled") setBrds(brdRes.value.data);
      if (repoRes.status === "fulfilled") setRepos(repoRes.value.data);
    } catch {
      /* tolerable — topbar is best-effort */
    }
  }, []);

  useEffect(() => {
    loadAmbient();
    const t = setInterval(loadAmbient, 30000); // refresh every 30s
    return () => clearInterval(t);
  }, [loadAmbient]);

  // Cmd+K listener
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen(true);
      }
      if (e.key === "Escape") {
        setPaletteOpen(false);
        setBellOpen(false);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // Build the union list of palette items
  const items: CmdItem[] = useMemo(() => {
    const dynamic: CmdItem[] = [];
    for (const b of brds.slice(0, 25)) {
      dynamic.push({
        key: `b:${b.id}`,
        title: b.filename,
        subtitle: `BRD · ${b.total_rules ?? 0} rules`,
        href: `/brds/${b.id}`,
        group: "BRDs",
      });
    }
    for (const r of repos.slice(0, 25)) {
      dynamic.push({
        key: `r:${r.id}`,
        title: r.name,
        subtitle: `Repo · ${r.product}/${r.jurisdiction} · v${r.current_version}`,
        href: `/live-repo/${r.id}`,
        group: "Repos",
      });
    }
    return [...STATIC_PAGES, ...dynamic];
  }, [brds, repos]);

  return (
    <>
      <header
        className="fixed inset-x-0 top-0 z-40 flex h-12 items-center gap-3 border-b border-border/40 bg-background/80 px-4 pl-20 backdrop-blur-md"
        role="banner"
      >
        {/* Spacer to align with sidebar */}
        <div className="flex-1">
          <button
            type="button"
            onClick={() => setPaletteOpen(true)}
            className="group inline-flex h-8 w-full max-w-md items-center gap-2 rounded-lg border border-border/50 bg-card/40 px-3 text-xs text-muted-foreground transition-all hover:border-foreground/20 hover:bg-card"
          >
            <Search className="size-3.5" />
            <span className="flex-1 text-left">Search BRDs, repos, pages…</span>
            <kbd className="hidden rounded border border-border/60 bg-muted/40 px-1.5 py-0.5 font-mono text-[10px] sm:inline-block">
              ⌘K
            </kbd>
          </button>
        </div>

        {/* Notifications bell */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setBellOpen((o) => !o)}
            aria-label="Notifications"
            className={cn(
              "relative flex size-8 items-center justify-center rounded-lg transition-colors",
              bellOpen
                ? "bg-accent text-foreground"
                : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            <Bell className="size-4" />
            {pendingCount > 0 && (
              <span className="absolute -right-1 -top-1 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-amber-500 px-1 text-[9px] font-bold text-white">
                {pendingCount}
              </span>
            )}
          </button>

          {bellOpen && (
            <NotificationsPanel
              pendingCount={pendingCount}
              activity={activity}
              onClose={() => setBellOpen(false)}
            />
          )}
        </div>
      </header>

      {paletteOpen && (
        <CommandPalette
          items={items}
          onClose={() => setPaletteOpen(false)}
        />
      )}
    </>
  );
}

// ── Notifications dropdown ──────────────────────────────────────────────


function NotificationsPanel({
  pendingCount,
  activity,
  onClose,
}: {
  pendingCount: number;
  activity: DashboardActivityEvent[];
  onClose: () => void;
}) {
  return (
    <>
      {/* click-outside backdrop */}
      <div
        className="fixed inset-0 z-30"
        onClick={onClose}
        aria-hidden
      />
      <div className="absolute right-0 top-10 z-40 w-80 overflow-hidden rounded-xl border border-border/60 bg-popover shadow-lg">
        <div className="flex items-center justify-between border-b border-border/40 px-3 py-2">
          <span className="text-xs font-semibold tracking-tight">
            Notifications
          </span>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground"
            aria-label="Close"
          >
            <X className="size-3.5" />
          </button>
        </div>
        <div className="max-h-80 overflow-y-auto p-2">
          {pendingCount > 0 && (
            <Link
              href="/merge-workbench"
              onClick={onClose}
              className="mb-2 flex items-start gap-2 rounded-lg bg-amber-500/10 p-2 ring-1 ring-inset ring-amber-500/20"
            >
              <GitMerge className="mt-0.5 size-4 text-amber-600 dark:text-amber-400" />
              <div className="flex-1">
                <p className="text-xs font-semibold text-amber-700 dark:text-amber-300">
                  {pendingCount} merge proposal
                  {pendingCount === 1 ? "" : "s"} awaiting decision
                </p>
                <p className="text-[11px] text-amber-600/80 dark:text-amber-400/80">
                  Open the workbench to resolve them.
                </p>
              </div>
              <ArrowRight className="size-3.5 text-amber-600/60" />
            </Link>
          )}
          {activity.length === 0 ? (
            <p className="py-6 text-center text-xs italic text-muted-foreground">
              No recent activity.
            </p>
          ) : (
            <ul className="space-y-0.5">
              {activity.map((e, i) => (
                <li key={`${e.type}-${i}-${e.ts}`}>
                  <Link
                    href={e.href}
                    onClick={onClose}
                    className="block rounded-lg p-2 hover:bg-accent/50"
                  >
                    <p className="truncate text-xs font-medium">{e.title}</p>
                    {e.subtitle && (
                      <p className="truncate text-[10px] text-muted-foreground">
                        {e.subtitle}
                      </p>
                    )}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </>
  );
}

// ── Command palette ────────────────────────────────────────────────────


function CommandPalette({
  items,
  onClose,
}: {
  items: CmdItem[];
  onClose: () => void;
}) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (i) =>
        i.title.toLowerCase().includes(q) ||
        (i.subtitle ?? "").toLowerCase().includes(q) ||
        i.group.toLowerCase().includes(q),
    );
  }, [items, query]);

  // Group filtered items by group, preserving stable group order
  const grouped = useMemo(() => {
    const order: CmdItem["group"][] = ["Pages", "BRDs", "Repos", "Recent"];
    const map: Partial<Record<CmdItem["group"], CmdItem[]>> = {};
    for (const item of filtered) {
      (map[item.group] ??= []).push(item);
    }
    return order
      .filter((g) => map[g] && map[g]!.length > 0)
      .map((g) => ({ group: g, items: map[g]! }));
  }, [filtered]);

  // Flat ordered list for keyboard navigation
  const flatOrdered = useMemo(
    () => grouped.flatMap((g) => g.items),
    [grouped],
  );

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIndex((i) => Math.min(flatOrdered.length - 1, i + 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIndex((i) => Math.max(0, i - 1));
      } else if (e.key === "Enter") {
        e.preventDefault();
        const target = flatOrdered[activeIndex];
        if (target) {
          router.push(target.href);
          onClose();
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [flatOrdered, activeIndex, router, onClose]);

  return (
    <div
      role="dialog"
      aria-modal
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 px-4 pt-[10vh] backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg overflow-hidden rounded-xl border border-border/60 bg-popover shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 border-b border-border/40 px-3 py-2">
          <Search className="size-4 text-muted-foreground" />
          <input
            autoFocus
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search BRDs, repos, pages…"
            className="flex-1 bg-transparent text-sm focus:outline-none"
          />
          <kbd className="rounded border border-border/60 bg-muted/40 px-1.5 py-0.5 font-mono text-[10px]">
            esc
          </kbd>
        </div>
        <div className="max-h-[60vh] overflow-y-auto py-1">
          {grouped.length === 0 ? (
            <p className="px-3 py-6 text-center text-xs italic text-muted-foreground">
              No matches for &ldquo;{query}&rdquo;.
            </p>
          ) : (
            grouped.map(({ group, items: groupItems }) => (
              <div key={group} className="px-1.5 py-1">
                <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  {group}
                </p>
                <ul className="space-y-0.5">
                  {groupItems.map((item) => {
                    const flatIdx = flatOrdered.indexOf(item);
                    const isActive = flatIdx === activeIndex;
                    return (
                      <li key={item.key}>
                        <button
                          type="button"
                          className={cn(
                            "flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm",
                            isActive
                              ? "bg-accent text-accent-foreground"
                              : "hover:bg-accent/50",
                          )}
                          onMouseEnter={() => setActiveIndex(flatIdx)}
                          onClick={() => {
                            router.push(item.href);
                            onClose();
                          }}
                        >
                          <div className="flex-1 min-w-0">
                            <p className="truncate text-xs font-medium">
                              {item.title}
                            </p>
                            {item.subtitle && (
                              <p className="truncate text-[10px] text-muted-foreground">
                                {item.subtitle}
                              </p>
                            )}
                          </div>
                          {isActive && (
                            <ArrowRight className="size-3.5 text-muted-foreground/60" />
                          )}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))
          )}
        </div>
        <div className="flex items-center justify-between border-t border-border/40 px-3 py-1.5 text-[10px] text-muted-foreground">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1">
              <kbd className="rounded border border-border/60 bg-muted/40 px-1 font-mono">
                ↑↓
              </kbd>
              navigate
            </span>
            <span className="inline-flex items-center gap-1">
              <kbd className="rounded border border-border/60 bg-muted/40 px-1 font-mono">
                ↵
              </kbd>
              open
            </span>
          </div>
          <span>{filtered.length} result{filtered.length === 1 ? "" : "s"}</span>
        </div>
      </div>
    </div>
  );
}
