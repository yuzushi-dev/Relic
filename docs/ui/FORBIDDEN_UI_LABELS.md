# Forbidden UI Labels

This document enumerates UI labels that MUST NOT appear in the Researcher Workbench.

## Absolute Prohibitions

| Forbidden Label | Replace With |
|---|---|
| Diagnostics | Safety Signals |
| Pathology | Boundary Monitor |
| Symptoms | Event Stream |
| Mental Illness Detection | Context Signals |
| Clinical Risk | Risk Level |
| Bipolar Detector | - (do not implement) |
| Mood Disorder Monitor | - (do not implement) |
| Clinical Signals | Governance Signals |
| Symptom Tracking | Continuity Status |
| Diagnosis | Assessment |

## Rationale

The Researcher Workbench is a research governance tool, not a clinical diagnostic instrument.
All UI labels must reflect the non-diagnostic nature of the system.

## Enforcement

- UI components MUST reject any label containing clinical terminology at code review.
- Test `test_forbidden_labels_not_in_ui` validates this contract.
- Block condition `BLOCKED_FORBIDDEN_LABEL_IN_PANEL` is triggered if any forbidden label appears.

## Source Documents

- `docs/ui/01_INFORMATION_ARCHITECTURE.md` - Primary navigation structure
- `docs/ui/03_SAFETY_SIGNALS_PANEL.md` - Safety Signals panel specification
- `docs/ui/05_SHARED_CONTINUITY_PANEL.md` - Shared Continuity panel specification
