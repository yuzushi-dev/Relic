# PR33 Shared Continuity Data Contract

## Objective

Register PR33 Shared Continuity persistence contracts in the canonical data model.

## Continuity Markers

Continuity markers track longitudinal state across Gumi sessions. They require explicit subject confirmation before storage.

## Continuity Marker Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| marker_id | string | Yes | Unique marker identifier |
| subject_id | string | Yes | Subject scope identifier |
| gumi_instance_id | string | Yes | Gumi instance scope identifier |
| hermes_profile_id | string | Yes | Hermes profile scope identifier |
| marker_type | string | Yes | Type of continuity marker |
| content_hash | string | Yes | Hash of marker content |
| confirmed | boolean | Yes | Subject confirmation status |
| created_at | string | Yes | ISO 8601 timestamp |
| corrections | array | No | Array of correction records |

## Subject Confirmation

Markers MUST NOT be stored without explicit subject confirmation:

- `confirmed: true` — Subject has confirmed the marker
- `confirmed: false` — Marker is pending confirmation (must not be stored permanently)

## Corrections

When a correction is applied to a marker:

1. **Original marker is preserved** — Never deleted
2. **Correction is authoritative** — Takes precedence over original
3. **Correction record links to original** — Audit trail maintained

## Recall Rules

| Role | Can Recall | When |
|------|-----------|------|
| Subject | Own markers only | After confirmation |
| Researcher | All markers | Always |
| Gumi | Subject-confirmed only | During active session |

## Constraints

1. Markers require subject scope (subject_id, gumi_instance_id, hermes_profile_id)
2. clinical_interpretation_allowed is always false
3. Corrections are authoritative over original markers
4. Recall rules are defined per role

## Block Conditions

| Block ID | Condition |
|----------|-----------|
| BLOCKED_UNCONFIRMED_MARKER_IN_REGISTRY | Unconfirmed marker stored |
| BLOCKED_MARKER_WITHOUT_SUBJECT | Marker lacks subject scope |
| BLOCKED_MARKER_CLINICAL_INTERPRETATION | Marker allows clinical interpretation |
| BLOCKED_RECALL_RULES_UNDEFINED | Recall rules not defined |
