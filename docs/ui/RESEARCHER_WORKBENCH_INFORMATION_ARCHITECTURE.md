# Researcher Workbench - Information Architecture

## Overview

The Researcher Workbench is a multi-subject research management interface. All Gumi instances
are subject-scoped: there is no singleton global Gumi runtime. Editing any Gumi instance
requires an active subject scope. Global views of Gumi instances are aggregate/index only.

---

## Global Navigation (Study-Level)

These views exist at the top level, outside any subject scope.

| Section | Description |
|---|---|
| **Study Dashboard** | Aggregate overview of all subjects, risk alerts, and study-wide status. |
| **Subjects** | Registry of all subjects enrolled in the study. Entry point to subject-scoped views. |
| **Gumi Instances** | Index/aggregate view of all Gumi instances across subjects. Read-only at this level. |
| **Event Timeline** | Cross-subject event feed (redacted by default). Filterable by subject, event type, date. |
| **Inference Review** | Pending inference events requiring researcher review, across all subjects. |
| **Corrections** | Researcher-initiated correction records, cross-subject aggregate. |
| **Boundaries & Risk** | Study-wide boundary violations, risk alerts, and escalation queue. |
| **Cron Console** | Scheduled job status and failure log for all subjects and system crons. |
| **Artifacts** | Generated artifact index (all subjects, redacted metadata). |
| **Exports** | Export queue and export history for study data packages. |
| **Settings** | Study-level configuration: protocol version, IRB metadata, access control, integrations. |

### Constraint: Global Gumi Instances View

The **Gumi Instances** entry in global navigation is an index/aggregate view only.

- Displays: `gumi_instance_id`, linked `subject_id`, instance status, last active timestamp.
- Does NOT expose identity, voice, world, or relationship data at study level.
- Editing is disabled. Clicking a row navigates to the subject-scoped Gumi Instance view.

---

## Subject-Level Navigation

Activated when a subject is selected from the Subjects registry. All views below are scoped
to a single `subject_id`. The subject scope is always visible in the breadcrumb and page header.

| Section | Description |
|---|---|
| **Subject Overview** | Summary card: status, condition, linked Gumi instance, Hermes profile, risk level. |
| **Subject Baseline** | Baseline demographic and enrollment data for this subject. |
| **Gumi Instance** | Subject-scoped Gumi instance viewer and editor (nested navigation - see below). |
| **Timeline** | Event timeline for this subject only. Full fidelity, not redacted. |
| **Inference** | Inference events and pending reviews for this subject. |
| **Corrections** | Researcher correction log scoped to this subject. |
| **Boundaries** | Boundary definitions, violations, and risk assessments for this subject. |
| **Cron** | Scheduled jobs and cron history scoped to this subject. |
| **Artifacts** | Artifacts generated in context of this subject. |
| **Exports** | Export packages scoped to this subject. |
| **Audit Log** | Full audit trail of researcher and system actions for this subject. |

### Constraint: Subject Scope Requirement

- No subject-level route renders without a resolved `subject_id` in the URL path.
- Navigation to a subject-level view without a valid `subject_id` returns a 404 or redirect to the Subjects registry.
- There is no "current subject" global state shared across tabs or sessions.

---

## Gumi Instance Navigation (Subject-Scoped)

The Gumi Instance section is always nested under a subject. The breadcrumb pattern is:

```
Study Dashboard > Subjects > [subject_id] > Gumi Instance > [section]
```

Editing any field in this section requires an active, resolved subject scope.

| Section | Description |
|---|---|
| **Identity** | Name, persona archetype, identity anchors, and generation provenance. |
| **Voice** | Tone, register, lexical style, pacing, and expressive constraints. |
| **World** | World model: environment, lore, geography, cultural context. |
| **Body / Visual Canon** | Physical description and visual reference canon for the Gumi instance. |
| **Relationships** | Defined relationships between this Gumi instance and the subject or other entities. |
| **Routines** | Scheduled behavioral routines and proactive delivery patterns. |
| **Expressive Modes** | Mode definitions: narrative, reflective, playful, etc. |
| **First Contact** | First-contact script and onboarding event configuration. |
| **Versions** | Version history of Gumi instance configuration. Diff and rollback UI. |
| **Runtime Files** | Runtime profile pack and associated file artifacts. |

### Constraint: No Global Gumi Editing

- The global **Gumi Instances** index view has no edit controls.
- Creating or modifying a Gumi instance always requires navigating through a subject.
- Bulk edit of Gumi identity or world is not permitted from any view.

---

## Scope Hierarchy Summary

```
Study (global)
├── Study Dashboard
├── Subjects (registry)
│   └── [subject_id] (subject scope)
│       ├── Subject Overview
│       ├── Subject Baseline
│       ├── Gumi Instance (subject-scoped)
│       │   ├── Identity
│       │   ├── Voice
│       │   ├── World
│       │   ├── Body / Visual Canon
│       │   ├── Relationships
│       │   ├── Routines
│       │   ├── Expressive Modes
│       │   ├── First Contact
│       │   ├── Versions
│       │   └── Runtime Files
│       ├── Timeline
│       ├── Inference
│       ├── Corrections
│       ├── Boundaries
│       ├── Cron
│       ├── Artifacts
│       ├── Exports
│       └── Audit Log
├── Gumi Instances (aggregate index, read-only)
├── Event Timeline (cross-subject, redacted)
├── Inference Review (cross-subject)
├── Corrections (cross-subject)
├── Boundaries & Risk (cross-subject)
├── Cron Console (cross-subject)
├── Artifacts (cross-subject, redacted)
├── Exports
└── Settings
```

---

## Key Design Invariants

| Invariant | Rule |
|---|---|
| `BLOCKED_GLOBAL_GUMI_RUNTIME` | No route implies a singleton global Gumi runtime. |
| `BLOCKED_ROUTE_WITHOUT_SUBJECT_SCOPE` | No Gumi instance edit route resolves without a `subject_id` path segment. |
| `BLOCKED_MISSING_OBJECT_MODEL` | All views reference objects defined in `RESEARCHER_WORKBENCH_OBJECT_MODEL.md`. |
