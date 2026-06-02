---
design_tokens:
  colors:
    primary: "#5292c0"
    background: "#090b0e"
    surface_low: "#101318"
    surface_medium: "#171c23"
    surface_high: "#1e2430"
    text_primary: "#ced1da"
    text_secondary: "#7a8494"
    text_muted: "#708498"
    border_low: "rgba(255,255,255,0.055)"
    border_medium: "rgba(255,255,255,0.10)"
    semantic:
      success: "#3e8c6a"
      warning: "#b89840"
      error: "#d05050"
      info: "#5292c0"
      gumi: "#c260bc"
  typography:
    sans: "IBM Plex Sans, system-ui, sans-serif"
    mono: "IBM Plex Mono, Menlo, monospace"
    base_size: "13.5px"
    weights:
      light: 300
      regular: 400
      medium: 500
      bold: 600
  spacing:
    unit: "4px"
    scale: [0, 4, 8, 12, 16, 24, 32, 48, 64]
  radii:
    none: "0px"
    small: "2px"
---

# Relic Researcher Workbench: Design Goal

The design goal for the Relic Researcher UI is **"Minimalist Precision"**. The interface must prioritize data clarity, research governance, and instrument-grade reliability over decorative elements.

## Core Principles

1. **Information Density with Clarity**: The workbench handles complex data. We use a high-contrast dark theme (with light mode support) and consistent spacing to ensure that even dense information remains readable.
2. **Instrument-Grade Aesthetics**: The UI should feel like a laboratory instrument, functional, precise, and professional. We avoid rounded corners (`--r0: 0px`) and unnecessary gradients.
3. **Semantic Hierarchy**: Color is used strictly for semantic meaning (status, risk, stream type). Navigation and structure use a neutral palette to avoid distracting from the data.
4. **Fluid Responsiveness**: The 12-column grid system must adapt seamlessly to mobile, ensuring that researchers can monitor studies on any device without losing context.

## Navigation Philosophy

- **Global Rail**: A persistent sidebar for high-level navigation.
- **Contextual Headers**: Every page must have a clear `<h1>` and breadcrumb-style "eyebrow" to provide immediate context.
- **Functional Filters**: Filtering should be immediate and visible, using a dedicated "Filter Bar" component.

## Accessibility (WCAG 2.1)

- **Contrast**: All text must meet at least a 4.5:1 contrast ratio against its background.
- **Interactivity**: All buttons and links must have a minimum target size of 24x24px (preferably 36px+) and clear focus-visible states.
- **Hierarchy**: Proper semantic HTML (h1-h6) must be used to ensure screen reader compatibility.
