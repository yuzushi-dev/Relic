# Shared Continuity Memory — Architecture

## Components

```text
Gumi / Hermes conversation
  ↓
Hermes plugin: relic-shared-continuity
  ↓
Relic continuity service
  ↓
SQLite/PostgreSQL source-of-truth database
  ↓
Researcher Workbench Shared Continuity panel
```

## Not a Hermes memory provider

This must be implemented as a Hermes general plugin, not as a memory provider.

Reason:

```text
Hermes memory providers are broad recall providers.
Shared Continuity Memory is domain-specific, consent-bound, correction-bound, TTL-bound, and subject-scoped.
```

## Responsibilities

### Hermes native memory

Stores minimal stable instruction:

```text
Shared continuity is enabled for this subject.
Use subject words.
Do not diagnose.
Call Relic continuity tools for storage and recall.
```

### Hindsight

May provide broad recall for non-authoritative context.

Must not be source of truth for continuity markers.

### Shared Continuity Memory

Owns:

```text
continuity markers
follow-ups
corrections
marker edges
scope pause/resume state
audit events
recall limits
visibility flags
```

## Plugin surface

Hermes plugin name:

```text
relic-shared-continuity
```

Plugin type:

```text
general plugin
```

Required files:

```text
plugin.yaml
__init__.py
schemas.py
tools.py
hooks.py
skill/SKILL.md
```

## Tools

```text
relic_continuity_remember_marker
relic_continuity_correct_marker
relic_continuity_get_due_followups
relic_continuity_get_recent_markers
relic_continuity_forget_marker
relic_continuity_pause_scope
relic_continuity_resume_scope
```

## Hooks

```text
pre_llm_call
post_llm_call
transform_llm_output
```

`pre_llm_call` injects a small context block containing only due and allowed continuity threads.

`post_llm_call` writes audit events and optional candidate-marker telemetry. It must not silently convert user content into confirmed marker.

`transform_llm_output` blocks or rewrites forbidden clinical/backend/tracking language before delivery.
