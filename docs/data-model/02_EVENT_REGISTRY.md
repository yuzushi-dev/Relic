# Event Registry

Registry of all chronicle event types emitted by Relic subsystems.

## PR30 — Hermes Transform Events

### `hermes_transform_llm_output`

Emitted when the Hermes plugin post-processes LLM output before delivery
(e.g. OutputCritic modifies or blocks the raw response).

**Category:** `governance_decision`
**Subject-scoped:** yes
**Retention:** `standard_365d`

### `hermes_no_agent`

Emitted when the no-agent cron evaluator runs and emits a RuntimeDecision
(NO_REPLY, CANDIDATE, DELIVER, or BLOCKED).

**Category:** `governance_decision`
**Subject-scoped:** yes
**Retention:** `standard_365d`

## PR32 — Safety Signal Events

### `sensitive_pattern_detected`

Emitted when the SafetyPatternExtractor identifies a sensitive topic pattern
in subject input (e.g. clinical risk signals, crisis indicators).

**Category:** `safety`
**Subject-scoped:** yes
**Retention:** `legal_hold`
**Note:** `clinical_interpretation_allowed` is always `false` — raw detections
are never exposed to the LLM layer without explicit researcher gate.

### `behavior_policy_patch_applied`

Emitted when a dynamic behavior policy patch is applied to the active Gumi
instance (e.g. risk-level escalation, topic suppression).

**Category:** `governance_decision`
**Subject-scoped:** yes
**Retention:** `standard_365d`

## PR33 — Continuity Events

### `continuity_marker_created`

Emitted when a new ContinuityMarker is persisted for a subject.
Captures the subject_words, gumi_agreed_words, and source_type.

**Category:** `continuity`
**Subject-scoped:** yes
**Retention:** `standard_365d`

### `continuity_marker_corrected`

Emitted when an existing ContinuityMarker is corrected by either the subject
or the researcher (e.g. wrong assumption flagged and updated).

**Category:** `continuity`
**Subject-scoped:** yes
**Retention:** `standard_365d`

## Schema Reference

All events conform to `schemas/data-model/base_event.schema.json`.
Required fields: `event_id`, `subject_id`, `gumi_instance_id`,
`hermes_profile_id`, `event_class`, `ontological_class`, `timestamp`,
`source_refs`, `policy_snapshot_id`.
