# PR27F — Timeline and Event Stream Viewer

## Objective

Per-subject chronological view of all recorded events. Supports stream filtering by event class and ontological class. Cross-subject raw event access is unavailable by default.

---

## Route

```
/workbench/subjects/:subject_id/timeline
```

---

## Required Streams

| Stream | Description |
|--------|-------------|
| `all_events` | Full chronological event log for the subject |
| `user_interactions` | Events initiated by or directly involving the user |
| `gumi_diegetic` | Events from Gumi's in-world diegetic life |
| `system_inferences` | System-generated inference and signal events |
| `corrections` | Correction events and their outcomes |
| `governance` | Governance decisions and policy applications |
| `media` | Expressive media events (images, audio, music) |

---

## Required Ontological Classes

Every event must carry exactly one of the following `ontological_class` values:

- `empirical_user_interaction`
- `active_elicitation`
- `proactive_support`
- `gumi_diegetic_event`
- `expressive_media`
- `user_response_to_gumi`
- `system_inference`
- `correction`
- `governance_decision`
- `system_maintenance`

---

## Required Filters

| Filter | Type |
|--------|------|
| `event_class` | enum |
| `ontological_class` | enum (multi-select) |
| `subject_id` | string (locked to current subject) |
| `gumi_instance_id` | string |
| `risk_level` | enum: none / low / medium / high |
| `delivery_status` | enum: delivered / blocked / no_reply / candidate |
| `eligible_for_user_model` | boolean |
| `eligible_for_experience_analysis` | boolean |
| `has_user_response` | boolean |
| `has_correction` | boolean |
| `has_boundary_risk` | boolean |
| `has_media` | boolean |
| `date_range` | date interval |

---

## Event Row Fields

Each row in the timeline table shows:

- `timestamp` — ISO 8601
- `event_type` — human-readable label
- `initiator` — user / gumi / system / researcher
- `delivery_decision` — delivered / blocked / no_reply / candidate
- `risk` — none / low / medium / high
- `user_response` — yes / no / pending
- `model_eligibility` — eligible / ineligible / pending
- `short_redacted_preview` — max 80 chars, redacted if raw unavailable

---

## Event Detail Panel Fields

Shown when a row is expanded or selected:

| Field | Notes |
|-------|-------|
| `event_id` | Unique event identifier |
| `subject_id` | Must match current subject scope |
| `gumi_instance_id` | Gumi instance that generated or received the event |
| `hermes_profile_id` | Delivery profile used |
| `class` | Event class (e.g., `checkin`, `proactive_support`) |
| `ontological_class` | One of the 10 required classes |
| `timestamp` | Full ISO 8601 with timezone |
| `delivered` | yes / no |
| `decision` | delivered / blocked / no_reply / candidate |
| `policy_snapshot` | Policy state at time of event |
| `source_refs` | List of source evidence IDs |
| `content_preview` | Redacted or available preview |
| `raw_content_availability` | local-only / redacted / unavailable |
| `eligible_for_user_model` | yes / no |
| `eligible_for_experience_analysis` | yes / no |
| `related_inference_ids` | List of inference IDs |
| `related_correction_ids` | List of correction IDs |

---

## Required Controls

- Filter panel (collapsible)
- Stream selector (tab or dropdown)
- Date range picker
- Export current view (researcher role only)
- Open event detail
- Link to related inference
- Link to related correction

---

## Acceptance Criteria

- Every event has `subject_id`.
- Every event has `ontological_class`.
- Timeline defaults to subject scope.
- Cross-subject raw event view is unavailable by default.
- Event detail shows model eligibility.
- Event detail shows policy snapshot and source refs.

---

## Block Conditions

| Code | Description |
|------|-------------|
| `BLOCKED_EVENT_WITHOUT_SUBJECT` | Event lacks `subject_id` — must not appear in timeline |
| `BLOCKED_EVENT_WITHOUT_ONTOLOGICAL_CLASS` | Event lacks `ontological_class` — must not appear |
| `BLOCKED_CROSS_SUBJECT_RAW_TIMELINE` | Cross-subject raw view is disabled by default |
| `BLOCKED_EVENT_ELIGIBILITY_MISSING` | Event detail cannot be shown if eligibility fields are absent |
