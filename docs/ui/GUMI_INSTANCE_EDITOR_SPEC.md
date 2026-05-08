# Gumi Instance Editor — UI Specification

**PR:** PR27E  
**Status:** Draft  
**Scope:** Subject-specific Gumi instance editor (Researcher Workbench)

---

## Objective

The Gumi Instance Editor is always subject-scoped. Every Gumi instance belongs to exactly
one subject and one Hermes profile. Researchers can inspect and edit Gumi identity, voice,
world model, embodiment, relationships, routines, expressive modes, first-contact config,
runtime files, and version history — all with mandatory versioning.

---

## Block Conditions

The following conditions MUST prevent rendering or saving the editor:

| Condition | Description |
|---|---|
| `BLOCKED_GLOBAL_GUMI_EDITOR` | Editor must never open without a bound `subject_id`. |
| `BLOCKED_GUMI_INSTANCE_WITHOUT_SUBJECT` | A Gumi instance record without `subject_id` must not be displayed or created. |
| `BLOCKED_GUMI_INSTANCE_WITHOUT_HERMES_PROFILE` | A Gumi instance record without `hermes_profile_id` must not be displayed or created. |
| `BLOCKED_UNVERSIONED_RUNTIME_EDIT` | Runtime files cannot be edited without creating a new version entry. |

---

## Required Page Header

Every Gumi Instance page MUST display all four fields:

```
Subject: <subject_id>
Gumi instance: <gumi_instance_id>
Hermes profile: <hermes_profile_id>
Condition: <condition_id>
```

These fields are read-only in the header. They cannot be changed via the editor.

---

## Required Sections

The editor is divided into the following sections, rendered as collapsible panels:

1. **Identity**
2. **Voice**
3. **World**
4. **Embodiment / Visual Canon**
5. **Relationships**
6. **Routines**
7. **Expressive Modes**
8. **First Contact**
9. **Runtime Files**
10. **Version History**

---

## Section Specifications

### 1. Identity

Displays core Gumi identity metadata. All fields are versioned.

| Field | Type | Notes |
|---|---|---|
| `gumi_instance_id` | string | Read-only. UUID. |
| `generation_mode` | enum | `manual` \| `assisted` \| `auto` |
| `sweet_spot_config` | object | Nested config object. |
| `voice_summary` | string | Free-text summary of Gumi's voice. |
| `relational_stance` | string | E.g., "warm companion", "gentle guide". |
| `active_boundaries` | array[string] | List of active behavioral constraints. |
| `current_version` | string | Semver string, e.g., `"1.3.0"`. |
| `soul_md_hash` | string | SHA-256 hash of SOUL.md at last approve. |

### 2. Voice

Narrative voice configuration. Editable via candidate workflow.

- Tone descriptors
- Vocabulary constraints
- Prohibited phrasing
- Sample utterances (per register)

### 3. World

World model for this Gumi instance. Each world item is a `world_object` record.

| Field | Type | Notes |
|---|---|---|
| `world_object_id` | string | UUID. |
| `type` | enum | `place` \| `person` \| `object` \| `routine` \| `concept` |
| `label` | string | Human-readable name. |
| `status` | enum | `active` \| `retired` \| `candidate` |
| `source` | enum | `researcher` \| `inference` \| `subject_reported` |
| `last_used` | string | ISO 8601 datetime. |
| `appears_in_events` | array[string] | Event IDs where this object appears. |
| `risk_flags` | array[string] | E.g., `["sensitive_location"]`. |

World items covered:
- Where she lives
- What she does
- Daily routines
- Places
- Objects
- Friends
- Family / kinship figures
- Colleagues / acquaintances
- Music taste
- Food / media / hobbies
- Recurring weather / environment

### 4. Embodiment / Visual Canon

Visual identity constraints for image generation.

| Field | Type | Notes |
|---|---|---|
| `reference_image_set` | array[object] | List of approved reference images. |
| `active_visual_identity_constraints` | array[string] | Mandatory visual traits. |
| `allowed_visual_drift` | number | 0.0–1.0 drift tolerance score. |
| `blocked_motifs` | array[string] | Forbidden visual elements. |
| `last_generated_images` | array[string] | URLs or artifact IDs. |
| `user_response_summary` | string | Researcher note on user reactions. |
| `visual_consistency_score` | number | 0.0–1.0 aggregate consistency score. |

### 5. Relationships

Persons in the subject's social world as represented in Gumi's model.
Each relationship entry references a `world_object` of type `person`.

Fields: name, relationship_type, intimacy_level, last_referenced, risk_flags.

### 6. Routines

Scheduled behavioral patterns for this Gumi instance. References world objects of type
`routine`. Each routine entry links to Cron jobs.

### 7. Expressive Modes

Per-mode configuration and live stats.

**Modes:** `proactive_text`, `audio_presence`, `image_activity`, `music_lyria`,
`diegetic_life_fragments`, `discoveries`.

Each mode exposes:

| Field | Type | Notes |
|---|---|---|
| `mode` | enum | `disabled` \| `dry-run` \| `review-required` \| `auto-gated` \| `paused` |
| `max_per_day` | integer | Daily rate limit. |
| `max_per_week` | integer | Weekly rate limit. |
| `quiet_hours` | object | `{start: "HH:MM", end: "HH:MM"}` in subject's timezone. |
| `last_generated` | string | ISO 8601 datetime. |
| `last_delivered` | string | ISO 8601 datetime. |
| `reply_rate` | number | 0.0–1.0 fraction of deliveries replied to. |
| `dismissal_rate` | number | 0.0–1.0 fraction of deliveries dismissed. |
| `overreach_flags` | array[string] | Logged overreach events. |
| `risk_level` | enum | `low` \| `medium` \| `high` \| `critical` |

### 8. First Contact

Configuration for the initial contact event sequence. Locked after first delivery.

### 9. Runtime Files

Read-only view of runtime artifacts (SOUL.md, policy pack, embodiment pack, etc.).
Every edit to a runtime file creates a new version record. Silent edits are blocked.

Shows: file name, version, hash, last_modified, approved_by, status.

### 10. Version History

Chronological log of all approved versions for this Gumi instance.

| Field | Notes |
|---|---|
| `version` | Semver string. |
| `approved_at` | ISO 8601. |
| `approved_by` | Researcher ID. |
| `changeset_summary` | Human-readable diff summary. |
| `soul_md_hash` | Hash at approval time. |

---

## Required Controls

The following controls must be present in the editor UI:

| Control | Section | Description |
|---|---|---|
| Edit candidate | Any editable field | Open candidate edit dialog. |
| Regenerate candidate | Any editable field | Trigger AI regeneration of field. |
| Approve version | Version History | Promote candidate to approved version. |
| Rollback | Version History | Revert to a previous approved version. |
| Lock field | Any field | Prevent future edits to field. |
| Retire field | World / Relationships | Mark field value as retired. |
| Show usage | World items | Show events where item appears. |
| Add reference image | Embodiment | Upload new reference image. |
| Retire reference image | Embodiment | Remove image from active set. |
| Generate candidate image | Embodiment | Trigger image generation. |
| Approve visual canon update | Embodiment | Promote candidate images to canon. |
| Flag identity drift | Embodiment | Log an identity drift event. |
| Disable expressive mode | Expressive Modes | Set mode to `disabled`. |
| Enable dry-run | Expressive Modes | Set mode to `dry-run`. |
| Require review | Expressive Modes | Set mode to `review-required`. |
| Enable auto-gated delivery | Expressive Modes | Set mode to `auto-gated`. |
| Pause expressive mode | Expressive Modes | Set mode to `paused`. |
| Set rate limit | Expressive Modes | Edit `max_per_day` / `max_per_week`. |
| Open last event | Expressive Modes | Navigate to last event in timeline. |
| Open policy | Runtime Files | Open policy pack viewer. |

---

## Acceptance Criteria

- Gumi editor is always subject-scoped. It cannot be opened without a `subject_id`.
- Every Gumi instance maps to exactly one `subject_id` and one `hermes_profile_id`.
- Every edit is versioned. No field value change is saved without a version record.
- Runtime files cannot be silently edited. Every runtime file change creates a version entry.
- Expressive modes expose all five states: `disabled`, `dry-run`, `review-required`,
  `auto-gated`, `paused`.
