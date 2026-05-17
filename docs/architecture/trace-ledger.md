# Chronicle Trace Ledger

> **Version**: chronicle-ledger/v1  
> **Status**: Implemented (2026-05-16)  
> **Owner**: Relic Core Team

---

## Overview

Chronicle is the audit-grade trace ledger for Relic. It provides dual-write persistence (SQLite + JSONL) for all governance decisions, context events, and runtime observations.

**Design Principle**: Chronicle is append-only, redacted, and consent-gated.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Event Emitter                            │
│  (relic/chronicle/emitter.py)                                │
└─────────────────────┬───────────────────────────────────────┘
                      │
         ┌────────────┴────────────┐
         │                         │
         ▼                         ▼
┌─────────────────┐       ┌─────────────────┐
│   SQLite DB     │       │   JSONL Files   │
│ (structured)    │       │ (append-only)   │
│ ~/.relic/       │       │ ~/.relic/       │
│ chronicle.db    │       │ journal/        │
└─────────────────┘       └─────────────────┘
```

### Dual-Write Strategy

1. **JSONL append FIRST** (immutable forensic journal)
2. **SQLite insert SECOND** (source of truth for queries)

**Failure handling**:
- If SQLite fails → JSONL already written → `chronicle verify --repair` can recover
- If JSONL fails → Do NOT write SQLite → fail-open with error code

---

## Schema

### Event Model

| Field | Type | Description |
|-------|------|-------------|
| `event_id` | UUID | Unique event identifier |
| `event_type` | string | Snake_case type (see catalogue below) |
| `event_category` | EventCategory | Category for grouping |
| `trace_id` | UUID | Trace correlation ID |
| `run_id` | UUID | Optional run identifier |
| `session_id` | UUID | Optional session ID |
| `subject_id` | string | Subject reference |
| `source_module` | string | Emitting module path |
| `timestamp` | string | UTC ISO timestamp |
| `payload` | dict | Redacted event payload |
| `payload_hash` | string | SHA-256 hash of payload |
| `payload_redacted` | bool | Redaction flag |
| `sensitivity` | PrivacyLevel | Data sensitivity level |
| `visibility` | VisibilityLevel | Access level |
| `consent_basis` | string | Legal basis for processing |
| `retention_policy` | RetentionPolicy | Retention duration |

### Companion Records

| Record | Purpose | Migration |
|--------|---------|-----------|
| `Decision` | Governance decisions | 0004 |
| `StateSnapshot` | Periodic state snapshots | 0005 |
| `ProvenanceEdge` | PROV-O relations | 0006 |
| `AccessLogEntry` | Access audit trail | 0007 |

---

## Event Type Catalogue

### Runtime Events (`relic.hermes_adapter`)

| Event Type | Category | Description |
|------------|----------|-------------|
| `runtime_received` | runtime | Hermes envelope received at boundary |
| `identity_resolved` | runtime | Sender→subject mapping completed |
| `session_key_bound` | runtime | Session key hash bound to envelope |
| `tool_call_observed` | runtime | Hermes tool call observed |

### Governance Events (`relic.hermes_adapter.governance`)

| Event Type | Category | Description |
|------------|----------|-------------|
| `source_policy_checked` | governance | Source class taxonomy check |
| `context_pack_requested` | governance | PromptContextPack build requested |
| `context_item_admitted` | governance | Context item admitted to pack |
| `context_item_blocked` | governance | Context item blocked from pack |
| `context_pack_rendered` | governance | PromptContextPack rendered |
| `delivery_decision_made` | governance | Delivery gate decision rendered |

### Identity Events (`relic.hermes_adapter.identity`)

| Event Type | Category | Description |
|------------|----------|-------------|
| `consent_granted` | identity | User granted multi-chat consent |
| `consent_revoked` | identity | User revoked multi-chat consent |
| `explicit_mapping_registered` | identity | Sender→subject mapping registered |

### Output Events (`relic.hermes_adapter.output`)

| Event Type | Category | Description |
|------------|----------|-------------|
| `output_reviewed` | output | OutputCritic reviewed LLM output |
| `output_blocked` | output | Output blocked by critic/filter |
| `output_transformed` | output | Output transformed by hook |
| `escalation_notified` | safety | Safety escalation triggered |

### Handoff Events (`relic.hermes_adapter.handoff_gate`)

| Event Type | Category | Description |
|------------|----------|-------------|
| `handoff_requested` | handoff | Session handoff requested |
| `handoff_authorized` | handoff | Handoff authorized by gate |
| `handoff_blocked` | handoff | Handoff blocked by gate |

### Approval Events (`relic.hermes_adapter.approvals`)

| Event Type | Category | Description |
|------------|----------|-------------|
| `approval_requested` | approval | Approval requested for action |
| `approval_granted` | approval | Approval granted |
| `approval_denied` | approval | Approval denied |

### Cron Events (`relic.hermes_adapter.cron_bridge`)

| Event Type | Category | Description |
|------------|----------|-------------|
| `proactive_checkin_scheduled` | cron | Proactive check-in scheduled |
| `proactive_message_delivered` | cron | Proactive message delivered |
| `proactive_message_blocked` | cron | Proactive message blocked |
| `cron_decision_made` | cron | Cron/watcher decision rendered |

---

## Redaction Policy

### What is Redacted

- All user message content
- All subject identifiers (hashed for correlation)
- All profile content summaries
- All context item payloads

### What is Preserved

- Event types and categories
- Timestamps and durations
- Decision outcomes (not rationale)
- Numeric metrics (token counts, latency)

### Hash Algorithm

```python
import hashlib

def compute_hash(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode()).hexdigest()[:32]}"
```

---

## Consent Gate

All Chronicle events require a legal basis:

| Basis | Description |
|-------|-------------|
| `memory_storage` | User consented to memory storage |
| `analytics` | User consented to analytics |
| `roleplay` | User consented to roleplay features |
| `data_sharing` | User consented to data sharing |
| `SAFETY` | Legitimate interest (safety escalation) |
| `PRIVACY` | Legitimate interest (privacy protection) |
| `INCIDENT` | Legitimate interest (incident response) |

---

## Retention Policies

| Policy | Duration | Description |
|--------|----------|-------------|
| `ephemeral` | < 1h | Auto-deleted by reaper |
| `short_30d` | 30 days | Short-term debugging |
| `standard_365d` | 1 year | Default retention |
| `extended_research` | 3 years | Research purposes |
| `legal_hold` | Indefinite | Legal/compliance hold |

---

## Access Control

### Visibility Levels

| Level | Access |
|-------|--------|
| `researcher` | Default, researcher-only |
| `admin` | Admin-level (includes researcher) |
| `subject_export` | Includable in GDPR export |

### Access Audit

Every read operation is logged in `chronicle_access_log`:

```sql
CREATE TABLE chronicle_access_log (
    access_id TEXT PRIMARY KEY,
    trace_id TEXT,
    access_kind TEXT,
    accessed_at TEXT,
    accessor_id TEXT,
    query_hash TEXT
);
```

---

## Query Interface

### Python API

```python
from relic.chronicle.reader import ChronicleReader

reader = ChronicleReader()

# Get events by subject
events = reader.get_events_by_subject("subject-123", limit=100)

# Get events by type
events = reader.get_events_by_type("context_pack_requested")

# Get timeline
timeline = reader.get_timeline(
    trace_id="trace-abc",
    start_time="2026-05-16T00:00:00Z",
    end_time="2026-05-16T23:59:59Z",
)
```

### CLI

```bash
# List recent events
relic chronicle list --limit 50

# Get events by subject
relic chronicle query --subject subject-123

# Export subject data (GDPR)
relic chronicle export --subject subject-123 --output gdpr-export.json

# Verify journal integrity
relic chronicle verify --repair
```

---

## References

- `relic/chronicle/schema.py` — Pydantic models
- `relic/chronicle/emitter.py` — Dual-write emitter
- `relic/chronicle/reader.py` — Query interface
- `relic/chronicle/redaction.py` — Redaction utilities
- `relic/chronicle/consent_gate.py` — Consent verification
- `relic/chronicle/retention.py` — Retention reaper
- `docs/architecture/hermes-current-state.md` — Hermes integration context
