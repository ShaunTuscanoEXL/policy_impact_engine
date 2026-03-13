# UI Redesign — Vercel/Linear-Inspired

**Date:** 2026-03-13
**Approach:** B (Framer Motion + CSS redesign)
**Default theme:** Light mode with dark mode toggle

---

## Theme & Color System

### Light Mode (default)
- Background: `#fafafa`
- Cards: `#ffffff`, 1px `rgba(0,0,0,0.06)` border, subtle box-shadow
- Text primary: `#0a0a0a`, secondary: `#737373`
- Accent: `#0070f3` (Vercel blue)
- Destructive: `#ef4444`

### Dark Mode
- Background: `#0a0a0a`
- Cards: `#171717`, 1px `rgba(255,255,255,0.08)` border
- Glassmorphism: `backdrop-filter: blur(12px)`, `rgba(255,255,255,0.03)` bg
- Text primary: `#ededed`, secondary: `#a1a1a1`

### Shared
- Font: Geist (unchanged)
- Border radius: 8px (reduced from 10px)

---

## Sidebar — Collapsed Icon Rail

- 64px collapsed, 220px expanded on hover
- Fixed left, full viewport height
- Top: app logo, Bottom: theme toggle + settings
- Middle: nav icons (Home, FileText, Database, Play, BarChart3, GitCompare)
- Active item: left 2px accent border + subtle bg highlight
- Framer Motion: `animate({ width })` spring, labels fade in with x offset
- Tooltip on hover when collapsed
- Page content: 64px left margin, expand overlays (no layout shift)

---

## Dashboard — Bento Grid

### Layout (4-column grid)
```
Row 1: 4x stat cards (BRDs, Datasets, Simulations, Scenarios) — 1x1 each
Row 2: Recent Simulations table (2x1) + Impact Chart area chart (2x1)
Row 3: Quick Actions full-width row (Upload BRD, New Simulation)
```

### Card Behavior
- Stat cards: large number, label below, icon top-right (low opacity), gradient border on hover
- Framer Motion: `whileHover={{ y: -2, scale: 1.01 }}`
- Chart: area chart with gradient fill, transparent bg, themed colors
- Table: compact rows, status dots (not badges), hover highlight
- Quick actions: ghost buttons with arrow icons, hover glow

### Page Transitions
- `AnimatePresence` wrapping route content
- Fade + slight upward slide on enter

---

## Page-Level Design Patterns

### All Pages
- Breadcrumb nav at top (small, muted)
- Title: `text-2xl font-semibold tracking-tight`
- Description: `text-sm text-muted-foreground`
- Cards: subtle border, no heavy shadows, glassmorphism in dark mode
- Staggered entrance: 50ms delay between sibling cards

### Tables
- Header: `text-xs uppercase tracking-wider text-muted-foreground`
- Row hover: left 2px accent border slides in
- Status: 8px colored dots instead of full badges
- Actions: icon-only, appear on row hover

### Forms & Dialogs
- Inputs: h-10, subtle border, accent glow on focus
- Dialogs: centered, backdrop blur, slide-up + fade
- Buttons: primary = solid accent, secondary = ghost with border

### Charts
- Monochrome palette: shades of blue/gray
- Grid lines: `rgba(0,0,0,0.04)`
- Tooltips: dark bg, rounded corners

---

## Dependencies

- `framer-motion` (~30KB) — page transitions, hover animations, sidebar expand/collapse
- All existing deps unchanged
