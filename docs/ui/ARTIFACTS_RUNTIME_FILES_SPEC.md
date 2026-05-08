# PR27K — Artifacts and Runtime Files Viewer Spec

## Overview

The artifact/runtime file inspection view lets a researcher inspect, compare, and manage all versioned artifacts associated with a subject. Every artifact is subject-scoped and immutable without an explicit versioned operation.

---

## Artifact Types

| Artifact | Description |
|---|---|
| `SOUL.md` | Narrative identity document for the Gumi instance |
| `USER.md` | Researcher-authored user model summary |
| `MEMORY.md` | Active memory document injected at runtime |
| `PORTRAIT.md` | Relational portrait synthesized from evidence |
| `subject_profile.json` | Structured subject baseline |
| `gumi_profile.json` | Gumi instance identity and persona configuration |
| `gumi_world_state.json` | Gumi's diegetic world snapshot |
| `runtime_profile_pack` | Combined runtime artifact bundle |
| `cron_manifest` | Scheduled delivery configuration |
| `policy_snapshot` | Governance policy at a point in time |
| `artifact_registry` | Index of all subject artifacts with hashes |

---

## Required Fields per Artifact

Every artifact record must expose:

| Field | Type | Description |
|---|---|---|
| `artifact_id` | string | Unique artifact identifier (`ART-` prefix) |
| `subject_id` | string | Owning subject (`SUBJ-` prefix) |
| `gumi_instance_id` | string | Associated Gumi instance (`GUMI-` prefix) |
| `artifact_type` | string | One of the artifact types listed above |
| `path` | string | Filesystem/storage path |
| `hash` | string | `sha256:` prefixed content hash |
| `schema_version` | string | Schema version string |
| `source_snapshot` | string | Snapshot identifier this artifact derives from |
| `status` | enum | `active`, `stale`, `quarantined`, `superseded` |
| `generated_at` | string (date-time) | ISO-8601 generation timestamp |
| `used_by_runtime` | boolean | Whether this artifact is injected at runtime |

---

## Controls

| Control | Description |
|---|---|
| Open redacted preview | View artifact content with private fields masked |
| Compare versions | Diff two artifact versions side by side |
| Mark stale | Flag artifact as outdated without deleting |
| Quarantine | Suspend artifact from runtime use pending review |
| Request recompile | Trigger pipeline to regenerate artifact from source |
| Export | Include artifact in a redacted export bundle |
| Rollback | Revert to a prior version (creates versioned entry) |

---

## Forbidden Actions

- **Direct unversioned edit**: The UI must not allow free-text edit of an artifact without creating a new versioned entry.
- **Silent write**: Any write operation must produce an audit log entry.
- **Cross-subject copy**: An artifact from subject A cannot be applied to subject B.

---

## Block Conditions

| Code | Trigger |
|---|---|
| `BLOCKED_ARTIFACT_WITHOUT_SUBJECT` | Artifact record missing `subject_id` |
| `BLOCKED_UNVERSIONED_ARTIFACT_EDIT` | Edit attempted without creating a new version |
| `BLOCKED_CROSS_SUBJECT_ARTIFACT_COPY` | Attempt to copy artifact across subject boundary |

---

## Acceptance Criteria

- Every artifact is subject-scoped: `subject_id` is required and non-null.
- Runtime files cannot be silently edited: all writes produce an audit entry.
- Artifact status is visible in the listing view.
- Artifact versions can be compared via the Compare versions control.
- Cross-subject artifact copy is blocked at the UI and API layer.

---

## Route

`/workbench/subjects/:subject_id/artifacts`

Sub-routes:
- `/workbench/subjects/:subject_id/artifacts/:artifact_id` — detail view
- `/workbench/subjects/:subject_id/artifacts/:artifact_id/compare` — version compare
