# Subject Baseline Page — UI Specification

**Task:** PR27D  
**Status:** Draft  
**Last updated:** 2026-05-05

---

## 1. Objective

The Subject Baseline Page gives researchers a single-screen view of a subject's complete baseline profile. Every field displays its **origin label** (how the value was obtained), its current value, and a full version history. Inline editing is allowed; every edit is versioned and may propagate corrections to dependent artifacts.

---

## 2. Route

```
/workbench/subjects/:subject_id/baseline
```

---

## 3. Page Header

| Element | Description |
|---------|-------------|
| Subject ID badge | `subj_<id>` in monospace |
| Bootstrap session link | Clickable link to the originating bootstrap session |
| Researcher ID | Shown as `@researcher_id` |
| Creation date | ISO 8601 date |
| Baseline method badge | One of: `structured_interview`, `self_report_survey`, `researcher_coded`, `system_inferred`, `hybrid` |
| Schema version | `v<major>.<minor>` |

---

## 4. Required Fields

The page MUST render all of the following fields. Fields are grouped into sections.

### 4.1 Metadata

| Field | Origin labels allowed |
|-------|----------------------|
| `bootstrap_session_id` | system-inferred |
| `researcher_id` | researcher-coded |
| `creation_date` | system-inferred |
| `baseline_method` | researcher-coded |

### 4.2 Self-Report Fields

Collected directly from the subject. Origin label: `subject-stated`.

| Field | Notes |
|-------|-------|
| Name / preferred name | Free text |
| Age range | Enum (e.g., `18-24`, `25-34`, …) |
| Gender identity | Free text with privacy tier |
| Language | BCP-47 code |
| Timezone | IANA tz string |
| Contact channel preference | e.g., `telegram`, `email` |
| Narrative self-description | Long text |

### 4.3 Researcher-Coded Fields

Assigned by researcher after interview. Origin label: `researcher-coded`.

| Field | Notes |
|-------|-------|
| Attachment style | Controlled vocabulary |
| Communication style | Controlled vocabulary |
| Affect regulation notes | Free text |
| Cultural context notes | Free text |

### 4.4 System-Inferred Fields

Derived from interaction logs or model inference. Origin label: `system-inferred`. These fields MUST be **visually distinct** from subject-stated fields (e.g., italic label, distinct background chip).

| Field | Notes |
|-------|-------|
| Estimated engagement level | Float 0–1 |
| Inferred relational style | Controlled vocabulary |
| Session affect summary | Short text |
| Response latency pattern | Short text |

### 4.5 Interaction Preferences

| Field | Origin labels allowed |
|-------|----------------------|
| Message length preference | subject-stated, researcher-coded |
| Emoji/visual preference | subject-stated |
| Response timing expectation | subject-stated |
| Preferred topics | subject-stated |
| Avoided topics | subject-stated |

### 4.6 Relational Expectations

| Field | Origin labels allowed |
|-------|----------------------|
| Desired relationship tone | subject-stated, researcher-coded |
| Continuity expectations | subject-stated |
| Disclosure comfort level | subject-stated |
| Role expectations for Gumi | subject-stated, researcher-coded |

### 4.7 Boundaries

| Field | Origin labels allowed |
|-------|----------------------|
| Hard limits | subject-stated |
| Soft limits | subject-stated, researcher-coded |
| Negotiable areas | subject-stated, researcher-coded |

### 4.8 Opt-Out Categories

List of strings. Origin label: `subject-stated`. Renders as removable chips.

### 4.9 Risk Flags

| Field | Origin labels allowed |
|-------|----------------------|
| Flag category | researcher-coded |
| Severity | researcher-coded |
| Notes | researcher-coded |
| Reviewed at | system-inferred |

### 4.10 Version History

Collapsible table showing all past edits. Each row includes:
- `version` number
- `edited_at` timestamp
- `edited_by` (researcher or system)
- `fields_changed` list
- `edit_mode` (`manual`, `correction_propagation`, `system_update`)
- `change_summary` free text

---

## 5. Origin Labels

Every baseline field MUST display exactly one of the following origin labels as a non-color visual tag (text badge):

| Label | Visual treatment |
|-------|-----------------|
| `subject-stated` | Solid badge, primary color |
| `researcher-coded` | Solid badge, secondary color |
| `system-inferred` | Italic badge, muted background — visually distinct |
| `generated-candidate` | Dashed border badge |
| `manually-edited` | Badge with pencil icon |
| `corrected` | Badge with checkmark, amber tint |
| `retired` | Strikethrough text, grey badge |

> **Block condition:** `BLOCKED_BASELINE_FIELD_WITHOUT_ORIGIN` — any field rendered without an origin label fails CI.

---

## 6. Required Controls

| Control | Behavior |
|---------|----------|
| **Edit button** (per field) | Opens inline editor; saving creates a new version entry |
| **Correction propagation toggle** | When active, saving a corrected field queues propagation to dependent artifacts |
| **Version history expander** | Reveals full version timeline for the field or the whole record |
| **Retire field button** | Marks field as `retired`; does not delete; creates version entry |
| **Export baseline JSON** | Downloads current snapshot as `subject_baseline_<subject_id>_v<n>.json` |
| **Flag review button** | Adds or removes a risk flag; always creates versioned entry |

---

## 7. Versioning Rules

- Every save operation MUST increment `baseline_version`.
- `baseline_version` starts at `1` on creation.
- A `version_history` entry MUST be appended for every change, including system-inferred updates.
- Edits performed via correction propagation MUST record `edit_mode: "correction_propagation"`.

> **Block condition:** `BLOCKED_UNVERSIONED_BASELINE_EDIT` — any edit that does not produce a version history entry fails CI.

---

## 8. Correction Propagation

When a researcher corrects a baseline field:

1. The system identifies all artifacts that reference that field.
2. A propagation job is queued with `status: pending`.
3. Dependent artifacts are updated or flagged for re-review.
4. The propagation trace is stored and linked from the baseline record.

> **Block condition:** `BLOCKED_CORRECTION_PROPAGATION_MISSING` — saving a correction without queueing propagation fails CI.

---

## 9. Accessibility & Display Rules

- Origin labels MUST use text, not color alone.
- `system-inferred` fields MUST be visually distinct (italic + muted chip).
- All timestamps display in the researcher's local timezone.
- Risk flags render with severity-aware text labels (not colored dots only).
- Version history is keyboard-navigable.

---

## 10. Error States

| Condition | UI behavior |
|-----------|-------------|
| Field missing origin label | Red inline error: "Origin required" |
| Edit save fails | Toast error; version NOT incremented |
| Propagation job fails | Warning banner with retry option |
| Schema version mismatch | Warning banner; page still loads with best-effort render |
