# Event Registry

## Objective

Define the canonical event registry for Hermes, Sensitive Pattern Governance (PR32), and Shared Continuity Memory (PR33).

## Event Base Fields

Every event MUST include the following fields:

| Field | Type | Description |
|-------|------|-------------|
| event_id | string | Unique event identifier (UUID) |
| subject_id | string | Subject scope identifier |
| gumi_instance_id | string | Gumi instance scope identifier |
| hermes_profile_id | string | Hermes profile scope identifier |
| event_class | string | Classification of the event |
| ontological_class | string | Philosophical category of the event |
| timestamp | string | ISO 8601 timestamp |
| source_refs | array | References to source data |
| policy_snapshot_id | string | Policy state at event time |

## Ontological Classes

| Class | Description |
|-------|-------------|
| empirical_user_interaction | Direct user input or action |
| active_elicitation | Gumi actively eliciting information |
| proactive_support | Gumi proactively providing support |
| gumi_diegetic_event | Event within the Gumi narrative world |
| expressive_media | Creative or expressive output |
| user_response_to_gumi | User responding to Gumi |
| system_inference | System-inferred state or intent |
| correction | Correction to previous state |
| governance_decision | Policy or governance decision |
| system_maintenance | System-level operation |

## Event Metadata Redaction

| Field | Redaction Rule |
|-------|----------------|
| raw_text | Redacted unless explicitly approved |
| provider_logs | Researcher-only access |
| session_keys | Always hashed |
| credentials | Never stored |

## PR30 Events

PR30 events emitted by Hermes hooks:

- `hermes_transform_llm_output` - Transform LLM output before delivery
- `hermes_no_agent` - Block agentic mode activation

## PR32 Events

PR32 sensitive pattern governance events:

- `sensitive_pattern_detected` - Safety signal detected
- `behavior_policy_patch_applied` - Patch applied with label stripping

## PR33 Events

PR33 continuity marker events:

- `continuity_marker_created` - New continuity marker stored
- `continuity_marker_corrected` - Correction to existing marker

## Block Conditions

| Block ID | Condition |
|----------|-----------|
| BLOCKED_EVENT_WITHOUT_SUBJECT | Event lacks subject scope |
| BLOCKED_EVENT_WITHOUT_ONTOLOGICAL_CLASS | Event missing ontological_class |
| BLOCKED_EVENT_METADATA_REDACTION_UNDEFINED | Redaction rules not defined |
| BLOCKED_PR30_EVENT_NOT_REGISTERED | PR30 event not in registry |
| BLOCKED_PR32_EVENT_NOT_REGISTERED | PR32 event not in registry |
| BLOCKED_PR33_EVENT_NOT_REGISTERED | PR33 event not in registry |
