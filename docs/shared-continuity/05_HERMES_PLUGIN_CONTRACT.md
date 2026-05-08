# Hermes Plugin Contract - relic-shared-continuity

## Plugin type

General plugin.

Not a memory provider.

## Directory

```text
~/.hermes/plugins/relic-shared-continuity/
```

Project-local plugin is allowed only if explicitly enabled and trusted:

```text
./.hermes/plugins/relic-shared-continuity/
```

## Required files

```text
plugin.yaml
__init__.py
schemas.py
tools.py
hooks.py
skill/SKILL.md
```

## Tools

### relic_continuity_remember_marker

Creates a confirmed marker.

Must require:

```text
subject_id
gumi_instance_id
hermes_profile_id
marker_type
subject_words
source
clinical_interpretation_allowed = false
```

### relic_continuity_correct_marker

Stores subject correction and updates marker final wording.

### relic_continuity_get_due_followups

Returns due follow-ups after applying TTL, recall, pause, burden, quiet-hour, and subject-scope rules.

### relic_continuity_get_recent_markers

Returns recent active markers for summaries.

### relic_continuity_forget_marker

Forgets or archives a marker on user request.

### relic_continuity_pause_scope

Pauses one continuity scope.

### relic_continuity_resume_scope

Resumes one continuity scope.

## Hooks

### pre_llm_call

Injects only minimal continuity context.

### post_llm_call

Logs audit events and non-authoritative candidate telemetry.

Must not silently save markers as confirmed.

### transform_llm_output

Blocks or rewrites:

```text
diagnostic language
clinical labels
pattern/tracking language
backend disclosure
overly app-like phrasing
```

## Skill

Skill name:

```text
relic:shared-continuity
```

Purpose:

```text
Teach Gumi how to keep the thread naturally.
```
