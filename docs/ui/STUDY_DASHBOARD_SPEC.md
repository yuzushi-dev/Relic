# Study Dashboard - UI Specification

**PR:** PR27B  
**Route:** `/researcher/study/:study_id`  
**Status:** Draft

---

## Overview

The Study Dashboard is the top-level researcher interface for a single study. It shows aggregate study health and a registry of all enrolled subjects. All cross-subject data is aggregate or redacted by default.

---

## Header panel

The header panel displays the following study-level fields:

| Field | Source | Notes |
|---|---|---|
| `study_id` | study record | Immutable identifier |
| `protocol_version` | study record | SemVer string |
| Number of **active** subjects | computed | Count of subjects with `status = active` |
| Number of **paused** subjects | computed | Count of subjects with `status = paused` |
| Number of **archived** subjects | computed | Count of subjects with `status = archived` |
| Subjects by condition | computed | Breakdown per condition label |
| Active risk alerts | computed | Count of subjects with `risk != none` |
| Pending reviews | computed | Count of subjects with `pending_review = true` |
| Failed cron jobs | computed | Count across all subjects |
| Hermes provisioning failures | computed | Count of subjects with `hermes_profile_id = null` |
| Exports pending | computed | Queue depth from export service |
| Last validation run | study record | ISO-8601 timestamp or `null` |

---

## Subject registry table

Each enrolled subject is rendered as exactly one row. Columns:

| Column | Schema field | Notes |
|---|---|---|
| Subject | `subject_id` | Stable, opaque identifier - never PII |
| Gumi Instance | `gumi_instance_id` | Link to instance detail |
| Hermes Profile | `hermes_profile_id` | Must be present; row is flagged if `null` (triggers `BLOCKED_MISSING_HERMES_PROFILE_ID`) |
| Condition | `condition` | Controlled vocabulary (e.g. `control`, `treatment_a`) |
| Status | `status` | One of `active`, `paused`, `archived` |
| Last User Interaction | `last_user_interaction_at` | ISO-8601 timestamp |
| Last Gumi Initiative | `last_gumi_initiative_at` | ISO-8601 timestamp |
| Risk | `risk` | One of `none`, `low`, `medium`, `high` |
| Pending Review | `pending_review` | Boolean - renders as badge |

---

## Required controls

### Subject management

- **Create subject** - opens create-subject modal; writes new subject record; does not modify any other subject.
- **Import subject** - bulk CSV import; validates headers before commit.

### Bulk validation controls

- **Validate all profiles** - triggers profile validation job across all subjects; read-only operation.
- **Check all Hermes profiles** - pings Hermes provisioning endpoint for each subject; read-only operation.

### Bulk delivery controls

- **Pause all proactive delivery** - sets `proactive_delivery_paused = true` on all active subjects.
- **Pause all expressive media** - sets `expressive_media_paused = true` on all active subjects.

### Export

- **Export redacted study summary** - generates a CSV/JSON export with PII stripped; cross-subject raw data is never exported.

### Filters

- **Filter by condition** - multi-select; shows only rows matching selected conditions.
- **Filter by risk** - multi-select; values: `none`, `low`, `medium`, `high`.
- **Filter by status** - toggles for `active`, `paused`, `archived`.

---

## Forbidden controls

The following operations are explicitly forbidden from the Study Dashboard. They must not appear as bulk actions and must not be reachable via any keyboard shortcut or API call from this route.

- Bulk rewrite of identity fields
- Bulk rewrite of world-state fields
- Bulk rewrite of persona fields
- Bulk rewrite of baseline fields

---

## Acceptance criteria

1. The dashboard shows **one row per subject** - no duplicate rows, no merged rows.
2. Every row includes `subject_id`, `gumi_instance_id`, and `hermes_profile_id`.
3. Cross-subject data is aggregate/redacted by default; raw individual records are never shown in the table header panel.
4. Bulk controls can **pause** or **validate** only - no bulk identity/world/persona/baseline edits.
5. Any row where `hermes_profile_id` is `null` must be visually flagged and counted under "Hermes provisioning failures".

---

## Block conditions

| Code | Triggered when |
|---|---|
| `BLOCKED_CROSS_SUBJECT_RAW_DATA` | Any UI element would expose unaggregated data from more than one subject simultaneously |
| `BLOCKED_BULK_IDENTITY_EDIT` | A bulk action attempts to write identity, world, persona, or baseline fields |
| `BLOCKED_MISSING_HERMES_PROFILE_ID` | A subject row has `hermes_profile_id = null` |

---

## Data flow

```
GET /api/study/:study_id/overview  →  study_overview.schema.json
GET /api/study/:study_id/subjects  →  subject_registry_row.schema.json[]
POST /api/study/:study_id/bulk/pause-delivery
POST /api/study/:study_id/bulk/pause-media
POST /api/study/:study_id/bulk/validate-profiles
POST /api/study/:study_id/bulk/check-hermes
POST /api/study/:study_id/export/redacted-summary
```

All POST endpoints return `{ ok: boolean, affected: number }`.
