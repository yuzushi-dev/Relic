# Safety Signals Panel Specification

## Overview

The Safety Signals Panel is a component of the Researcher Workbench that displays sensitive pattern signals to authorized researchers. It shows evidence, confidence, and allowed adaptations WITHOUT exposing signal labels to Gumi or subject.

## Panel Name

**NOT labeled "Diagnostics"** or any clinical term.

The panel should be named something like:
- "Safety Signals"
- "Context Signals"
- "Adaptive Context"

## Data Displayed

### Required Fields

| Field | Visible to Researcher | Visible to Subject | Visible to Gumi |
|-------|---------------------|-------------------|-----------------|
| evidence_refs | Yes | No | No |
| baseline_comparison | Yes | No | No |
| confidence | Yes | No | No |
| allowed_adaptations | Yes | No | No (only constraints) |
| forbidden_disclosures | Yes | No | No |
| signal_status | Yes | No | No |

### Signal Label Visibility

- **NEVER visible to subject**: Signal labels never appear in subject-facing output
- **NEVER visible to Gumi**: Signal labels never appear in Gumi runtime
- **ONLY visible to researcher**: Full signal information for review

## Researcher Actions

### Allowed Actions

1. **Approve**: Researcher can approve a pending signal
2. **Reject**: Researcher can reject a signal
3. **Expire**: Researcher can expire a signal

### Forbidden Actions

1. **Send to Gumi**: Researcher cannot send signal label to Gumi
2. **Send to Subject**: Researcher cannot send signal label to subject
3. **Override Visibility**: Cannot make labels visible to subject or Gumi

## Panel Structure

```
Safety Signals Panel
├── Signal List
│   ├── Signal (status: pending/approved/rejected/expired)
│   │   ├── Evidence References
│   │   ├── Baseline Comparison
│   │   ├── Confidence Score
│   │   ├── Allowed Adaptations
│   │   └── Researcher Actions [Approve] [Reject] [Expire]
│   └── ...
└── Filters
    ├── Status Filter
    ├── Confidence Range
    └── Date Range
```

## Block Conditions

The following block conditions apply:
- BLOCKED_DIAGNOSTICS_LABEL_IN_PANEL: Panel not labeled "Diagnostics"
- BLOCKED_SIGNAL_LABEL_TO_GUMI: Label never sent to Gumi
- BLOCKED_SIGNAL_LABEL_TO_SUBJECT: Label never sent to subject
- BLOCKED_PATHOLOGY_DETECTION_SCOPE: No pathology detection
- BLOCKED_SIGNAL_WITHOUT_SUBJECT_SCOPE: All signals subject-scoped
- BLOCKED_SUBJECT_VISIBLE_SIGNAL: Signals not subject-visible

## Acceptance Criteria

1. Panel is NOT labeled "Diagnostics" or clinical terms
2. Panel shows: evidence_refs, baseline_comparison, confidence, allowed_adaptations, forbidden_disclosures
3. Researcher can approve, reject, or expire signals
4. Researcher CANNOT send signal label to Gumi
5. Researcher CANNOT send signal label to subject
6. Signal label NEVER appears in Gumi runtime or subject output

## Implementation Notes

- Panel is read-only for signal data
- Actions only affect signal status (approve/reject/expire)
- No data flows from panel to Gumi or subject
- All sensitive data stays within researcher's view
