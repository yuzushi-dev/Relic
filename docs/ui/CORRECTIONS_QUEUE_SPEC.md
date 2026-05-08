# Corrections Queue and Propagation Viewer Specification

## Status

Normative specification for PR27H.

## Purpose

Implement the corrections queue and propagation view for the Researcher Workbench.

## Required Fields

| Field | Description |
|---|---|
| correction_id | Unique correction identifier |
| subject_id | Owning subject (required) |
| target_field | Dot-path to corrected field |
| previous_value | Value before correction |
| corrected_value | Value after correction |
| rationale | Researcher rationale |
| created_at | Correction timestamp |
| researcher_id | Researcher who made correction |
| propagation_status | pending/propagating/complete/failed |

## Propagation View

The propagation view must show the full chain:

```
correction
  → affected observations
    → affected signals
      → affected hypotheses
        → affected runtime hints
          → affected artifacts
            → affected Gumi behaviors
```

## Block Conditions

| Condition | Trigger |
|---|---|
| BLOCKED_CORRECTION_WITHOUT_SUBJECT | Correction without subject scope |
| BLOCKED_CORRECTION_WITHOUT_PROPAGATION_STATUS | Missing propagation status |
| BLOCKED_REJECT_WITHOUT_REASON | Rejection without written reason |
| BLOCKED_CORRECTION_PROPAGATION_UNINSPECTABLE | Propagation chain not viewable |

## Required Actions

- view correction detail
- reject correction (requires reason)
- quarantine affected artifact
- trigger profile recompile
- view propagation graph

## Acceptance Criteria

- [ ] Every correction is subject-scoped
- [ ] Every correction has propagation_status
- [ ] Rejecting requires written reason
- [ ] Affected artifacts can be quarantined
- [ ] Corrections can trigger profile recompile
- [ ] Propagation view shows full chain
