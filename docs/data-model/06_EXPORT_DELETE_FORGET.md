# Export, Delete, and Forget Semantics

## Objective

Define export, delete, and forget semantics for all subject-scoped data.

## Operations

### Export

Subject data export generates a manifest containing:

| Field | Description |
|-------|-------------|
| subject_id | Subject identifier |
| condition | Export condition (withdrawal, completion, transfer) |
| redaction_status | Whether redactions were applied |
| hermes_profile_hash | Hash of Hermes profile at export time |
| soul_md_hash | Hash of SOUL.md at export time |
| policy_snapshot | Policy snapshot identifier |
| event_counts | Event counts by ontological class |
| exported_at | ISO 8601 timestamp |

**Researcher-only safety signals (PR32) are excluded from subject exports by default.**

### Delete

Delete removes data from storage and creates an audit event:

- Audit event MUST be created on delete
- Subject scope MUST be preserved in audit event
- Delete is irreversible

### Forget

Forget removes data from Gumi recall WITHOUT deleting from storage:

- Data remains in storage for regulatory compliance
- Gumi can no longer recall the data
- Audit event MUST be created on forget
- **Forget is subject-scoped** — Cannot forget data belonging to another subject

## Export Redaction Rules

| Data Type | Included in Export |
|-----------|-------------------|
| Events | Yes |
| Continuity Markers | Yes (confirmed only) |
| Safety Signals | No (researcher-only) |
| Runtime Objects | Yes |
| SOUL.md | Yes (hash only) |
| Hermes Profile | Yes (hash only) |

## Audit Events

| Operation | Audit Event Required |
|-----------|---------------------|
| Export | Yes |
| Delete | Yes |
| Forget | Yes |

## Block Conditions

| Block ID | Condition |
|----------|-----------|
| BLOCKED_EXPORT_WITH_RESEARCHER_SIGNALS | Export includes researcher-only signals |
| BLOCKED_FORGET_WITHOUT_AUDIT_EVENT | Forget without audit trail |
| BLOCKED_DELETE_WITHOUT_AUDIT_EVENT | Delete without audit trail |
| BLOCKED_FORGET_NOT_SUBJECT_SCOPED | Forget operates across subject boundaries |
| BLOCKED_EXPORT_WITHOUT_REDACTION_STATUS | Export manifest missing redaction status |
