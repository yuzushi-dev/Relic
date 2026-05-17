# Data Model

## Scope hierarchy

Every object in Relic belongs to exactly one subject scope. The hierarchy is:

```
Study
  └── Subject
        └── GumiInstance
              └── HermesProfile
```

A runtime object is identified by the triple `(subject_id, gumi_instance_id, hermes_profile_id)`. No runtime object may exist without all three. Objects belonging to one subject cannot be accessed by another subject's Gumi instance.

| Object type | Required scope | Description |
|---|---|---|
| Runtime objects | All three IDs | Artifacts, events, traces, memory candidates |
| Subject | `subject_id` | A participant within a study |
| Study | `study_id` | Top-level research container |

## Primary storage

`relic.db` is the canonical source of truth. It is a SQLite database at `~/.relic/relic.db` by default (configurable via `RELIC_DB_PATH`). Markdown vault exports are derived from it and can be regenerated. External memory provider indices (Hindsight, Holographic, etc.) are also derived — they are not authoritative.

### Core tables

```sql
subjects           (id, study_id, created_at)
gumi_instances     (id, subject_id, created_at)
hermes_profiles    (id, gumi_instance_id, profile_hash, created_at)

runtime_objects    (id, subject_id, gumi_instance_id, hermes_profile_id,
                    object_type, created_at)

events             (id, subject_id, gumi_instance_id, hermes_profile_id,
                    event_class, ontological_class, timestamp)

continuity_markers (id, subject_id, gumi_instance_id, hermes_profile_id,
                    confirmed, created_at)

sensitive_signals  (id, subject_id, gumi_instance_id, hermes_profile_id,
                    created_at)
```

Session keys are stored as SHA-256 hashes only. The raw key is never written to storage.

## Events

Every event has a base set of required fields:

| Field | Description |
|---|---|
| `event_id` | UUID |
| `subject_id`, `gumi_instance_id`, `hermes_profile_id` | Scope |
| `event_class` | What kind of event (observation, correction, governance decision, etc.) |
| `ontological_class` | What type of data this represents (see below) |
| `timestamp` | ISO 8601 |
| `source_refs` | References to source data |
| `policy_snapshot_id` | Which policy was active when this event was recorded |

### Ontological classes

The ontological class is the most important field for data stream separation. It determines whether an event can be used as evidence about the subject.

| Class | Evidence-eligible | Description |
|---|---|---|
| `empirical_user_interaction` | Yes | Direct user input |
| `active_elicitation` | Yes | User responding to a structured question |
| `user_response_to_gumi` | Conditional | User responding to diegetic content |
| `gumi_diegetic_event` | No | Events in Gumi's fictional life |
| `expressive_media` | No | Creative outputs sent by Gumi |
| `system_inference` | No | System-generated inferences |
| `correction` | N/A | Correction to previous data |
| `governance_decision` | N/A | Policy or safety decision |
| `system_maintenance` | N/A | Internal system operation |

## Continuity markers

Continuity markers store subject-confirmed relational memory across sessions. They require explicit confirmation before permanent storage (`confirmed: true`). Unconfirmed markers cannot be stored in the registry.

When a marker is corrected, the original is preserved. The correction is authoritative but the original is part of the audit trail. Gumi can recall only subject-confirmed markers.

## Sensitive signals

Sensitive signals (safety signals from `relic/safety/`) are researcher-facing only. They are not included in subject exports, not visible to Gumi, and not stored in shared continuity memory. The field `clinical_interpretation_allowed` is always `false`.

## Export and deletion semantics

| Operation | Effect |
|---|---|
| Export | Produces a redacted bundle; safety signals excluded; audit event created |
| Delete | Removes data from storage; irreversible; audit event created |
| Forget | Removes from Gumi recall without deleting; audit event created; subject-scoped only |

All three operations require an audit event. Forget operates within subject scope — it cannot affect data belonging to another subject.

## PostgreSQL migration

The current implementation uses SQLite as the MVP storage backend. The migration target is PostgreSQL for production deployments with concurrent access. The migration steps and rollback procedures are defined in `relic-blueprint/blueprints/data-model/DATA_MODEL.md` (internal). The key constraint is that subject scope must be preserved at every step and the vector index must never be treated as the source of truth.
