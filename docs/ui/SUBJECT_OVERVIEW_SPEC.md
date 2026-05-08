# Subject Overview — UI Specification

## PR27C

## Purpose

The Subject Overview page is the primary entry point for a researcher managing an individual
subject within an experiment. It provides a consolidated view of the subject's current state,
Gumi instance health, Hermes profile status, and exposes all subject-scoped controls.

---

## Route

```
/workbench/experiments/{experiment_id}/subjects/{subject_id}/overview
```

`subject_id` is a **required** path parameter. The page must be inaccessible without it.
A missing or invalid `subject_id` must redirect to the experiment subjects list with an error
notification. This satisfies block condition `BLOCKED_SUBJECT_SCOPE_MISSING`.

---

## Required Fields

The following fields must be displayed on the Subject Overview page:

| Field | Description |
|---|---|
| `subject_id` | Unique subject identifier (read-only label) |
| `experiment_id` | Parent experiment identifier (link to experiment overview) |
| `subject_status` | Current subject lifecycle status (e.g. active, archived, withdrawn) |
| `consent_status` | Consent state (e.g. consented, withdrawn, pending) |
| `active_condition` | Experimental condition the subject is assigned to |
| `bootstrap_status` | Bootstrap completion state (e.g. complete, in_progress, not_started) |
| `active_gumi_instance` | Name/id of the active Gumi instance for this subject (must be visible; absence blocks rendering — `BLOCKED_MISSING_GUMI_INSTANCE`) |
| `hermes_profile_status` | Provisioning status of the associated Hermes profile (must be visible) |
| `last_user_interaction` | ISO 8601 timestamp of the most recent user-initiated interaction |
| `last_gumi_initiative` | ISO 8601 timestamp of the most recent proactive Gumi initiative |
| `last_relic_extraction` | ISO 8601 timestamp of the most recent Relic memory extraction |
| `last_synthesis` | ISO 8601 timestamp of the most recent synthesis run |
| `last_correction` | ISO 8601 timestamp of the most recent researcher correction |
| `active_cron_modes` | List of currently active cron modes for this subject |
| `risk_summary` | Aggregated risk flag summary (severity level + count) |
| `pending_review_count` | Number of inference items pending researcher review |

---

## Pause State Model

Pause states are **subject-scoped**: pausing one subject must not affect any other subject.
This satisfies block condition `BLOCKED_PAUSE_NOT_SUBJECT_SCOPED`.

The following granular pause flags are supported:

| Flag | Scope |
|---|---|
| `pause_all` | Suspend all Gumi output and ingestion for this subject |
| `pause_proactive` | Suppress proactive Gumi initiatives |
| `pause_checkin` | Suppress scheduled check-in messages |
| `pause_followup` | Suppress follow-up prompts |
| `pause_images` | Suppress image generation and delivery |
| `pause_audio` | Suppress audio message delivery |
| `pause_music` | Suppress music generation and delivery |
| `pause_diegetic_life` | Suppress diegetic-life background events |
| `pause_relic_ingestion` | Suspend Relic memory extraction for this subject |

Each pause flag is independently toggleable. Enabling `pause_all` sets all flags to active.
Disabling `pause_all` does not automatically clear other flags (researcher must clear manually).

---

## Required Controls

The following actions must be available on the Subject Overview page:

| Control | Action |
|---|---|
| Edit subject baseline | Navigate to subject baseline editor |
| Open Gumi instance | Open the active Gumi instance workspace |
| Open timeline | Navigate to the subject interaction timeline |
| Open inference review | Navigate to the inference review queue for this subject |
| Open boundary monitor | Navigate to the boundary monitoring view |
| Pause subject | Toggle `pause_all` for this subject |
| Pause Gumi outputs | Toggle `pause_proactive` + `pause_checkin` + `pause_followup` |
| Pause active elicitation | Toggle `pause_followup` |
| Pause expressive media | Toggle `pause_images` + `pause_audio` + `pause_music` |
| Archive subject | Transition subject status to `archived` (requires confirmation dialog) |
| Export redacted subject bundle | Trigger redacted bundle export job |

All controls that mutate state must be disabled if the subject status is `archived` or
`withdrawn`, except "Export redacted subject bundle" which remains available.

---

## Block Conditions

| Code | Condition | Behavior |
|---|---|---|
| `BLOCKED_SUBJECT_SCOPE_MISSING` | `subject_id` absent from route | Redirect to experiment subjects list; show error toast |
| `BLOCKED_PAUSE_NOT_SUBJECT_SCOPED` | Pause action affects more than one subject | Action rejected; log error; show warning to researcher |
| `BLOCKED_MISSING_GUMI_INSTANCE` | `active_gumi_instance` is null or absent | Page renders with degraded state banner; Gumi controls disabled |

---

## Acceptance Criteria

- The Subject Overview page is inaccessible without a valid `subject_id` in the route.
- The active Gumi instance is visible on the page; absence triggers degraded state.
- The active Hermes profile status is visible.
- All pause controls operate exclusively on the current subject's pause flags.
- A pause action on subject A cannot affect pause flags on subject B.

---

## Data Contract

The page is backed by the `subject_overview` schema:

```
schemas/ui/subject_overview.schema.json
```

A reference fixture is available at:

```
fixtures/researcher-workbench/subject_overview_subj_001.json
```
