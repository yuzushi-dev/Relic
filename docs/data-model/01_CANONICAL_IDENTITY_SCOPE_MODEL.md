# Canonical Identity and Scope Model

## Objective

Define the canonical identity and scope model used across PR24, PR25, PR30, PR32, and PR33.

## Hierarchy

```
Study
  └── Subject
        └── GumiInstance
              └── HermesProfile
```

Every runtime object MUST belong to exactly one subject scope, defined by the triple:

- `subject_id` — the human participant identifier
- `gumi_instance_id` — the specific Gumi runtime instance
- `hermes_profile_id` — the Hermes profile hash or identifier

## Object Model

| Object Type | Required Scope | Description |
|------------|----------------|-------------|
| Runtime objects | `subject_id`, `gumi_instance_id`, `hermes_profile_id` | All runtime objects require full subject scope |
| Study | `study_id` only | Top-level research container |
| Subject | `subject_id` | Participant within a study |

## Constraints

1. **Subject scope is required** — No runtime object may exist without a subject scope.
2. **Cross-subject shared memory is forbidden** — Data belonging to one subject may not be accessible to another.
3. **Hermes session key stored as hash** — Raw session keys are never stored; only their SHA-256 hash is retained.
4. **Exactly one subject scope per object** — A runtime object may not belong to multiple subjects.

## Block Conditions

| Block ID | Condition |
|----------|-----------|
| BLOCKED_RUNTIME_OBJECT_WITHOUT_SUBJECT | Runtime object lacks subject_id, gumi_instance_id, or hermes_profile_id |
| BLOCKED_CROSS_SUBJECT_MEMORY | Attempt to share data across subject boundaries |
| BLOCKED_RAW_SESSION_KEY | Raw session key stored instead of hash |
| BLOCKED_MULTIPLE_SUBJECT_SCOPES_PER_OBJECT | Runtime object belongs to more than one subject |

## References

- PR24: Subject registration and profile management
- PR25: GumiInstance provisioning
- PR30: Hermes event emission
- PR32: Sensitive pattern governance
- PR33: Shared continuity memory
