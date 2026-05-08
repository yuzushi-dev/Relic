# Researcher Workbench — Shared Continuity Panel Specification

## Status

Normative specification for PR33H.

## Purpose

Display Shared Continuity Memory data in the Researcher Workbench. Shows subject words, Gumi agreed words, corrections, and follow-up status. Never shows clinical terms. Always subject-scoped.

## Panel Layout

```
+------------------------------------------+
|  Shared Continuity Memory                |
+------------------------------------------+
|  Subject: subj_001    Gumi: gumi_001    |
+------------------------------------------+
|  [Marker List - subject-scoped]         |
|                                          |
|  +------------------------------------+  |
|  | Subject Words    | Gumi Words      |  |
|  | "too fast"       | "moving fast"   |  |
|  +------------------------------------+  |
|  | Status: active   | Followup: due   |  |
|  +------------------------------------+  |
|                                          |
|  [Corrections Section]                   |
|  +------------------------------------+  |
|  | CORRECTED: "too fast" → "just right"| |
|  +------------------------------------+  |
+------------------------------------------+
```

## Data Display Rules

### Subject Words (required)
- Display subject's own words verbatim
- Label as "Subject Words"
- Never alter or normalize

### Gumi Agreed Words (optional)
- Display only if Gumi has confirmed
- Label as "Gumi Words" or "Agreed"
- Empty state: "Pending Gumi confirmation"

### Corrections (when present)
- Label clearly as "CORRECTED"
- Show original → new wording
- Use subject's corrected words only

### Follow-up Status (per marker)
- Show current status: pending, due, sent, acknowledged, ignored, exhausted
- Show attempt count / max attempts
- Never show clinical interpretation

## Forbidden Displays

```
NEVER SHOW:
- Clinical labels (bipolar, depression, mania, etc.)
- System inferences about mood or diagnosis
- Raw diagnostic interpretations
- Pathology markers
- Symptom tracking data
```

## Subject Scoping

- Panel data must be filtered by current subject_id
- Gumi instance and Hermes profile scope must match
- No cross-subject data leakage

## Component States

### Empty State
"No continuity markers for this subject yet."

### Loading State
"Loading shared continuity data..."

### Error State
"Unable to load shared continuity panel."

## Acceptance Criteria

1. Panel shows subject words and Gumi agreed words separately
2. Corrections visible and labeled as such
3. Clinical terms NEVER shown in panel
4. Panel is subject-scoped
5. Follow-up status visible per marker
6. Panel does not show raw clinical interpretations