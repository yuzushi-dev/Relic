# Design System: Relic Researcher Workbench
**Project ID:** relic-researcher-ui-refactor

## 1. Visual Theme & Atmosphere
"Instrument-Grade Utilitarian Precision." The theme is a high-density, sharp-edged, flat dark interface modeled after high-fidelity laboratory equipment and telemetry dashboards. It prioritizes data clarity, research governance, and visual density over decorative illustrations. Corners are sharp, borders are thin, and color is used strictly for semantic communication.

## 2. Color Palette & Roles
*   **Primary Background** (`--background` / `#090b0e`): Slate Black. Deep dark canvas for high-contrast on illuminated displays.
*   **Sidebar & Low Surface** (`--card` / `#101318`): Deep Slate Gray. Used for the persistent sidebar and background panels.
*   **Elevated Surface** (`--popover` / `#171c23`): Slate Charcoal. Used for cards, dialog boxes, and dropdown select sheets.
*   **Border Low** (`--border` / `rgba(255,255,255,0.06)`): Translucent White. Thin dividers for structural alignment.
*   **Border High** (`--border-hover` / `rgba(255,255,255,0.20)`): Semi-translucent White. Used for focus and hover states.
*   **Active Accent / Info** (`--primary` / `#5292c0`): Clean Steel Blue. Used for active navigation links, highlights, and primary data markers.
*   **Primary Text** (`--foreground` / `#ced1da`): Light Slate Gray. Used for body copy, numbers, and primary readouts.
*   **Muted Text** (`--muted-foreground` / `#708498`): Slate Steel. Used for headers, descriptions, and passive metadata.
*   **Success Status** (`--success` / `#3e8c6a`): Forest Emerald Green. Used for active/validated statuses and consent indicators.
*   **Warning / Pending** (`--warning` / `#b89840`): Amber Gold. Used for paused status or items queued for review.
*   **Danger / Error** (`--destructive` / `#d05050`): Crimson Red. Used for risk alerts, failed cron jobs, or provisioning failures.
*   **Gumi Core Signature** (`--gumi` / `#c260bc`): Pale Orchid Purple. Used for Gumi-specific logs, profiles, and messages.

## 3. Typography Rules
*   **Headers & Body Text**: `IBM Plex Sans` (with system-ui, sans-serif fallbacks). Technical tone with high readability.
*   **Technical Data, Tables & Code**: `IBM Plex Mono` (with Menlo, monospace fallbacks). Applied to hashes, timestamps, statistics, CLI logs, and raw JSON payloads.
*   **Letter Spacing**: `-0.01em` on large titles to increase visual density; `0.05em` on uppercase badges to suggest clean alignment.
*   **Font Weights**: `300` (Light) for secondary descriptions, `400` (Regular) for body data, `500` (Medium) for active items, and `600` (Semi-Bold) for section titles and headers.

## 4. Component Stylings
*   **Buttons**: Sharp-edged (`border-radius: 0px` or `2px`), flat background with custom border. Primary buttons utilize a solid steel blue background; secondary buttons are border-only outlines. Focus rings utilize `--primary` with a 2px offset.
*   **Cards/Containers**: Flat, square containers (`border-radius: 0px` or `2px`). Background matches the low-elevation slate surfaces. Shadows are absent or flat (`box-shadow: none`) to maintain a clean digital instrumentation appearance.
*   **Inputs/Forms/Selects**: Subtle border strokes (`rgba(255,255,255,0.1)`) with a dark sunken background. Dropdowns utilize shadcn/ui select popups styled with `--popover`.
*   **Status Badges**: Styled as small rectangular pill shapes with matching text colors and translucent background fills (`color-mix` with 8% opacity).

## 5. Layout Principles
*   **Grid System**: 12-column responsive layout grid using native CSS grids. Cells span width via `.col-X` classes.
*   **Spacing**: High-density spacing based on multiples of `4px` (`4px`, `8px`, `12px`, `16px`, `24px`, `32px`).
*   **Dense Data Management**: Subject Overview and Baseline Profile screens utilize multi-column setups or horizontal tabs rather than single endless scrolling lists.
*   **Telemetry Stream**: Time-series log displays (Timeline and Chronicle Events) use a split-pane layout: a list of events on the left, and detail inspect panels on the right.
