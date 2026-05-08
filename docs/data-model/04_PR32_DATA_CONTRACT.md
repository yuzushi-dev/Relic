# PR32 Sensitive Pattern Data Contract

## Objective

Register PR32 sensitive pattern object schemas and persistence rules in the canonical data model.

## Safety Signal Classification

Safety signals (sensitive patterns) are **researcher-facing only** and must not be visible to subjects or Gumi.

## Sensitive Signal Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| signal_id | string | Yes | Unique signal identifier |
| subject_id | string | Yes | Subject scope |
| gumi_instance_id | string | Yes | Gumi instance scope |
| hermes_profile_id | string | Yes | Hermes profile scope |
| signal_type | string | Yes | Type of sensitive pattern detected |
| detected_at | string | Yes | ISO 8601 timestamp |
| researcher_visible | boolean | Yes | Always true (researcher-only) |
| subject_visible | boolean | No | Always false |
| gumi_visible | boolean | No | Always false |
| clinical_interpretation_allowed | boolean | No | Always false |

## PR32 Boundary Enforcement

Safety signals (PR32) are **NOT memories** and must not be accessible to:

1. Gumi runtime recall
2. Subject-facing exports
3. Shared Continuity Memory (PR33)

## Behavior Policy Patches

When applying behavior policy patches:

1. **Labels are stripped** - Family names, personal identifiers removed
2. **Only policy delta stored** - Not the full patched content
3. **Audit trail preserved** - Patch applied event recorded

## Constraints

1. Safety signals require subject scope (subject_id, gumi_instance_id, hermes_profile_id)
2. clinical_interpretation_allowed is always false
3. Signals are not stored in Gumi recall
4. Signals are not included in subject exports

## Block Conditions

| Block ID | Condition |
|----------|-----------|
| BLOCKED_SENSITIVE_SIGNAL_SUBJECT_VISIBLE | Safety signal made subject-visible |
| BLOCKED_SENSITIVE_SIGNAL_GUMI_VISIBLE | Safety signal made Gumi-visible |
| BLOCKED_BEHAVIOR_POLICY_NOT_LABEL_STRIPPED | Patch applied without label stripping |
| BLOCKED_SENSITIVE_SIGNAL_WITHOUT_SUBJECT_SCOPE | Signal lacks required scope |
| BLOCKED_CLINICAL_INTERPRETATION_ALLOWED | clinical_interpretation_allowed is true |
