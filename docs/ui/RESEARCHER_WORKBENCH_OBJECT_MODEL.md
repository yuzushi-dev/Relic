# Researcher Workbench — Object Model

## Purpose

This document defines the canonical objects referenced by all Researcher Workbench views and routes.
Every UI view in the workbench must reference only objects defined here. The object model enforces
the subject-scoped information architecture described in `RESEARCHER_WORKBENCH_INFORMATION_ARCHITECTURE.md`.

---

## Core Objects

### Study

The top-level research context. A single deployment manages one study.

| Field | Type | Description |
|---|---|---|
| `study_id` | `string` | Unique study identifier. |
| `protocol_version` | `string` | IRB protocol version string (e.g., `v2.1`). |
| `title` | `string` | Human-readable study title. |
| `status` | `enum` | `active` \| `paused` \| `completed` \| `archived`. |
| `irb_reference` | `string` | IRB approval reference number. |
| `created_at` | `datetime` | Study creation timestamp. |
| `settings` | `StudySettings` | Study-level configuration object. |

### StudySettings

| Field | Type | Description |
|---|---|---|
| `allow_proactive_delivery` | `boolean` | Global toggle for Gumi-initiated contact. |
| `allow_expressive_media` | `boolean` | Global toggle for expressive media output. |
| `data_redaction_default` | `boolean` | Whether cross-subject views are redacted by default. |
| `export_requires_approval` | `boolean` | Whether exports require researcher sign-off. |

---

### Subject

A research participant enrolled in the study.

| Field | Type | Description |
|---|---|---|
| `subject_id` | `string` | Unique subject identifier (opaque, not PII). |
| `study_id` | `string` | Parent study reference. |
| `condition` | `string` | Experimental condition assignment. |
| `status` | `enum` | `active` \| `paused` \| `archived`. |
| `gumi_instance_id` | `string` | ID of the Gumi instance linked to this subject. One-to-one. |
| `hermes_profile_id` | `string` | ID of the Hermes delivery profile for this subject. |
| `enrolled_at` | `datetime` | Enrollment timestamp. |
| `last_user_interaction_at` | `datetime \| null` | Timestamp of most recent user-initiated interaction. |
| `last_gumi_initiative_at` | `datetime \| null` | Timestamp of most recent Gumi-initiated contact. |
| `risk_level` | `enum` | `none` \| `low` \| `medium` \| `high`. |
| `pending_review_count` | `integer` | Count of open inference review items. |

#### Constraint

Each subject has exactly one `gumi_instance_id`. A Gumi instance belongs to exactly one subject.
There is no many-to-one or shared Gumi relationship.

---

### SubjectBaseline

Baseline enrollment data for a subject. Stored separately from runtime state.

| Field | Type | Description |
|---|---|---|
| `subject_id` | `string` | Parent subject reference. |
| `age_range` | `string` | Age bracket (e.g., `25-34`). Not exact DOB. |
| `condition` | `string` | Condition assignment at enrollment. |
| `enrollment_notes` | `string \| null` | Researcher notes at enrollment (not shared with Gumi). |
| `baseline_survey_ref` | `string \| null` | Reference to external baseline survey record. |

---

### GumiInstance

A subject-scoped AI companion instance. Never exists without a parent subject.

| Field | Type | Description |
|---|---|---|
| `gumi_instance_id` | `string` | Unique instance identifier. |
| `subject_id` | `string` | Owning subject. Required. |
| `study_id` | `string` | Parent study. |
| `version` | `string` | Current active configuration version. |
| `status` | `enum` | `active` \| `paused` \| `draft` \| `archived`. |
| `identity` | `GumiIdentity` | Identity configuration block. |
| `voice` | `GumiVoice` | Voice and register configuration. |
| `world` | `GumiWorld` | World model block. |
| `body` | `GumiBodyCanon` | Physical and visual canon. |
| `relationships` | `GumiRelationship[]` | List of defined relationship records. |
| `routines` | `GumiRoutine[]` | Scheduled behavioral routines. |
| `expressive_modes` | `GumiExpressiveMode[]` | Expressive mode definitions. |
| `first_contact` | `GumiFirstContact` | First-contact configuration. |
| `runtime_files` | `RuntimeFilePack` | Associated runtime profile pack. |
| `created_at` | `datetime` | Instance creation timestamp. |
| `updated_at` | `datetime` | Last modification timestamp. |

#### Constraint

`GumiInstance` cannot be created, edited, or deleted outside a subject scope.
The global Gumi Instances index exposes only: `gumi_instance_id`, `subject_id`, `status`,
`updated_at`. All other fields are subject-scoped only.

---

### GumiIdentity

| Field | Type | Description |
|---|---|---|
| `name` | `string` | Gumi instance name as presented to subject. |
| `archetype` | `string` | Persona archetype label (e.g., `companion`, `mentor`). |
| `identity_anchors` | `string[]` | Core identity anchor phrases. |
| `generation_provenance` | `string \| null` | Reference to generation report that produced this identity. |

### GumiVoice

| Field | Type | Description |
|---|---|---|
| `tone` | `string` | Primary tone descriptor (e.g., `warm`, `dry`, `earnest`). |
| `register` | `enum` | `casual` \| `formal` \| `mixed`. |
| `lexical_style` | `string` | Lexical style notes. |
| `pacing` | `enum` | `slow` \| `moderate` \| `brisk`. |
| `expressive_constraints` | `string[]` | Prohibited expressive patterns or words. |

### GumiWorld

| Field | Type | Description |
|---|---|---|
| `environment` | `string` | World environment description. |
| `lore` | `string \| null` | Lore or backstory text. |
| `geography` | `string \| null` | Geographic or spatial context. |
| `cultural_context` | `string \| null` | Cultural framing notes. |

### GumiBodyCanon

| Field | Type | Description |
|---|---|---|
| `physical_description` | `string` | Textual physical description. |
| `visual_references` | `string[]` | Reference image IDs or URLs. |
| `canon_notes` | `string \| null` | Consistency notes for visual canon. |

### GumiRelationship

| Field | Type | Description |
|---|---|---|
| `relationship_id` | `string` | Unique relationship record ID. |
| `label` | `string` | Relationship label (e.g., `primary_user`, `mentor`). |
| `entity_type` | `enum` | `subject` \| `external_character` \| `system`. |
| `entity_ref` | `string` | Reference ID of the related entity. |
| `notes` | `string \| null` | Researcher notes on this relationship. |

### GumiRoutine

| Field | Type | Description |
|---|---|---|
| `routine_id` | `string` | Unique routine ID. |
| `label` | `string` | Human-readable routine name. |
| `cron_expression` | `string` | Cron schedule expression. |
| `action_type` | `string` | Type of proactive action triggered. |
| `enabled` | `boolean` | Whether routine is active. |

### GumiExpressiveMode

| Field | Type | Description |
|---|---|---|
| `mode_id` | `string` | Unique mode ID. |
| `name` | `string` | Mode name (e.g., `narrative`, `reflective`, `playful`). |
| `description` | `string` | Mode behavior description. |
| `trigger_conditions` | `string[]` | Conditions that activate this mode. |

### GumiFirstContact

| Field | Type | Description |
|---|---|---|
| `script_ref` | `string \| null` | Reference to first-contact script artifact. |
| `onboarding_event_id` | `string \| null` | ID of the linked onboarding event. |
| `completed_at` | `datetime \| null` | Timestamp of first contact completion. |

---

### HermesProfile

Delivery profile controlling how and when Gumi messages reach the subject.

| Field | Type | Description |
|---|---|---|
| `hermes_profile_id` | `string` | Unique profile ID. |
| `subject_id` | `string` | Owning subject. |
| `channel` | `string` | Delivery channel (e.g., `sms`, `email`, `push`). |
| `delivery_windows` | `DeliveryWindow[]` | Permitted delivery time windows. |
| `paused` | `boolean` | Whether all delivery is paused for this subject. |

### DeliveryWindow

| Field | Type | Description |
|---|---|---|
| `day_of_week` | `string[]` | Days active (e.g., `["Mon", "Tue"]`). |
| `start_time` | `string` | Window start in `HH:MM` (local time). |
| `end_time` | `string` | Window end in `HH:MM` (local time). |
| `timezone` | `string` | IANA timezone string. |

---

### Event

An immutable record of a system or interaction event for a subject.

| Field | Type | Description |
|---|---|---|
| `event_id` | `string` | Unique event ID. |
| `subject_id` | `string` | Owning subject. |
| `event_type` | `string` | Event type key (e.g., `user_message`, `gumi_initiative`, `inference`). |
| `timestamp` | `datetime` | Event timestamp. |
| `payload_ref` | `string \| null` | Reference to event payload artifact. |
| `redacted` | `boolean` | Whether payload is redacted in cross-subject views. |

---

### InferenceReviewItem

A pending researcher review for a model inference event.

| Field | Type | Description |
|---|---|---|
| `review_id` | `string` | Unique review item ID. |
| `subject_id` | `string` | Owning subject. |
| `event_id` | `string` | Triggering event reference. |
| `inference_type` | `string` | Type of inference (e.g., `risk_flag`, `state_update`). |
| `status` | `enum` | `pending` \| `approved` \| `corrected` \| `dismissed`. |
| `created_at` | `datetime` | When the review item was created. |
| `resolved_at` | `datetime \| null` | When the item was actioned. |
| `researcher_note` | `string \| null` | Researcher note on resolution. |

---

### CorrectionRecord

A researcher-initiated correction to system-inferred state.

| Field | Type | Description |
|---|---|---|
| `correction_id` | `string` | Unique correction ID. |
| `subject_id` | `string` | Owning subject. |
| `target_field` | `string` | Dot-path to the corrected field. |
| `previous_value` | `any` | Value before correction. |
| `corrected_value` | `any` | Value after correction. |
| `rationale` | `string` | Researcher rationale for the correction. |
| `created_at` | `datetime` | Correction timestamp. |
| `researcher_id` | `string` | ID of the researcher who made the correction. |

---

### BoundaryRecord

A boundary rule or violation record for a subject.

| Field | Type | Description |
|---|---|---|
| `boundary_id` | `string` | Unique boundary ID. |
| `subject_id` | `string` | Owning subject. |
| `boundary_type` | `string` | Boundary category (e.g., `topic_exclusion`, `contact_limit`). |
| `definition` | `string` | Human-readable boundary definition. |
| `violation_count` | `integer` | Number of violations recorded. |
| `last_violation_at` | `datetime \| null` | Timestamp of most recent violation. |
| `risk_level` | `enum` | `none` \| `low` \| `medium` \| `high`. |

---

### AuditLogEntry

An immutable audit entry for a researcher or system action.

| Field | Type | Description |
|---|---|---|
| `audit_id` | `string` | Unique audit entry ID. |
| `subject_id` | `string \| null` | Subject scope, if applicable. |
| `actor_type` | `enum` | `researcher` \| `system` \| `cron`. |
| `actor_id` | `string` | ID of the actor. |
| `action` | `string` | Action key (e.g., `gumi.identity.update`, `subject.pause`). |
| `timestamp` | `datetime` | Action timestamp. |
| `diff_ref` | `string \| null` | Reference to diff artifact, if applicable. |

---

### Artifact

A generated file or data artifact associated with a subject or the study.

| Field | Type | Description |
|---|---|---|
| `artifact_id` | `string` | Unique artifact ID. |
| `subject_id` | `string \| null` | Owning subject, if subject-scoped. |
| `artifact_type` | `string` | Type key (e.g., `export`, `runtime_profile`, `report`). |
| `label` | `string` | Human-readable artifact label. |
| `created_at` | `datetime` | Creation timestamp. |
| `file_ref` | `string` | Reference to file storage location. |
| `redacted` | `boolean` | Whether artifact is redacted in cross-subject views. |

---

### RuntimeFilePack

The assembled runtime profile files for a Gumi instance.

| Field | Type | Description |
|---|---|---|
| `pack_id` | `string` | Unique pack ID. |
| `gumi_instance_id` | `string` | Owning Gumi instance. |
| `subject_id` | `string` | Owning subject. |
| `profile_version` | `string` | Version tag for this pack. |
| `files` | `RuntimeFile[]` | List of component files. |
| `generated_at` | `datetime` | Pack generation timestamp. |

### RuntimeFile

| Field | Type | Description |
|---|---|---|
| `file_id` | `string` | Unique file ID. |
| `role` | `string` | File role (e.g., `system_prompt`, `world_state`, `memory_index`). |
| `file_ref` | `string` | Storage reference. |
| `checksum` | `string` | SHA-256 checksum for integrity verification. |

---

## Object Ownership Summary

| Object | Owned By | Editable From |
|---|---|---|
| Study | — (global) | `/workbench/settings` |
| Subject | Study | Subject-level views |
| SubjectBaseline | Subject | `/workbench/subjects/:subject_id/baseline` |
| GumiInstance | Subject (required) | `/workbench/subjects/:subject_id/gumi/...` only |
| HermesProfile | Subject | Subject-level views |
| Event | Subject | Immutable |
| InferenceReviewItem | Subject | `/workbench/subjects/:subject_id/inference` |
| CorrectionRecord | Subject | `/workbench/subjects/:subject_id/corrections` |
| BoundaryRecord | Subject | `/workbench/subjects/:subject_id/boundaries` |
| AuditLogEntry | Subject or Study | Immutable |
| Artifact | Subject or Study | Read-only in cross-subject view |
| RuntimeFilePack | GumiInstance (→ Subject) | `/workbench/subjects/:subject_id/gumi/runtime-files` |
