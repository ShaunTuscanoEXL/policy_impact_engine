# UI Redesign — Vercel/Linear-Inspired Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the Policy Impact Engine frontend from a basic functional UI to a polished Vercel/Linear-inspired design with icon rail sidebar, bento grid dashboard, glassmorphism cards, and Framer Motion animations.

**Architecture:** CSS-first redesign updating globals.css theme variables + replacing the sidebar component with a collapsible icon rail + refactoring each page for new design patterns. Framer Motion adds page transitions, hover effects, and sidebar animation.

**Tech Stack:** Next.js 16, Tailwind CSS v4, shadcn/base-nova, Framer Motion, Recharts, Lucide React, next-themes

---

### Task 1: Install Dependencies & Update Theme

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/app/globals.css`

**Step 1: Install framer-motion and next-themes**

Run:
```bash
cd frontend && npm install framer-motion
```

next-themes is already installed per package.json.

**Step 2: Update globals.css with new color system**

Replace the `:root` and `.dark` blocks in `frontend/src/app/globals.css` with the Vercel/Linear-inspired palette:

```css
:root {
  --background: #fafafa;
  --foreground: #0a0a0a;
  --card: #ffffff;
  --card-foreground: #0a0a0a;
  --popover: #ffffff;
  --popover-foreground: #0a0a0a;
  --primary: #0070f3;
  --primary-foreground: #ffffff;
  --secondary: #f5f5f5;
  --secondary-foreground: #171717;
  --muted: #f5f5f5;
  --muted-foreground: #737373;
  --accent: #f5f5f5;
  --accent-foreground: #171717;
  --destructive: #ef4444;
  --border: rgba(0, 0, 0, 0.06);
  --input: rgba(0, 0, 0, 0.06);
  --ring: #0070f3;
  --chart-1: #0070f3;
  --chart-2: #3b82f6;
  --chart-3: #60a5fa;
  --chart-4: #93c5fd;
  --chart-5: #bfdbfe;
  --radius: 0.5rem;
  --sidebar: #fafafa;
  --sidebar-foreground: #0a0a0a;
  --sidebar-primary: #0070f3;
  --sidebar-primary-foreground: #ffffff;
  --sidebar-accent: #f5f5f5;
  --sidebar-accent-foreground: #171717;
  --sidebar-border: rgba(0, 0, 0, 0.06);
  --sidebar-ring: #0070f3;
}

.dark {
  --background: #0a0a0a;
  --foreground: #ededed;
  --card: #171717;
  --card-foreground: #ededed;
  --popover: #171717;
  --popover-foreground: #ededed;
  --primary: #0070f3;
  --primary-foreground: #ffffff;
  --secondary: #1a1a1a;
  --secondary-foreground: #ededed;
  --muted: #1a1a1a;
  --muted-foreground: #a1a1a1;
  --accent: #1a1a1a;
  --accent-foreground: #ededed;
  --destructive: #dc2626;
  --border: rgba(255, 255, 255, 0.08);
  --input: rgba(255, 255, 255, 0.1);
  --ring: #0070f3;
  --chart-1: #3b82f6;
  --chart-2: #60a5fa;
  --chart-3: #93c5fd;
  --chart-4: #bfdbfe;
  --chart-5: #dbeafe;
  --radius: 0.5rem;
  --sidebar: #0a0a0a;
  --sidebar-foreground: #ededed;
  --sidebar-primary: #0070f3;
  --sidebar-primary-foreground: #ffffff;
  --sidebar-accent: #1a1a1a;
  --sidebar-accent-foreground: #ededed;
  --sidebar-border: rgba(255, 255, 255, 0.08);
  --sidebar-ring: #0070f3;
}
```

Also add these utility classes after the `@layer base` block:

```css
@layer utilities {
  .glass {
    background: rgba(255, 255, 255, 0.03);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
  }
}
```

**Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/app/globals.css
git commit -m "style: update theme to Vercel/Linear-inspired palette and install framer-motion"
```

---

### Task 2: Replace Sidebar with Animated Icon Rail

**Files:**
- Rewrite: `frontend/src/components/sidebar.tsx`
- Modify: `frontend/src/app/layout.tsx`

**Step 1: Rewrite sidebar as icon rail**

Replace `frontend/src/components/sidebar.tsx` with a new component that:
- Is 64px wide collapsed, 220px expanded on hover
- Uses `framer-motion`'s `motion.aside` with `animate={{ width }}` and a spring transition
- Shows only icons when collapsed, icons + labels when expanded (labels fade in with `motion.span` opacity/x animation)
- Has tooltip-like behavior: on collapsed hover, show label as a floating tooltip next to the icon
- Active item has a left 2px `#0070f3` border + subtle background highlight
- Top section: app logo icon (Zap from lucide-react) + "PIE" text (visible only when expanded)
- Bottom section: theme toggle button (Sun/Moon icons using next-themes `useTheme`), version text when expanded
- Navigation items: Home (LayoutDashboard), BRDs (FileText), Datasets (Database), Simulations (PlayCircle), Scenarios (GitCompare)

Key implementation details:
```tsx
"use client";
import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { useTheme } from "next-themes";
import {
  LayoutDashboard, FileText, Database, PlayCircle, GitCompare,
  Zap, Sun, Moon,
} from "lucide-react";
import { cn } from "@/lib/utils";

// Collapsed: w-16 (64px), Expanded: w-[220px]
// onMouseEnter/Leave toggles expanded state
// motion.aside animate={{ width: expanded ? 220 : 64 }}
// Each nav item: icon always visible, label wrapped in AnimatePresence
// Active detection: same logic as current sidebar
// Theme toggle at bottom: onClick toggles theme via setTheme
```

**Step 2: Update layout.tsx**

- Wrap the app in `ThemeProvider` from next-themes (with `attribute="class"`, `defaultTheme="light"`)
- Change `<main>` left margin from sidebar flex to `ml-16` (64px) to match collapsed rail width
- Remove `flex` layout from root div — sidebar is now fixed position

```tsx
import { ThemeProvider } from "next-themes";

// In the return:
<ThemeProvider attribute="class" defaultTheme="light">
  <div className="min-h-screen">
    <Sidebar />
    <main className="ml-16 min-h-screen overflow-y-auto p-8">
      {children}
    </main>
  </div>
  <Toaster />
</ThemeProvider>
```

**Step 3: Commit**

```bash
git add frontend/src/components/sidebar.tsx frontend/src/app/layout.tsx
git commit -m "style: replace sidebar with animated icon rail and add theme provider"
```

---

### Task 3: Add Page Transition Wrapper

**Files:**
- Create: `frontend/src/components/page-transition.tsx`
- Modify: `frontend/src/app/layout.tsx`

**Step 1: Create page transition component**

```tsx
"use client";
import { motion } from "framer-motion";

export function PageTransition({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}
```

**Step 2: Add staggered children wrapper**

Also export a `StaggerContainer` and `StaggerItem` for bento grid cards:

```tsx
export function StaggerContainer({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <motion.div
      className={className}
      initial="hidden"
      animate="visible"
      variants={{
        hidden: {},
        visible: { transition: { staggerChildren: 0.05 } },
      }}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <motion.div
      className={className}
      variants={{
        hidden: { opacity: 0, y: 12 },
        visible: { opacity: 1, y: 0 },
      }}
      transition={{ duration: 0.3 }}
    >
      {children}
    </motion.div>
  );
}
```

**Step 3: Create an interactive card wrapper**

```tsx
export function HoverCard({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <motion.div
      className={className}
      whileHover={{ y: -2, scale: 1.01 }}
      transition={{ type: "spring", stiffness: 300, damping: 20 }}
    >
      {children}
    </motion.div>
  );
}
```

**Step 4: Commit**

```bash
git add frontend/src/components/page-transition.tsx
git commit -m "feat: add framer-motion page transition and stagger animation wrappers"
```

---

### Task 4: Redesign Dashboard Page (Bento Grid)

**Files:**
- Rewrite: `frontend/src/app/page.tsx`
- Rewrite: `frontend/src/components/dashboard/stats-cards.tsx`
- Rewrite: `frontend/src/components/dashboard/recent-simulations.tsx`
- Create: `frontend/src/components/dashboard/impact-chart.tsx`
- Create: `frontend/src/components/dashboard/quick-actions.tsx`

**Step 1: Rewrite stats-cards.tsx**

Each stat card:
- White card with subtle border, icon in top-right at 10% opacity (large, 32px)
- Large number (text-3xl font-semibold), label below (text-sm text-muted-foreground)
- Wrapped in `HoverCard` for lift-on-hover effect
- Uses `StaggerItem` for staggered entrance
- Loading state: skeleton pulse animation

```tsx
// Structure per card:
<HoverCard>
  <Card className="relative overflow-hidden border border-border/50 shadow-sm">
    <CardContent className="p-6">
      <Icon className="absolute top-4 right-4 h-8 w-8 text-muted-foreground/10" />
      <p className="text-sm font-medium text-muted-foreground">{label}</p>
      <p className="mt-1 text-3xl font-semibold tracking-tight">{value}</p>
    </CardContent>
  </Card>
</HoverCard>
```

**Step 2: Create impact-chart.tsx**

- Area chart using Recharts showing simulation impact trend
- Gradient fill under the line (blue to transparent)
- Monochrome blue palette
- Transparent background, subtle grid lines
- Wrapped in Card with "Impact Trend" title

**Step 3: Rewrite recent-simulations.tsx**

- Compact table with status dots (8px colored circles) instead of badges
- Header row: `text-xs uppercase tracking-wider text-muted-foreground`
- Row hover: subtle left border accent animation
- Actions appear on hover (opacity transition)

**Step 4: Create quick-actions.tsx**

- Full-width row with 2-3 ghost-style action buttons
- "Upload BRD", "New Simulation", "Compare Scenarios"
- Each button: icon + text, subtle border, arrow icon on right
- Hover: subtle glow/border color change to accent

**Step 5: Rewrite dashboard page.tsx**

Bento grid layout:
```tsx
<PageTransition>
  <div className="space-y-6">
    {/* Header */}
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
      <p className="text-sm text-muted-foreground">Overview of policy simulations and impact analysis</p>
    </div>

    {/* Bento Grid */}
    <StaggerContainer className="grid grid-cols-4 gap-4">
      {/* Row 1: 4 stat cards */}
      <StaggerItem><StatCard ... /></StaggerItem>
      <StaggerItem><StatCard ... /></StaggerItem>
      <StaggerItem><StatCard ... /></StaggerItem>
      <StaggerItem><StatCard ... /></StaggerItem>

      {/* Row 2: Recent table (span 2) + Chart (span 2) */}
      <StaggerItem className="col-span-2"><RecentSimulations ... /></StaggerItem>
      <StaggerItem className="col-span-2"><ImpactChart ... /></StaggerItem>

      {/* Row 3: Quick Actions (span 4) */}
      <StaggerItem className="col-span-4"><QuickActions /></StaggerItem>
    </StaggerContainer>
  </div>
</PageTransition>
```

**Step 6: Commit**

```bash
git add frontend/src/app/page.tsx frontend/src/components/dashboard/
git commit -m "style: redesign dashboard with bento grid layout and animations"
```

---

### Task 5: Redesign List Pages (BRDs, Datasets, Simulations, Scenarios)

**Files:**
- Modify: `frontend/src/app/brds/page.tsx`
- Modify: `frontend/src/app/datasets/page.tsx`
- Modify: `frontend/src/app/simulations/page.tsx`
- Modify: `frontend/src/app/scenarios/page.tsx`

**Step 1: Apply common patterns to all 4 list pages**

For each page:
- Wrap in `<PageTransition>`
- Update header: `text-2xl font-semibold tracking-tight` (was text-3xl bold)
- Update description: `text-sm text-muted-foreground`
- Add breadcrumb: `<p className="text-xs text-muted-foreground mb-4">Dashboard / {PageName}</p>`
- Table header: `text-xs uppercase tracking-wider`
- Status indicators: replace Badge with 8px colored dots + text label
- Row actions: show on hover with opacity transition
- Cards: add `border-border/50 shadow-sm` classes
- Wrap table card in `<motion.div>` with fade-in animation
- Delete dialogs: add backdrop blur class

**Step 2: Update status dot pattern**

Create a shared StatusDot component or inline pattern:
```tsx
function StatusDot({ status }: { status: string }) {
  const colors: Record<string, string> = {
    COMPLETED: "bg-emerald-500",
    RUNNING: "bg-blue-500",
    PENDING: "bg-neutral-400",
    FAILED: "bg-red-500",
  };
  return (
    <span className="flex items-center gap-2">
      <span className={cn("h-2 w-2 rounded-full", colors[status] ?? "bg-neutral-400")} />
      <span className="text-sm">{status.charAt(0) + status.slice(1).toLowerCase()}</span>
    </span>
  );
}
```

**Step 3: Commit**

```bash
git add frontend/src/app/brds/page.tsx frontend/src/app/datasets/page.tsx frontend/src/app/simulations/page.tsx frontend/src/app/scenarios/page.tsx
git commit -m "style: redesign list pages with updated typography, status dots, and animations"
```

---

### Task 6: Redesign Detail Pages

**Files:**
- Modify: `frontend/src/app/brds/[id]/page.tsx`
- Modify: `frontend/src/app/datasets/[id]/page.tsx`
- Modify: `frontend/src/app/simulations/[id]/page.tsx`
- Modify: `frontend/src/app/simulations/new/page.tsx`
- Modify: `frontend/src/app/rules/[ruleSetId]/page.tsx`
- Modify: `frontend/src/app/scenarios/[id]/page.tsx`

**Step 1: Apply common patterns to all detail pages**

For each page:
- Wrap in `<PageTransition>`
- Add breadcrumb navigation
- Update header typography (text-2xl, tracking-tight)
- Cards: `border-border/50 shadow-sm`
- Stagger card animations where multiple cards exist
- Dialog animations: add backdrop blur
- Form inputs: ensure focus ring uses accent color

**Step 2: Update impact dashboard components**

For `frontend/src/components/impact/*.tsx`:
- Summary cards: wrap in HoverCard, use StaggerContainer
- Charts: monochrome blue palette, subtle grid lines, dark tooltips
- Segment table: update header typography
- Financial panel: update card styling

**Step 3: Update scenario comparison components**

For `frontend/src/components/scenarios/*.tsx`:
- Comparison charts: monochrome blue palette
- Delta table: cleaner borders, updated typography

**Step 4: Update rule editor components**

For `frontend/src/components/rules/*.tsx`:
- Conflict panel: softer warning styling
- Rule table: hover effects, typography updates
- Editor dialog: backdrop blur, smoother animations

**Step 5: Update BRD/dataset components**

For `frontend/src/components/brds/*.tsx` and `frontend/src/components/datasets/*.tsx`:
- Upload dropzone: accent color border on drag, smoother transitions
- Processing status: accent-colored steps
- Data profile charts: monochrome palette

**Step 6: Commit**

```bash
git add frontend/src/app/ frontend/src/components/
git commit -m "style: redesign detail pages and component library with new design system"
```

---

### Task 7: Final Polish & Dark Mode Verification

**Files:**
- Modify: `frontend/src/app/globals.css` (if needed)
- Modify: various components for dark mode fixes

**Step 1: Verify dark mode**

Test all pages in dark mode:
- Toggle theme via sidebar button
- Verify all cards have glassmorphism in dark mode (glass class where appropriate)
- Verify text contrast meets accessibility standards
- Fix any missing dark mode styles

**Step 2: Add dark mode glassmorphism to cards**

In `frontend/src/components/ui/card.tsx`, update the Card component to include dark mode glass effect:
```tsx
// Add to card className:
"dark:bg-card/80 dark:backdrop-blur-xl dark:border-border/50"
```

**Step 3: Build and verify**

Run:
```bash
cd frontend && npx next build
```

Ensure no TypeScript errors and all 12 routes compile.

**Step 4: Commit**

```bash
git add .
git commit -m "style: dark mode polish and glassmorphism effects"
```
