---
name: Relic Scientific
colors:
  background: "#ffffff"
  surface: "#f8fafc"
  surface-2: "#f1f5f9"
  card: "#ffffff"
  card-border: "#e2e8f0"
  foreground: "#0f172a"
  foreground-2: "#475569"
  muted: "#f1f5f9"
  muted-fg: "#94a3b8"
  accent: "#0891b2"
  accent-dark: "#0e7490"
  accent-soft: "#06b6d4"
  accent-muted: "#ecfeff"
  accent-fg: "#164e63"
  success: "#16a34a"
  success-muted: "#f0fdf4"
  warn: "#d97706"
  warn-muted: "#fffbeb"
  danger: "#dc2626"
  danger-muted: "#fef2f2"
typography:
  h1:
    fontFamily: Geist
    fontSize: 22px
    fontWeight: 700
    lineHeight: 1.2
  h2:
    fontFamily: Geist
    fontSize: 15px
    fontWeight: 600
    lineHeight: 1.3
  body:
    fontFamily: Geist
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: Geist
    fontSize: 11px
    fontWeight: 500
    textTransform: uppercase
    letterSpacing: 0.08em
  mono:
    fontFamily: Geist Mono
    fontSize: 12px
rounded:
  default: 0px
  sm: 2px
  lg: 4px
spacing:
  card-padding: 24px
  grid-gap: 24px
  section-gap: 32px
  table-row-height: 44px
  sidebar-width: 224px
  nav-group-gap: 24px
---

## Overview

Relic Scientific is a light, open dashboard aesthetic for an HCI research monitoring tool.
The design draws from academic paper layouts and scientific instrument interfaces — not gaming UIs.
Every visual decision prioritizes legibility of data, clarity of structure, and a calm working environment.

## Colors

The palette is built on a white/slate foundation with a single cyan accent.

- **Background (#ffffff):** Pure white. Pages and cards sit on white; the surface layer (slate-50) is used only for the page body behind cards.
- **Surface (#f8fafc):** The outermost layer — page background, sidebar background, table header fills.
- **Card border (#e2e8f0):** A single, consistent border for all card and table edges. Never use shadow for elevation; use border instead.
- **Foreground (#0f172a):** Near-black slate for all primary text, titles, and data values.
- **Foreground-2 (#475569):** Secondary text — subtitles, table cell text, descriptions.
- **Muted-fg (#94a3b8):** Tertiary — labels, timestamps, empty states.
- **Accent (#0891b2, cyan-600):** The single interaction color. Used for active nav items, links, chart primary series, and focused states. Not for decorative purposes.
- **Accent-soft (#06b6d4):** Hover states and secondary chart series.
- **Accent-muted (#ecfeff):** Background tint for selected rows, active badges.

State colors (success, warn, danger) are used exclusively for status badges, alert borders, and KPI indicators. Never use them for decoration.

## Typography

Geist and Geist Mono are the only type families used.

- **Headings (h1):** 22px / 700. One per page. No decoration, no border.
- **Section titles (h2):** 15px / 600. Card titles and panel headers.
- **Body (13px / 400):** All prose, table content, descriptions.
- **Labels (11px / 500, uppercase):** Navigation group headers, KPI labels, column headers.
- **Mono (Geist Mono, 12px):** All numeric data values, timestamps, IDs, code snippets. Use consistently — never mix proportional and monospace within a data column.

## Layout

The layout is a fixed sidebar + scrollable main area.

- **Sidebar (224px):** White background, `border-right: 1px solid #e2e8f0`. No shadow. Navigation groups separated by 24px vertical space, each preceded by a label in uppercase 11px/500. Nav items have 8px vertical padding and no icon decorations beyond simple Unicode characters.
- **Main area:** Padded `32px` on all sides. Sections have a `page-title` (h1) with a subtitle below, then content blocks with 32px vertical gap.
- **Cards:** White, 1px solid `#e2e8f0` border, `border-radius: 0`, padding `24px`. No box-shadow.
- **Grid:** Two-column grids with `gap: 24px`. On narrow viewports, collapse to single column.

## Charts

Chart.js charts use the cyan palette as the primary series color (`#0891b2`), with `#94a3b8` for grid lines and axes. Background is always white. No fill gradients — lines only for time series, bars for distributions. Font: Geist 11px for axis labels.

## Badges and Status

Badges use `border-radius: 2px`, small padding (`2px 6px`), and the muted background of the corresponding state color with the full state color for the text. Never use colored backgrounds alone without a border.

| State   | Background      | Text      | Border                  |
|---------|-----------------|-----------|-------------------------|
| success | `#f0fdf4`       | `#16a34a` | `1px solid #bbf7d0`     |
| warn    | `#fffbeb`       | `#d97706` | `1px solid #fde68a`     |
| danger  | `#fef2f2`       | `#dc2626` | `1px solid #fecaca`     |
| accent  | `#ecfeff`       | `#0891b2` | `1px solid #a5f3fc`     |
| muted   | `#f1f5f9`       | `#475569` | `1px solid #e2e8f0`     |

## Responsiveness

The layout has three breakpoints. Token values that change at breakpoints override the desktop defaults above.

### Desktop (≥ 1024px) — default
- Sidebar fixed at `224px`, always visible, `position: fixed` left.
- Main content has `margin-left: 224px`, padding `32px`.
- Two-column card grids (`grid-template-columns: 1fr 1fr`).
- KPI grid: 4 columns (`repeat(4, 1fr)`).
- Page title `22px`.

### Tablet (640px – 1023px)
- Sidebar collapses to hidden by default, toggled via a hamburger button (top-left, `32px × 32px`).
- When open, sidebar overlays the content with a semi-transparent backdrop (`rgba(15,23,42,0.4)`); closes on backdrop tap.
- Main content has `margin-left: 0`, padding `24px`.
- Two-column grids collapse to single column.
- KPI grid: 2 columns (`repeat(2, 1fr)`).
- Page title `18px`.

### Mobile (< 640px)
- Sidebar same as tablet (overlay).
- Main content padding `16px`.
- KPI grid: 2 columns, tighter card padding `16px`.
- Tables: `overflow-x: auto` wrapper, min column width `80px` to allow horizontal scroll rather than wrapping.
- Page title `16px`.
- Nav group labels hidden; nav items show label only (no group heading).

### Responsive rules
- Never hide data on smaller screens — scroll instead of omit.
- Touch targets minimum `44px` tall on mobile (nav items, buttons).
- Charts maintain their aspect ratio; on mobile `height: 160px` instead of `180px`.
- The sidebar backdrop and hamburger button are only rendered in DOM on viewports < 1024px via CSS `display: none` at desktop.

## What to avoid

- No dark backgrounds anywhere in the UI.
- No glowing effects, animated borders, or neon accents.
- No more than one accent color active at a time on a page.
- No decorative Unicode symbols as icons — only functional ones (▲▼ for sort, ↺ for refresh).
- No font sizes below 11px.
