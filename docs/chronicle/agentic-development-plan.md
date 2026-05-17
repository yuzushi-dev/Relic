# Chronicle — Agentic Development Plan (extended)

**Data:** 2026-05-16  
**Stato:** plan di implementazione agentica complementare a `docs/chronicle/legacy/agentic_dev_v1_scaffold.md`. Lo presuppone e lo estende. Quando i due divergono, **prevale questo documento** (più recente, integra audit del repo).

**Riferimento architetturale:** `docs/chronicle/research.md`.

**Audience:** coding agents (subagent_type qualunque) che eseguono task bounded. Ogni task qui dentro deve essere selezionabile, verificabile, e ≤ una sessione di lavoro.

---

## 0. Lettura obbligatoria prima di iniziare

Un agente DEVE leggere — in ordine — prima di toccare codice:

1. `docs/chronicle/research.md` — research document esteso (modello canonico, taxonomy, governance).
2. `docs/chronicle/legacy/research_v1_scaffold.md` — research document iniziale (OTel + Phoenix + schemi base).
3. `docs/chronicle/legacy/agentic_dev_v1_scaffold.md` — plan iniziale (14 step, integration code-points).
4. Questo file.
5. I file Relic toccati dal task assegnato (Read tool su path absoluti).

**Mai assumere repository structure** senza verifica con `Glob`/`Bash ls`/`find` o con `Read` sul file specifico.

---

## 1. Development goals

### 1.1 Goal G1 — Capture unificata
Un solo event store (SQLite + JSONL mirror) cattura **events, decisioni, state snapshots, artifact provenance** da tutti i sottosistemi Relic.

### 1.2 Goal G2 — Riuso infrastruttura
Zero duplicazione di moduli già presenti: `relic/db/`, `relic/artifacts/`, `relic/control/`, `relic/correction/`, `relic/persistence.py`, `relic/compiler/lineage.py` sono **dipendenze obbligate**, non da reinventare.

### 1.3 Goal G3 — Privacy GDPR-aligned
Capture-time consent enforcement, sensitivity labels (`PrivacyLevel`), retention by category, deletion cascading, audit dell'audit.

### 1.4 Goal G4 — Researcher inspection
CLI `chronicle` (`query`, `timeline`, `decision`, `snapshot`, `provenance`, `stats`, `export`, `delete`, `reaper`, `replay`) + HTML report generator. UI opzionale Phoenix in fase 5.

### 1.5 Goal G5 — Acceptance criteria pass
Le 23 domande di `docs/chronicle/research.md` §16 sono rispondibili automaticamente da test.

---

## 2. Non-goals

- Non costruire un secondo DB scollegato da `relic/db/`.
- Non sostituire `relic/control/{consent,delete,export,incident}.py`.
- Non emettere contenuto raw (prompt, risposte, marker, payload utente).
- Non hard-dipendere da Phoenix / Langfuse / OTel collector (tutti opzionali).
- Non costruire UI web prima di stabilizzare lo schema eventi.
- Non rompere i 7 JSONL legacy: dual-write per ≥ 3 minor release.
- Non introdurre features speculative (es. ML anomaly detection sul trace) in fase 1-4.

---

## 3. Repository areas to inspect first

Ogni agente, indipendentemente dal task, **deve** prima fare almeno questi read:

| Path | Perché |
|------|--------|
| `relic/db/__init__.py` | API connessione SQLite |
| `relic/db/loader.py` | migration loader pattern |
| `relic/db/migrations/` | numerazione e formato migration esistenti |
| `relic/schemas.py` | `LineageMixin`, `*Record` modelli |
| `relic/artifacts/types.py` | `Artifact`, `LineageRef`, `CorrectionCutoff`, `RuntimeProfilePack` |
| `relic/artifacts/registry.py` | `ArtifactRegistry.register/get/get_descendants/verify_integrity` |
| `relic/artifacts/checksums.py` | `compute_checksum`, `hash_prompt`, `hash_hint` (usare questi, mai re-implementare hash) |
| `relic/control/consent.py` | `ConsentManager`, `ConsentType`, `ConsentScope` |
| `relic/control/delete.py` | `DeleteManager.dry_run/delete`, cascading invalidate |
| `relic/control/export.py` | `ExportManager`, `ExportFormat`, `ExportOptions` |
| `relic/control/incident.py` | `IncidentReporter`, severities, quarantine |
| `relic/persistence.py` | `PrivacyLevel` enum (SAFE/S2/S1/S0) |
| `relic/privacy/trace.py` | `PrivacyTrace` v1 |
| `relic/correction/propagation.py` | `CorrectionPropagator`, `CorrectionType`, `CorrectionTrace` |
| `relic/compiler/lineage.py` | `ArtifactLineage`, `LineageTracker` |
| `relic/gumi_plugin/cron_wiring.py` | `_evaluate_decision`, `emit_decision_event`, `make_decision` |
| `relic/gumi/llm_narrator.py` | `_call_llm` (entry instrumentation LLM) |
| `relic/hermes_plugin/memory_provider.py` | `prefetch`, `sync_turn` |
| `relic/hermes_plugin/hooks.py` | hook dispatcher |
| `relic/hermes_plugin/soul_loader.py` | SOUL.md load |
| `relic/hermes_plugin/tool_permissions.py` | tool permission check |
| `relic/hermes_plugin/fail_safe.py` | fallback |
| `relic/profile/registry.py` | profile read/write + `profile_edit_log.jsonl` |
| `relic/profile/bootstrap_tui.py` | bootstrap step machine + `bootstrap_session.jsonl` |
| `relic/cac/controller.py` | admission evaluate |
| `relic/cac/trace.py` | `CACTraceWriter` + `cac_trace.jsonl` |
| `relic/eval/harness.py` | eval pipeline (entry per `experiment_id`) |
| `docs/chronicle/legacy/research_v1_scaffold.md` | scaffold iniziale (riferimento) |
| `docs/chronicle/legacy/agentic_dev_v1_scaffold.md` | step iniziali (riferimento) |
| `docs/chronicle/research.md` | research esteso (questo plan vi si appoggia) |

---

## 4. Existing scaffold assessment

| Cosa lo scaffold copre bene | Cosa manca / da correggere |
|----------------------------|---------------------------|
| Strumentazione `cron_wiring`, `llm_narrator`, `memory_provider`, hooks, CAC, DeliveryGate (Step 2-7) | Non considera `soul_loader`, `tool_permissions`, `fail_safe`, `correction/propagation`, `control/incident`, `profile/registry` write log, `eval/harness` |
| Schemi base (Cron/LLM/Memory/Hook/Delivery/CAC/ProfileBootstrap traces) | Mancano `decision_record` separato da event, `state_snapshot`, `artifact_provenance_edge`, `chronicle_access` audit |
| Privacy "no raw content" + SHA-256 | Non integra `PrivacyLevel` esistente, `ConsentType` esistente, retention enum, secret detector |
| Tracer Python (`relic/chronicle/tracer.py`) con JSONL+SQLite+OTLP exporter (Step 1) | Crea un SQLite separato (`~/.relic/chronicle/traces.db`) invece di estendere `relic/db/` con migration |
| CLI `chronicle-query` (Step 9) | Manca: timeline, decision, snapshot, provenance, replay, export-cascade, delete-cascade, reaper |
| Test base tracer (Step 10) | Manca: test integrazione consent gate, sensitivity drop, deletion cascade, schema migration |
| Conversation turn + topic + engagement (Step 11-13) | Non aggancia consent/sensitivity, topic classifier non gestisce sensitive_user_data |
| Docker Phoenix (Step 8) | OK, ma deve essere opt-in profile, non default. Whitelist OTLP host esplicita. |

**Decisione**: lo scaffold rimane riferimento valido per i blocchi che copre. Questo plan **aggiunge** fase 0 (integration), fase 6 (governance), fase 7 (replay), e corregge la scelta di storage (un solo SQLite, non due).

---

## 5. Proposed folder structure

```
relic/
├── chronicle/                    # NEW
│   ├── __init__.py              # public API: emit, query, etc.
│   ├── schema.py                # Pydantic models (Event, Decision, Snapshot, ProvenanceEdge)
│   ├── enums.py                 # EventCategory, RetentionPolicy, VisibilityLevel, ReasoningCapture
│   ├── context.py               # contextvars (trace_id, run_id, session_id, span_id)
│   ├── emitter.py               # write-path: dual SQLite+JSONL, consent gate, secret filter
│   ├── reader.py                # read-path: SQL queries, joins (events+decisions+snapshots)
│   ├── exporters/
│   │   ├── __init__.py
│   │   ├── jsonl.py             # append JSONL
│   │   ├── sqlite.py            # write SQLite via relic.db
│   │   ├── otlp.py              # opt OTLP (Phoenix/Jaeger)
│   │   └── parquet.py           # opt fase 4 — DuckDB analytics export
│   ├── snapshots.py             # state snapshot capture+diff
│   ├── provenance.py            # artifact provenance edges
│   ├── consent_gate.py          # capture-time consent enforcement
│   ├── redaction.py             # secret detector + payload redaction
│   ├── retention.py             # reaper logic
│   ├── access_audit.py          # chronicle_access events
│   ├── replay.py                # state replay primitive (fase 7)
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── legacy_jsonl.py      # legge i 7 JSONL legacy → chronicle events
│   │   ├── otel_semconv.py      # mappatura attributi gen_ai.* / openinference.*
│   │   ├── ecs.py               # export Elastic Common Schema (opt)
│   │   └── prov_o.py            # export W3C PROV-O JSON-LD (opt)
│   └── cli/
│       ├── __init__.py
│       ├── main.py              # entry chronicle CLI
│       ├── query.py
│       ├── timeline.py
│       ├── decision.py
│       ├── snapshot.py
│       ├── provenance.py
│       ├── stats.py
│       ├── export_cmd.py
│       ├── delete_cmd.py
│       ├── reaper.py
│       ├── replay_cmd.py
│       └── report_html.py
│
relic/db/migrations/
├── ...                          # esistenti
└── NN_chronicle_events.sql       # NEW
    NN+1_chronicle_decisions.sql
    NN+2_chronicle_state_snapshots.sql
    NN+3_chronicle_provenance_edges.sql
    NN+4_chronicle_access_log.sql

tests/chronicle/
├── __init__.py
├── test_schema.py
├── test_emitter.py
├── test_consent_gate.py
├── test_redaction.py
├── test_sensitivity.py
├── test_retention.py
├── test_deletion_cascade.py
├── test_access_audit.py
├── test_snapshots.py
├── test_provenance.py
├── test_cli_query.py
├── test_cli_timeline.py
├── test_cli_export.py
├── test_cli_delete.py
├── test_replay.py
├── test_acceptance.py           # le 23 domande
└── fixtures/
    └── sample_traces.jsonl
```

**Vincoli folder structure:**
- `relic/chronicle/` non importa da `relic/gumi/`, `relic/hermes_plugin/`, `relic/gumi_plugin/`. Le integrazioni avvengono dentro QUEI moduli che importano da `relic/chronicle/`, non viceversa.
- `relic/chronicle/__init__.py` esporta solo l'API public: `emit_event`, `emit_decision`, `emit_snapshot`, `emit_provenance_edge`, `start_span`, `get_trace_id`, `new_trace_id`, `set_trace_id`, `register_session`, `register_run`, `register_experiment`.

---

## 6. Required schemas (mandatory)

### 6.1 Migration `NN_chronicle_events.sql`

```sql
CREATE TABLE IF NOT EXISTS chronicle_events (
    event_id            TEXT PRIMARY KEY,
    event_type          TEXT NOT NULL,
    event_category      TEXT NOT NULL,
    trace_id            TEXT NOT NULL,
    run_id              TEXT,
    session_id          TEXT,
    parent_event_id     TEXT,
    experiment_id       TEXT,
    subject_id          TEXT,
    agent_id            TEXT,
    profile_id          TEXT,
    hermes_profile_id   TEXT,
    actor_type          TEXT,
    actor_id            TEXT,
    source_module       TEXT,
    target_module       TEXT,
    timestamp           TEXT NOT NULL,   -- ISO8601 microseconds UTC
    duration_ms         REAL,
    input_refs          TEXT,            -- JSON array of refs
    output_refs         TEXT,            -- JSON array of refs
    payload_redacted    INTEGER DEFAULT 0,
    payload_hash        TEXT,
    payload             TEXT,            -- JSON dict
    sensitivity         TEXT NOT NULL DEFAULT 'SAFE',
    visibility          TEXT NOT NULL DEFAULT 'researcher',
    consent_basis       TEXT,
    retention_policy    TEXT NOT NULL DEFAULT 'standard_365d',
    tags                TEXT,            -- JSON array of "k:v"
    severity            TEXT NOT NULL DEFAULT 'info',
    validation_status   TEXT,
    error_code          TEXT,
    retry_count         INTEGER DEFAULT 0,
    schema_version      TEXT NOT NULL DEFAULT 'chronicle-event/v1',
    created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chronicle_events_trace        ON chronicle_events(trace_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_events_session      ON chronicle_events(session_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_events_run          ON chronicle_events(run_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_events_experiment   ON chronicle_events(experiment_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_events_subject      ON chronicle_events(subject_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_events_profile      ON chronicle_events(profile_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_events_type         ON chronicle_events(event_type);
CREATE INDEX IF NOT EXISTS idx_chronicle_events_category     ON chronicle_events(event_category);
CREATE INDEX IF NOT EXISTS idx_chronicle_events_timestamp    ON chronicle_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_chronicle_events_parent       ON chronicle_events(parent_event_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_events_severity     ON chronicle_events(severity);
CREATE INDEX IF NOT EXISTS idx_chronicle_events_sensitivity  ON chronicle_events(sensitivity);
CREATE INDEX IF NOT EXISTS idx_chronicle_events_retention    ON chronicle_events(retention_policy);
```

### 6.2 Migration `NN+1_chronicle_decisions.sql`

```sql
CREATE TABLE IF NOT EXISTS chronicle_decisions (
    decision_id            TEXT PRIMARY KEY,
    trace_id               TEXT NOT NULL,
    run_id                 TEXT,
    session_id             TEXT,
    subject_id             TEXT,
    actor_type             TEXT,         -- agent|rule|user|system
    actor_id               TEXT,
    decision_kind          TEXT NOT NULL,
    selected_action        TEXT NOT NULL,  -- JSON dict
    rejected_alternatives  TEXT,           -- JSON array
    observable_inputs      TEXT,           -- JSON dict
    observable_outputs     TEXT,           -- JSON dict
    confidence             REAL,
    uncertainty_notes      TEXT,
    evidence_refs          TEXT,           -- JSON array
    rationale_summary      TEXT,           -- max 280 char enforced
    consent_basis          TEXT,
    sensitivity            TEXT NOT NULL DEFAULT 'SAFE',
    validation_status      TEXT NOT NULL DEFAULT 'pending',
    timestamp              TEXT NOT NULL,
    schema_version         TEXT NOT NULL DEFAULT 'chronicle-decision/v1',
    created_at             TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chronicle_decisions_trace     ON chronicle_decisions(trace_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_decisions_session   ON chronicle_decisions(session_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_decisions_subject   ON chronicle_decisions(subject_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_decisions_kind      ON chronicle_decisions(decision_kind);
CREATE INDEX IF NOT EXISTS idx_chronicle_decisions_actor     ON chronicle_decisions(actor_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_decisions_status    ON chronicle_decisions(validation_status);
```

### 6.3 Migration `NN+2_chronicle_state_snapshots.sql`

```sql
CREATE TABLE IF NOT EXISTS chronicle_state_snapshots (
    snapshot_id            TEXT PRIMARY KEY,
    snapshot_type          TEXT NOT NULL,
    subject_id             TEXT,
    scope_ref              TEXT,
    captured_at            TEXT NOT NULL,
    trigger_event_id       TEXT,
    previous_snapshot_id   TEXT,
    content_hash           TEXT NOT NULL,
    content_ref            TEXT,             -- artifact_id or blob path
    content_size_bytes     INTEGER,
    diff_from_previous     TEXT,             -- JSON dict
    consent_basis          TEXT,
    sensitivity            TEXT NOT NULL DEFAULT 'SAFE',
    retention_policy       TEXT NOT NULL DEFAULT 'standard_365d',
    schema_version         TEXT NOT NULL DEFAULT 'chronicle-snapshot/v1',
    created_at             TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chronicle_snap_subject  ON chronicle_state_snapshots(subject_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_snap_type     ON chronicle_state_snapshots(snapshot_type);
CREATE INDEX IF NOT EXISTS idx_chronicle_snap_scope    ON chronicle_state_snapshots(scope_ref);
CREATE INDEX IF NOT EXISTS idx_chronicle_snap_captured ON chronicle_state_snapshots(captured_at);
CREATE INDEX IF NOT EXISTS idx_chronicle_snap_prev     ON chronicle_state_snapshots(previous_snapshot_id);
```

### 6.4 Migration `NN+3_chronicle_provenance_edges.sql`

```sql
CREATE TABLE IF NOT EXISTS chronicle_provenance_edges (
    edge_id              TEXT PRIMARY KEY,
    artifact_id          TEXT NOT NULL,    -- target artifact (FK artifact_records.id)
    from_node_type       TEXT NOT NULL,    -- event|snapshot|artifact
    from_node_id         TEXT NOT NULL,
    to_node_type         TEXT NOT NULL,    -- artifact
    to_node_id           TEXT NOT NULL,
    relation             TEXT NOT NULL,    -- PROV-O: used|wasGeneratedBy|wasDerivedFrom|wasInformedBy
    contribution_role    TEXT,             -- input|template|policy|filter|enricher
    weight               REAL DEFAULT 1.0,
    created_at           TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chronicle_prov_artifact  ON chronicle_provenance_edges(artifact_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_prov_from      ON chronicle_provenance_edges(from_node_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_prov_to        ON chronicle_provenance_edges(to_node_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_prov_relation  ON chronicle_provenance_edges(relation);
```

### 6.5 Migration `NN+4_chronicle_access_log.sql`

```sql
CREATE TABLE IF NOT EXISTS chronicle_access_log (
    access_id        TEXT PRIMARY KEY,
    accessor_id      TEXT NOT NULL,
    access_kind      TEXT NOT NULL,        -- query|export|delete|view
    target_filter    TEXT,                  -- JSON dict
    rows_returned    INTEGER,
    result_hash      TEXT,
    severity         TEXT NOT NULL DEFAULT 'info',
    timestamp        TEXT NOT NULL,
    schema_version   TEXT NOT NULL DEFAULT 'chronicle-access/v1'
);

CREATE INDEX IF NOT EXISTS idx_chronicle_access_accessor ON chronicle_access_log(accessor_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_access_kind     ON chronicle_access_log(access_kind);
CREATE INDEX IF NOT EXISTS idx_chronicle_access_timestamp ON chronicle_access_log(timestamp);
```

### 6.6 Pydantic models (`relic/chronicle/schema.py`)

Tutti i Pydantic models DEVONO ereditare da `LineageMixin` quando applicabile e validare `schema_version`. Esempio:

```python
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from relic.persistence import PrivacyLevel
from relic.control.consent import ConsentType


class EventCategory(str, Enum):
    MESSAGE = "message"
    MODEL = "model"
    TOOL = "tool"
    MEMORY = "memory"
    PROFILE = "profile"
    DECISION = "decision"
    ARTIFACT = "artifact"
    SAFETY = "safety"
    PRIVACY = "privacy"
    CONSENT = "consent"
    ADMIN = "admin"
    EVAL = "eval"
    BACKGROUND = "background"
    ERROR = "error"
    STATE_SNAPSHOT = "state_snapshot"
    PROVENANCE = "provenance"


class RetentionPolicy(str, Enum):
    EPHEMERAL = "ephemeral"
    SHORT_30D = "short_30d"
    STANDARD_365D = "standard_365d"
    EXTENDED_RESEARCH = "extended_research"
    LEGAL_HOLD = "legal_hold"


class VisibilityLevel(str, Enum):
    RESEARCHER = "researcher"
    ADMIN = "admin"
    SUBJECT_EXPORT = "subject_export"


class ReasoningCapture(str, Enum):
    NONE = "none"
    METRICS_ONLY = "metrics_only"
    REDACTED_SUMMARY = "redacted_summary"
    RAW_RESEARCHER_ONLY = "raw_researcher_only"


class Event(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: str
    event_category: EventCategory
    trace_id: UUID
    run_id: UUID | None = None
    session_id: UUID | None = None
    parent_event_id: UUID | None = None
    experiment_id: UUID | None = None
    subject_id: str | None = None
    agent_id: str | None = None
    profile_id: str | None = None
    hermes_profile_id: str | None = None
    actor_type: str | None = None
    actor_id: str | None = None
    source_module: str
    target_module: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    duration_ms: float | None = None
    input_refs: list[str] = Field(default_factory=list)
    output_refs: list[str] = Field(default_factory=list)
    payload_redacted: bool = False
    payload_hash: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    sensitivity: PrivacyLevel = PrivacyLevel.SAFE
    visibility: VisibilityLevel = VisibilityLevel.RESEARCHER
    consent_basis: ConsentType | None = None
    retention_policy: RetentionPolicy = RetentionPolicy.STANDARD_365D
    tags: list[str] = Field(default_factory=list)
    severity: str = "info"
    validation_status: str | None = None
    error_code: str | None = None
    retry_count: int = 0
    schema_version: str = "chronicle-event/v1"
```

Analoghi per `Decision`, `StateSnapshot`, `ProvenanceEdge`.

**Validation rules:**
- `rationale_summary` ≤ 280 char (validator).
- `tags` ogni elemento must match `^[a-z_]+:[\w-]+$`.
- `event_type` must match `^[a-z]+(_[a-z]+)*$` (snake_case).
- `payload_hash` se presente: deve essere `sha256:<16-64 hex>`.

### 6.7 Unificazione `PrivacyTrace`

I due `PrivacyTrace` (in `relic/privacy/trace.py` e `relic/persistence.py`) hanno schemi divergenti. Mantenerli, ma **aggiungere adapter** in `relic/chronicle/adapters/legacy_jsonl.py` che li converte a `Event(event_type="privacy_decision", ...)` con il payload §6.7 del research doc.

In una fase 2 (post-stabilizzazione), proporre PR per deprecare uno dei due. Non in fase 1.

---

## 7. Event taxonomy (riepilogo, vedi `research.md` §6 per schemi completi)

Schema canonical: §6.1 di questo doc + payload-specifici di `research.md` §6.

Categorie obbligatorie minime (fase 3):

| Category | Event types | Modulo origine |
|----------|-------------|----------------|
| `message` | `message_received`, `message_sent` | hermes_runtime, gumi_plugin/cron_wiring |
| `model` | `model_called`, `model_returned` | gumi/llm_narrator |
| `tool` | `tool_called`, `tool_returned` | hermes_plugin/tool_permissions + commands |
| `memory` | `memory_read`, `memory_write`, `memory_decay`, `memory_consolidation` | hermes_plugin/memory_provider, memory_dynamics, gumi_continuity, gumi_memory/providers |
| `profile` | `profile_read`, `profile_write_attempted`, `profile_write_applied`, `profile_write_rejected` | profile/registry |
| `decision` | metadata su `chronicle_decisions` table | tutti i decisori (cron_wiring, cac, critic, profile/inferred_fields, ...) |
| `artifact` | `artifact_registered`, `artifact_quarantined`, `artifact_invalidated` | artifacts/registry, control/incident |
| `safety` | `safety_escalation`, `incident_opened`, `incident_status_changed` | safety/escalation_notifier, control/incident |
| `privacy` | `privacy_decision` | privacy/*, persistence |
| `consent` | `consent_changed` | control/consent |
| `admin` | `chronicle_access`, `system_message_loaded`, `command_invoked` | chronicle/cli, hermes_plugin/soul_loader, hermes_plugin/commands |
| `eval` | `eval_run_started`, `eval_case_executed`, `eval_metric_computed` | eval/harness, eval/* |
| `background` | `background_job_started`, `background_job_completed`, `cron_fired`, `cron_scheduled`, `cron_drift` | gumi_plugin/cron_*, chronicle/topic_classifier |
| `error` | `error_raised`, `retry_started`, `fallback_triggered` | tutti i moduli con error handling |
| `state_snapshot` | (records vivono in tabella separata; event di tipo `snapshot_captured` opzionale per audit) | chronicle/snapshots |
| `provenance` | (records vivono in tabella separata) | chronicle/provenance |

---

## 8. Interface contracts

### 8.1 Public emit API

```python
# relic/chronicle/__init__.py

from contextvars import ContextVar
from contextlib import contextmanager

def emit_event(
    *,
    event_type: str,
    event_category: EventCategory,
    source_module: str,
    payload: dict[str, Any] | None = None,
    sensitivity: PrivacyLevel = PrivacyLevel.SAFE,
    consent_basis: ConsentType | None = None,
    parent_event_id: UUID | None = None,
    severity: str = "info",
    **kwargs,
) -> UUID:
    """Emit one event. Returns event_id. Fail-open (logs error, returns dummy on fail)."""

def emit_decision(
    *,
    decision_kind: str,
    selected_action: dict,
    actor_type: str,
    actor_id: str,
    observable_inputs: dict | None = None,
    rejected_alternatives: list[dict] | None = None,
    rationale_summary: str = "",          # ≤ 280 char, no CoT raw
    confidence: float | None = None,
    evidence_refs: list[str] | None = None,
    **kwargs,
) -> UUID:
    """Emit one decision record. Returns decision_id. Fail-open."""

def emit_snapshot(
    *,
    snapshot_type: str,
    subject_id: str | None,
    scope_ref: str,
    content: dict | str | bytes,
    trigger_event_id: UUID | None = None,
    previous_snapshot_id: UUID | None = None,
    sensitivity: PrivacyLevel = PrivacyLevel.SAFE,
    **kwargs,
) -> UUID:
    """Capture state snapshot. content è hashed + stored. Returns snapshot_id."""

def emit_provenance_edge(
    *,
    artifact_id: UUID,
    from_node_type: str,        # event|snapshot|artifact
    from_node_id: UUID,
    relation: str,              # PROV-O: used|wasGeneratedBy|wasDerivedFrom|wasInformedBy
    contribution_role: str | None = None,
    weight: float = 1.0,
) -> UUID:
    """Add an edge to artifact provenance graph. Returns edge_id."""

@contextmanager
def start_span(
    op: str,
    *,
    event_category: EventCategory = EventCategory.BACKGROUND,
    **kwargs,
):
    """Context manager: emit_event START on entry, emit_event COMPLETE/FAIL on exit. Sets parent_event_id automatically."""

def get_trace_id() -> UUID | None: ...
def new_trace_id() -> UUID: ...
def set_trace_id(trace_id: UUID) -> None: ...
def register_session(session_id: UUID) -> None: ...
def register_run(run_id: UUID) -> None: ...
def register_experiment(experiment_id: UUID) -> None: ...
```

### 8.2 Consent gate contract

```python
# relic/chronicle/consent_gate.py

def is_capture_allowed(consent_basis: ConsentType | None, subject_id: str | None) -> tuple[bool, str]:
    """
    Returns (allowed, reason). Called BEFORE writing event to store.

    Rules:
    - consent_basis = None → allowed (event sistema, no PII)
    - subject_id = None → allowed (event globale)
    - consent_basis in {SAFETY, PRIVACY, INCIDENT} → always allowed (legitimate interest)
    - else: ConsentManager.check_consent(consent_basis, session_id=None) must return True
    """
```

### 8.3 Redaction contract

```python
# relic/chronicle/redaction.py

SECRET_PATTERNS = [
    r"(?i)api[_-]?key\s*[:=]\s*[\w-]{16,}",
    r"(?i)bearer\s+[\w.-]{20,}",
    r"-----BEGIN\s+\w+\s+PRIVATE\s+KEY-----",
    # ...
]

def contains_secret(payload: dict | str) -> bool:
    """True if payload contains pattern match. Block emission."""

def redact_payload(payload: dict) -> dict:
    """Returns redacted copy. Replaces matched values with '[REDACTED]'."""
```

### 8.4 Deletion cascade contract

`chronicle delete --subject X` MUST:

1. Chiamare `DeleteManager(db_path).delete(scope=DeleteScope.SESSION, target_id=session_uuid_for_x)` per le tabelle Relic (prompts, corrections, artifacts).
2. Cancellare da `chronicle_events WHERE subject_id = X`.
3. Cancellare da `chronicle_decisions WHERE subject_id = X`.
4. Cancellare da `chronicle_state_snapshots WHERE subject_id = X`.
5. Cancellare da `chronicle_provenance_edges` con `from_node_id` o `to_node_id` orphan dopo i delete sopra.
6. Cancellare thinking files in `~/.relic/chronicle/thinking/` con event_id orphan.
7. Cancellare snapshot blobs in `~/.relic/chronicle/snapshots/` con snapshot_id orphan.
8. Emettere `chronicle_access` event con `access_kind=delete`, `target_filter={"subject_id": "X"}`, `rows_returned=<total>`.

Tutto **atomico** (singola transaction SQLite).

### 8.5 Export cascade contract

`chronicle export --subject X --output path.tar` MUST:

1. Chiamare `ExportManager(db_path).export(output_path=path/relic.json, options=ExportOptions(session_id=...))`.
2. Aggiungere a `path/` un file `chronicle_events.jsonl` con tutti gli eventi `subject_id=X` redatti per `visibility=subject_export` (esclude S0/S1).
3. Aggiungere `chronicle_decisions.jsonl`, `chronicle_state_snapshots.jsonl`, `chronicle_provenance_edges.jsonl`.
4. Aggiungere `MANIFEST.json` con: counts per categoria, schema_versions, redaction_applied.
5. Tar/gzip il path.
6. Emettere `chronicle_access` event con `access_kind=export`.

---

## 9. Storage requirements

### 9.bis Dual-write rationale & recovery model (chiarimento)

**Source of truth:** SQLite primary. Tutte le query (CLI, reader, reaper, export, delete) leggono **solo** da SQLite. JSONL non viene mai letto dal runtime.

**Ruolo JSONL:** journal forense append-only. Tre giustificazioni concrete:
1. **Forensic immutability:** SQLite supporta UPDATE/DELETE; un attaccante con accesso al file può alterare righe. JSONL è append-only by convention + filesystem permission, più difficile da manomettere senza lasciare traccia (rotation + gzip + esterno backup).
2. **SQLite corruption recovery:** se `~/.relic/relic.db` corrompe (rare ma documentato in literature SQLite), il JSONL permette `chronicle migrate --from-journal` per ricostruire `chronicle_*` tables (idempotente: skip se `(timestamp, source_module, payload_hash)` già presente).
3. **Out-of-band audit:** un esterno (security team, GDPR auditor) può grepare JSONL senza dover capire schema SQLite.

**WAL non sostituisce JSONL.** WAL risolve concorrenza scrittura, NON immutabilità né recovery cross-corruption. WAL si attiva comunque (PRAGMA) — è ortogonale.

**Sincronizzazione:** scrittura **atomica per evento**, ordine: JSONL append PRIMA, SQLite insert DOPO. Razionale: se SQLite fail (lock, disk full, schema mismatch), JSONL è già scritto e non si perde l'evento. Se JSONL fail (disk full), SQLite non viene neanche tentato — emit ritorna error code che il caller fail-open ignora.

**Divergence model (se SQLite e JSONL divergono):**
- SQLite > JSONL: impossibile (JSONL scritto prima). Se accade, indica race condition o bug → log critical, run `chronicle verify` per audit.
- JSONL > SQLite: normale dopo fail SQLite. `chronicle verify --repair` rigioca le righe JSONL mancanti in SQLite.

**Reaper opera su entrambi.** Quando un evento è eliminato per retention:
1. DELETE da SQLite.
2. **NON** rimuove la riga JSONL (append-only). Invece: file JSONL del giorno è candidato per `chronicle reaper --archive-jsonl` che lo tar+gzip-pa in `~/.relic/chronicle/archive/YYYY-MM.tar.gz` con flag `expired_events_count`. L'archivio è cancellabile manualmente solo dal researcher con `chronicle reaper --delete-archives --older-than 5y` (default mai automatico).

**Subject deletion (GDPR) sovrascrive append-only.** Eccezione: `chronicle delete --subject X` DEVE rimuovere righe JSONL contenenti `subject_id=X` per compliance. Implementazione: rewrite del file giornaliero senza le righe target, atomico via temp file + rename. Audit event con `severity=warn`. Non è append-violation reale: è obbligo legale che sovrasta convenzione forense.

| Aspetto | Requisito | Default |
|---------|-----------|---------|
| Primary store (source of truth) | SQLite via `relic/db/` migrations | `~/.relic/relic.db` (esistente) |
| Journal (forense, append-only) | JSONL daily-rotated, scritto PRIMA di SQLite | `~/.relic/chronicle/journal/YYYY-MM-DD.jsonl` |
| Snapshot blobs | filesystem | `~/.relic/chronicle/snapshots/{snapshot_id}.json[.enc]` |
| Thinking files | filesystem, AES-256-GCM | `~/.relic/chronicle/thinking/{trace_id}/{event_id}.txt.enc` |
| OTLP exporter | optional | `CHRONICLE_OTLP_ENDPOINT` env, host-whitelisted |
| Parquet analytics | fase 4 | `~/.relic/chronicle/parquet/events-YYYY-WW.parquet` |
| File permissions | owner-only | `chmod 600` su files, `chmod 700` su dirs |
| SQLite mode | WAL | `PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA busy_timeout=5000` |
| Bulk insert | batched | min 10 events/batch o 100ms hold |
| Encryption at-rest | `S1+` snapshots & thinking | AES-256-GCM, key da OS keyring (`keyring` Python lib) |
| Backup | daily JSONL gzip → `~/.relic/chronicle/archive/YYYY-MM.tar.gz` | reaper job |

---

## 10. API requirements (CLI)

### 10.1 `chronicle query`

```
chronicle query [--trace TRACE_ID] [--run RUN_ID] [--session SESSION_ID]
               [--subject SUBJECT] [--profile PROFILE]
               [--event-type TYPE] [--event-category CAT]
               [--sensitivity-min LEVEL] [--severity-min LEVEL]
               [--consent CONSENT_TYPE]
               [--since DURATION] [--until ISO8601]
               [--limit N] [--format json|jsonl|table]
```

### 10.2 `chronicle timeline`

```
chronicle timeline (--trace TRACE_ID | --session SESSION_ID | --run RUN_ID)
                  [--format waterfall|tree|json]
                  [--include decisions,snapshots,provenance]
```

Produce un waterfall ASCII (default) o JSON tree.

### 10.3 `chronicle decision`

```
chronicle decision --id DECISION_ID
```

Mostra `selected_action`, `rejected_alternatives`, `evidence_refs`, `confidence`, `rationale_summary`.

### 10.4 `chronicle snapshot`

```
chronicle snapshot --id SNAPSHOT_ID
chronicle snapshot --diff BEFORE_ID AFTER_ID
chronicle snapshot --history --scope SCOPE_REF [--limit N]
```

### 10.5 `chronicle provenance`

```
chronicle provenance --artifact ARTIFACT_ID [--depth N] [--format dot|json|tree]
```

`--format dot` produce Graphviz; `tree` ASCII; `json` per integrazione.

### 10.6 `chronicle stats`

```
chronicle stats --event-type TYPE --window DURATION [--group-by FIELD]
chronicle stats --metric latency_p95|tokens_per_second|error_rate|...
```

### 10.7 `chronicle export`

```
chronicle export --subject SUBJECT --output PATH.tar [--include events,decisions,snapshots,provenance]
                [--no-redact]    # researcher only, mandatory password
                [--dry-run]
```

### 10.8 `chronicle delete`

```
chronicle delete --subject SUBJECT [--dry-run]
chronicle delete --trace TRACE_ID [--dry-run]
chronicle delete --before ISO8601 [--dry-run]
```

Default: dry-run obbligatorio per > 1000 record stimati senza `--force`.

### 10.9 `chronicle reaper`

```
chronicle reaper [--policy ephemeral|short_30d|standard_365d|...] [--dry-run]
```

### 10.10 `chronicle replay`

```
chronicle replay --trace TRACE_ID [--state-only|--with-llm-calls] [--output PATH]
```

`--state-only` (default) ricostruisce state senza chiamare modelli. `--with-llm-calls` invoca i modelli con stessi params (no garanzia stessa risposta).

### 10.11 `chronicle report --html`

Genera HTML report autocontenuto da un trace_id o subject_id, include timeline, decision summaries, provenance graph (Graphviz SVG inline).

---

## 11. UI requirements

### 11.1 Fase 4 (must)

- CLI completo (§10).
- HTML report generator (sopra).
- Nessuna dipendenza web server.

### 11.2 Fase 5 (opt)

- Phoenix integration (`CHRONICLE_OTLP_ENDPOINT=http://localhost:6006/v1/traces`).
- docker-compose profile `chronicle`.

### 11.3 Fase 6+ (opt)

- Streamlit single-file app per ispezione locale.
- Graphviz online viewer come fallback.

---

## 12. Privacy requirements (mandatory)

1. **Capture-time consent enforcement**: prima di INSERT, chiama `consent_gate.is_capture_allowed`. Se `False` → drop event silently (log debug).
2. **Sensitivity labels**: ogni event ha `sensitivity` = `PrivacyLevel`. Default `SAFE`. S0/S1 events richiedono motivazione esplicita nel call site (parametro non default).
3. **Retention by policy**: ogni event ha `retention_policy`. Reaper periodico (`chronicle reaper`).
4. **Deletion cascading**: vedi §8.4.
5. **Hash mai raw**: usa `relic.artifacts.checksums.compute_checksum`. Payload solo numerico/hash/enum.
6. **Secret detector**: `redaction.contains_secret(payload)` chiamato pre-emit. Hit → drop + `error_raised(code=CHRONICLE_SECRET_FILTERED)`.
7. **Subject pseudonimi**: validator `subject_id` pattern `^[a-z][a-z0-9_-]{1,32}$`. Email/telefono → reject schema validation.
8. **Audit dell'audit**: ogni accesso emette `chronicle_access` event.
9. **Researcher-only mode**: capability `forensic` (cattura thinking raw, accede a S1+ snapshot decritti) richiede env `CHRONICLE_RESEARCHER_KEY` settata + audit event con `severity=warn`.
10. **Encryption at-rest**: S1+ snapshot e thinking files criptati AES-256-GCM.
11. **OTLP whitelist**: `CHRONICLE_OTLP_ENDPOINT` must match `^https?://(localhost|127\.0\.0\.1|\[::1\]|phoenix\.local|.*\.local)(:\d+)?(/.*)?$` salvo override `CHRONICLE_ALLOW_EXTERNAL_OTLP=1` (allora warning a startup).
12. **File permissions**: `umask 077` per files Chronicle.

---

## 13. Testing requirements

### 13.1 Test suite mandatory `tests/chronicle/`

| Test file | Cosa testa | Pass criteria |
|-----------|-----------|---------------|
| `test_schema.py` | Pydantic validation Event/Decision/Snapshot/ProvenanceEdge | rationale_summary > 280 char rifiutato; subject_id email rifiutato; tags malformati rifiutati |
| `test_emitter.py` | dual-write SQLite + JSONL | dopo emit, row in `chronicle_events` AND line in `journal/YYYY-MM-DD.jsonl`; payload_hash deterministico |
| `test_consent_gate.py` | capture-time gate | ANALYTICS no consent → event dropped; SAFETY consent_basis → sempre allowed |
| `test_redaction.py` | secret detector | `payload = {"key": "sk-..."}` → contains_secret True; emit → drop + error event |
| `test_sensitivity.py` | sensitivity rules | S0 event default visibility researcher; subject_export filter drops S0/S1 |
| `test_retention.py` | reaper | events con retention_policy=ephemeral > 1h vecchi → cancellati; legal_hold mai cancellati |
| `test_deletion_cascade.py` | delete cascade | `chronicle delete --subject X` cancella events + decisions + snapshots + provenance + thinking files; calls DeleteManager |
| `test_access_audit.py` | audit dell'audit | ogni `chronicle query` produce `chronicle_access` row; result_hash deterministico |
| `test_snapshots.py` | snapshot diff | snapshot N e N+1, `diff_from_previous` calcolato; previous_snapshot_id chain |
| `test_provenance.py` | provenance graph | emit_provenance_edge crea row; query `chronicle provenance --artifact A` ritorna sottografo |
| `test_cli_query.py` | CLI query filters | combinazioni `--subject X --event-type model_called --since 24h --limit 10` ritorna riga corretta |
| `test_cli_timeline.py` | CLI timeline | waterfall ASCII contiene tutti gli event types del trace |
| `test_cli_export.py` | CLI export | bundle tar contiene MANIFEST + tutti i JSONL; chiamata a ExportManager |
| `test_cli_delete.py` | CLI delete | dry-run mostra counts; real delete azzera; cascade verificato |
| `test_replay.py` | state replay | replay con `--state-only` ricostruisce ultimo snapshot identico al persisted |
| `test_acceptance.py` | 23 domande di `research.md` §16 | tutte rispondibili da query/timeline/etc., asserzioni esplicite |
| `test_legacy_jsonl_adapter.py` | adapter 7 JSONL legacy | conversione `decision_events.jsonl` → events idempotente |
| `test_otel_semconv_mapper.py` | mapping gen_ai.* / openinference.* | LLM event → attributi span corretti |
| `test_integration_cron_pipeline.py` | E2E cron checkin | simulato cron fire → tutti gli events tipici emessi con trace_id condiviso |
| `test_integration_llm_call.py` | E2E LLM call | model_called + model_returned + tokens_per_second computed |
| `test_integration_profile_update.py` | E2E profile write | snapshot before + decision + write_applied + snapshot after; diff valorizzato |

### 13.2 Vincoli test

- Run con SQLite in `tempfile.TemporaryDirectory()`, no global state.
- **Sequenziali**, mai `pytest-xdist`. (Da memory `feedback_test_load.md`: macchina debole, evitare paralleli.)
- Cleanup deterministico (no leftover files).
- Coverage target ≥ 85% su `relic/chronicle/`.

### 13.3 CI gate

Aggiungere job CI che esegue:
```bash
pytest tests/chronicle/ -v --tb=short
```

Più linter `ruff check relic/chronicle/` e type check `mypy relic/chronicle/`.

---

## 14. Migration requirements

### 14.1 Schema migrations

Numerate (`NN_chronicle_events.sql`, etc.) con `NN` = prossimo numero libero in `relic/db/migrations/`. Mai modificare migration esistente; nuove additive only.

### 14.2 Legacy JSONL migration

Step:

1. `chronicle migrate --from-legacy-jsonl ~/.relic/decision_events.jsonl` legge le righe e le riscrive come `chronicle_events` con `event_type="cron_decision_legacy"` (per disambiguare). Idempotente (skip se `payload_hash` già presente).
2. Stesso per `cac_trace.jsonl`, `privacy_trace.jsonl`, `escalation_log.jsonl`, `bootstrap_session.jsonl`, `profile_edit_log.jsonl`, `delivery_decision_log.jsonl`.
3. Una volta migrato, i produttori legacy continuano a scrivere (dual-write) per 3 minor release.

### 14.3 Schema version bump

Quando `chronicle-event/v1` → `v2`:

1. Nuova migration aggiunge colonne nuove (additive).
2. `relic/chronicle/schema.py` aggiorna model con default per nuovi field.
3. Migration script `chronicle migrate v1→v2` riscrive `schema_version` su righe vecchie (opzionale; le righe v1 restano leggibili).
4. Documentare in `docs/chronicle/CHANGELOG.md`.

---

## 15. Acceptance criteria

Vedi `docs/chronicle/research.md` §16 per le 23 domande di acceptance. **Definition of done** del progetto Chronicle:

- ✅ Tutte le 23 domande hanno test passante in `tests/chronicle/test_acceptance.py`.
- ✅ Coverage ≥ 85% su `relic/chronicle/`.
- ✅ CI verde.
- ✅ HTML report generabile da subject_id reale (fixture o real run).
- ✅ Dual-write con 7 JSONL legacy funzionante; eventi identici tra legacy file e chronicle_events table per stesso run.
- ✅ `chronicle delete --subject X` rimuove tutto, `chronicle query --subject X` ritorna 0 righe dopo.
- ✅ Reaper su retention `ephemeral` cancella events > 1h.
- ✅ Secret detector blocca emit di payload con API key fake.
- ✅ Documentazione `docs/chronicle/USAGE.md` (CLI esempi) e `docs/chronicle/INVENTORY.md` (mappa moduli).

---

## 16. Staged task breakdown

Ogni task qui sotto è **bounded** (≤ una sessione di lavoro, ≤ 5 file toccati salvo dove esplicitamente segnato). Numerazione `T0xx`. **Dipendenze esplicite**.

### Phase 0 — Audit & integration (must)

**Strategia: spike-first.** Eseguire T001 + T003 + T004 (inventory + migration) come **spike di validazione** prima di toccare Phase 1. Se le migration SQL falliscono per ragioni non previste (e.g., `relic/db/` ha vincoli FK incompatibili, formato migration runner diverso da `[0-9]*.sql`), si scopre con 4 ore di lavoro buttate, non con 4 settimane di Phase 1-3 sopra fondamenta sbagliate.

**Critical-path gate post-spike:** prima di iniziare T010, eseguire i 5 comandi sotto. Ogni comando deve uscire con exit code 0 e l'output atteso indicato. Se uno fail → STOP, aprire issue, ridefinire migration/schema prima di proseguire.

```bash
# 1. DB connection (sanity)
python -c "from relic.db import get_connection; c = get_connection(); c.execute('SELECT 1').fetchone(); c.close(); print('db_ok')"
# atteso stdout: db_ok

# 2. Migrations apply (incluse le 5 nuove chronicle_*)
python -c "from relic.db import init_db; init_db(); print('migrations_ok')"
# atteso stdout: migrations_ok

# 3. Schema chronicle_events visibile
python -c "from relic.db import get_connection; c = get_connection(); rows = c.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'chronicle_%'\").fetchall(); print(sorted(r[0] for r in rows))"
# atteso stdout (set, ordine alfabetico): ['chronicle_access_log', 'chronicle_decisions', 'chronicle_events', 'chronicle_provenance_edges', 'chronicle_state_snapshots']

# 4. LineageMixin shape invariata (campi attesi: id, created_at, updated_at — vedi relic/schemas.py:11)
python -c "from relic.schemas import LineageMixin; fields = set(LineageMixin.model_fields.keys()); expected = {'id', 'created_at', 'updated_at'}; assert fields == expected, f'shape changed: {fields}'; print('mixin_ok')"
# atteso stdout: mixin_ok

# 5. PrivacyLevel canonical path (deciso in T002) importabile
python -c "from relic.persistence import PrivacyLevel; assert {l.value for l in PrivacyLevel} >= {'s0', 's1', 's2', 'safe'}; print('privacy_ok')"
# atteso stdout: privacy_ok
# NOTA: se T002 decide path canonico = relic/privacy/, aggiornare questo comando di conseguenza.
```

Wrapper one-liner per CI:
```bash
bash -c 'for cmd in db_ok migrations_ok ...; do ... done'   # implementare come script tests/chronicle/spike_gate.sh
```

#### T001 Repo inventory writeup
**Scope:** scrivere `docs/chronicle/INVENTORY.md` con la mappa di §2 del research esteso.  
**Inputs:** `docs/chronicle/research.md` §2; `find relic -name "*.py" -maxdepth 3`.  
**Outputs:** un nuovo file Markdown ≤ 30 KB.  
**Verification:** ogni modulo Relic ≥ 1 riferimento; documenta `_PrivacyTrace_` conflict.  
**Touched files:** `docs/chronicle/INVENTORY.md` (new).  
**Dependencies:** none.

#### T002 PrivacyTrace reconciliation proposal **[HARD BLOCKER per T010+]**
**Scope:** scrivere `docs/chronicle/PRIVACY_TRACE_RECONCILIATION.md` che spiega quale dei due `PrivacyTrace` (privacy/trace.py vs persistence.py) diventa canonico, perché, e come fare deprecazione del secondo. NESSUN codice toccato in T002.  
**Inputs:** Read di entrambi i file.  
**Outputs:** proposta scritta + tabella mapping campi + **decisione definitiva** su quale modulo è source-of-truth per `PrivacyLevel`/`PrivacyTrace`.  
**Verification:** decision documentata + tabella import-path target per i moduli Phase 1.  
**Touched files:** 1 nuovo markdown.  
**Dependencies:** T001.  

**Perché è hard blocker:** T010 importa `PrivacyLevel`. Se T002 stabilisce che la sorgente canonica è `relic/privacy/` (non `relic/persistence.py`), allora `relic/chronicle/schema.py` deve importare da lì. Cambiare import dopo T015 significa toccare 20+ file in Phase 3. Risolvere PRIMA.

Se T002 conclude "serve un nuovo modulo `relic/privacy_core/` per unificare", quello diventa T002b prerequisite di T010.

#### T003 New SQLite migration (events table)
**Scope:** scrivere `relic/db/migrations/NN_chronicle_events.sql` (vedi §6.1).  
**Inputs:** verifica `ls relic/db/migrations/` per prossimo NN.  
**Outputs:** un file SQL.  
**Verification:** `python -m relic.db.loader` (o test esistente) lo carica senza errori; `CREATE TABLE` ha 24+ colonne.  
**Touched files:** 1 file SQL.  
**Dependencies:** T001.

#### T004 New SQLite migrations (decisions, snapshots, provenance, access_log)
**Scope:** scrivere le altre 4 migration (vedi §6.2-6.5).  
**Outputs:** 4 file SQL.  
**Touched files:** 4 file SQL.  
**Dependencies:** T003.

### Phase 1 — Schema & emitter foundation

**Split in 1a (parallel-safe) e 1b (sequential, depends on 1a).**

**Phase 1a:** T010 + T011 + T016 (test plumbing) — standalone, testabile subito. Nessuna dipendenza tra loro post-T004. Se Phase 1b incontra problemi in fase 2+, 1a è già pronta e isolata.

**Phase 1b:** T012 + T013 + T014 + T015 — dipendono da 1a + T002. Critical path lineare.

#### Phase 1a

#### T010 Pydantic schema models
**Scope:** `relic/chronicle/schema.py` con `Event`, `Decision`, `StateSnapshot`, `ProvenanceEdge` + enums.  
**Inputs:** §6.6 di questo doc; `relic/persistence.py:PrivacyLevel`; `relic/control/consent.py:ConsentType`.  
**Outputs:** schema.py + enums.py.  
**Verification:** `pytest tests/chronicle/test_schema.py`.  
**Touched files:** `relic/chronicle/__init__.py`, `schema.py`, `enums.py`, `tests/chronicle/test_schema.py`.  
**Dependencies:** T004, **T002** (hard blocker — determina import path per PrivacyLevel).

#### T011 Context module (trace_id propagation)
**Scope:** `relic/chronicle/context.py` con `contextvars` per `trace_id`, `run_id`, `session_id`, `span_id`. API: `get_trace_id`, `new_trace_id`, `set_trace_id`, `register_session`, `register_run`, `register_experiment`, `get_traceparent`, `make_traceparent`.  
**Outputs:** `context.py` + test.  
**Verification:** test propagation cross-coroutine, isolation tra contextvars set su thread diversi.  
**Touched files:** `context.py`, `tests/chronicle/test_context.py`.  
**Dependencies:** T004 (può girare parallelo a T010, no import da schema.py).

#### T016 Test infrastructure (conftest + fixtures + helpers) **[NEW]**
**Scope:** scaffolding test reusabile per Phase 1b-6.  
**Files:**
- `tests/chronicle/conftest.py`: fixture `tmp_relic_db` (tempdir + migrations applicate), `tmp_chronicle_dir` (JSONL journal path), `clean_contextvars` (reset trace_id/run_id per test), `seed_subject` (consent records + sample subject), `mock_clock` (freezegun wrap).
- `tests/chronicle/fixtures/sample_events.py`: factory `make_event(event_type, **overrides) -> Event` per ridurre boilerplate.
- `tests/chronicle/fixtures/sample_traces.jsonl`: 50 eventi sintetici realistici (1 trace cron + LLM + memory + delivery completo) per regression test.
- `tests/chronicle/_base.py`: `ChronicleTestCase` base con setUp/tearDown comuni (db init, cleanup files, contextvar reset).  

**Verification:** `pytest tests/chronicle/test_schema.py` (T010) usa già `tmp_relic_db` fixture e passa.  
**Touched files:** 4 nuovi file test infra.  
**Dependencies:** T004, T010.  

**Perché esiste:** senza questo, ogni test T020+ riscrive setup db/contextvar (~30 LoC boilerplate × 20 test = 600 LoC duplicato). Coverage target 85% diventa irrealistico se ogni test costa 2x tempo per setup. T016 ammortizza tutto.

#### Phase 1b

#### T012 Redaction module
**Scope:** `relic/chronicle/redaction.py` con `SECRET_PATTERNS`, `contains_secret`, `redact_payload`. Riusa `detect-secrets` lib se già dep Relic; altrimenti regex inline.  
**Verification:** test con 5+ pattern types (API keys, bearer tokens, private keys).  
**Touched files:** `redaction.py`, `tests/chronicle/test_redaction.py`.  
**Dependencies:** T010, T016.

#### T013 Consent gate
**Scope:** `relic/chronicle/consent_gate.py` con `is_capture_allowed(consent_basis, subject_id)`. Chiama `ConsentManager.check_consent`.  
**Verification:** test su tutti gli scenari di §8.2.  
**Touched files:** `consent_gate.py`, `tests/chronicle/test_consent_gate.py`.  
**Dependencies:** T011, T016, conoscenza `relic/control/consent.py`.

#### T014 Emitter (dual SQLite + JSONL)
**Scope:** `relic/chronicle/emitter.py` con `emit_event`, `emit_decision`, `emit_snapshot`, `emit_provenance_edge`. Dual-write SQLite (via `relic.db.get_connection`) + JSONL (`~/.relic/chronicle/journal/YYYY-MM-DD.jsonl`). Chiama `consent_gate.is_capture_allowed` + `redaction.contains_secret`.  
**Verification:** test dual-write determinismo, fail-open (se SQLite fail, JSONL deve essere scritto comunque), divergence recovery (vedi §9.bis).  
**Touched files:** `emitter.py`, `exporters/sqlite.py`, `exporters/jsonl.py`, `tests/chronicle/test_emitter.py`.  
**Dependencies:** T012, T013, T016.

#### T015 Public API `__init__.py`
**Scope:** esporre `emit_event`, `emit_decision`, `emit_snapshot`, `emit_provenance_edge`, `start_span`, context helpers. Tutti `try/except` wrapped.  
**Verification:** `from relic.chronicle import emit_event` funziona; nessun import circolare con altri moduli Relic.  
**Touched files:** `relic/chronicle/__init__.py`.  
**Dependencies:** T014.

### Phase 2 — Background services (snapshots, provenance, reaper)

#### T020 Snapshot capture module
**Scope:** `relic/chronicle/snapshots.py` con `capture_snapshot(snapshot_type, scope_ref, content, ...)`. Compute `content_hash` + diff vs `previous_snapshot_id`. Store blob in filesystem.  
**Verification:** test su profile snapshot fittizio, diff calcolato per `added/removed/changed`.  
**Touched files:** `snapshots.py`, `tests/chronicle/test_snapshots.py`.  
**Dependencies:** T014.

#### T021 Provenance module
**Scope:** `relic/chronicle/provenance.py` con `add_edge`, `get_ancestors(artifact_id, depth=N)`, `get_descendants(artifact_id, depth=N)`. PROV-O relation enum.  
**Verification:** test grafo a 3 livelli, `--depth` rispettato.  
**Touched files:** `provenance.py`, `tests/chronicle/test_provenance.py`.  
**Dependencies:** T014.

#### T022 Reaper module
**Scope:** `relic/chronicle/retention.py` con `Reaper.run(dry_run=False, policy=None)`. Cancella `chronicle_events` con `retention_policy` expired; cascading su snapshot/provenance/thinking.  
**Verification:** test su seed dati, dry-run conta correttamente, real run azzera.  
**Touched files:** `retention.py`, `tests/chronicle/test_retention.py`.  
**Dependencies:** T014, T020, T021.

#### T023 Access audit module
**Scope:** `relic/chronicle/access_audit.py` con `log_access(accessor_id, access_kind, target_filter, result)`. Insert in `chronicle_access_log`.  
**Verification:** test su query → row attesa, result_hash deterministico.  
**Touched files:** `access_audit.py`, `tests/chronicle/test_access_audit.py`.  
**Dependencies:** T014.

#### T024 Legacy JSONL adapter
**Scope:** `relic/chronicle/adapters/legacy_jsonl.py` con `migrate_decision_events`, `migrate_cac_trace`, `migrate_privacy_trace`, `migrate_escalation_log`, `migrate_bootstrap_session`, `migrate_profile_edit_log`, `migrate_delivery_decision_log`. Idempotente (skip se event con stesso `(timestamp, source_module, payload_hash)` esiste).  
**Verification:** test con fixture JSONL → conta righe migrate.  
**Touched files:** `adapters/legacy_jsonl.py`, `tests/chronicle/test_legacy_jsonl_adapter.py`.  
**Dependencies:** T014.

### Phase 3 — Runtime integration (incremental, one module at a time)

Ognuno di questi task **modifica un singolo file Relic** per emettere events Chronicle. **Fail-open obbligatorio**. **Mai modificare logica di business**. Pattern di import:

```python
try:
    from relic.chronicle import emit_event, emit_decision, emit_snapshot, start_span, get_trace_id, new_trace_id
    _CHRONICLE = True
except Exception:
    _CHRONICLE = False
```

Task elenco:

| Task | File | Events emessi |
|------|------|--------------|
| T031 | `relic/gumi_plugin/cron_wiring.py` | `cron_fired`, `cron_drift`, decision `cron_evaluator` per gate, `cron_decision` event aggregato |
| T032 | `relic/gumi/llm_narrator.py` | `model_called`, `model_returned` con tokens_per_second |
| T033 | `relic/hermes_plugin/memory_provider.py` | `memory_read` (prefetch), `memory_write` (sync_turn) |
| T034 | `relic/hermes_plugin/hooks.py` | `hook_invoked`, `hook_returned` per ogni hook |
| T035 | `relic/cac/controller.py` | `memory_admission` decision + `cac_scoring_breakdown` event |
| T036 | `relic/hermes_runtime.py:DeliveryGate` | `delivery_decision` decision + `message_sent` event |
| T037 | `relic/hermes_plugin/soul_loader.py` | `system_message_loaded` event |
| T038 | `relic/hermes_plugin/tool_permissions.py` | `tool_permission_check` decision; integrato con `tool_called` di `commands.py` |
| T039 | `relic/hermes_plugin/commands.py` | `tool_called`, `tool_returned`, `command_invoked` |
| T040 | `relic/hermes_plugin/fail_safe.py` | `fallback_triggered` event |
| T041 | `relic/hermes_plugin/resume_hooks.py` | `session_resumed` event |
| T042 | `relic/correction/propagation.py` | `correction_applied` event (collega `derived_artifacts_updated`) |
| T043 | `relic/control/incident.py` | `incident_opened`, `incident_status_changed`, `artifact_quarantined` events |
| T044 | `relic/control/consent.py` | `consent_changed` event |
| T045 | `relic/profile/registry.py` | `profile_read`, `profile_write_attempted/applied/rejected` events + snapshot trigger before/after |
| T046 | `relic/profile/bootstrap_tui.py` | `bootstrap_step_state_change` events |
| T047 | `relic/profile/inferred_fields.py`, `system_inference.py` | `profile_inference` decision (con evidence_refs) |
| T048 | `relic/eval/harness.py` | `eval_run_started`, `eval_case_executed`, `eval_metric_computed` (genera `experiment_id`) |
| T049 | `relic/memory_dynamics/decay.py`, `reinforcement.py`, `consolidation.py` | `memory_decay`, `memory_reinforcement`, `memory_consolidation` events (gated by volume threshold) |
| T050 | `relic/gumi_continuity/events.py` | `continuity_marker_lifecycle` events |
| T051 | `relic/gumi_memory/providers/*.py` | `external_memory_call` events (provider, latency, response_hash) |
| T052 | `relic/gumi_plugin/critic.py` | `critic_decision` decision (action: pass/modify/block + rationale ≤280) |
| T053 | `relic/gumi_plugin/checkin_media_dispatcher.py` | `media_dispatch_decision` decision |
| T054 | `relic/gumi_plugin/{tts,image_gen,lyria}.py` | `media_generated` events |
| T055 | `relic/gumi_plugin/memory_sync.py` | `memory_sync_event` |
| T056 | `relic/checkin/scheduler.py`, `question_engine.py`, `facet_updater.py` | `checkin_*` events |
| T057 | `relic/compiler/passes.py`, `pipeline.py` | `compiler_pass_executed` events |
| T058 | `relic/context_pack/builder.py` | `context_pack_built` event |
| T059 | `relic/safety/escalation_notifier.py` | `safety_escalation` event |
| T060 | `relic/artifacts/registry.py:register` | `artifact_registered` event + auto-add provenance edges da `lineage_refs` |

Ogni task T03x-T06x ha **stesso shape**:
- Read file target.
- Identifica entry/exit points della funzione/metodo.
- Aggiungi import block (try/except).
- Wrappa con `start_span` o emetti event diretti.
- Aggiungi 1+ test di integrazione in `tests/chronicle/`.
- Verifica nessuna regressione (run test suite esistente del modulo).

### Phase 4 — Inspection tools

#### T070 Reader module
**Scope:** `relic/chronicle/reader.py` con `query_events`, `query_decisions`, `query_snapshots`, `join_trace`. Tutte le funzioni interrogano via `relic.db`.  
**Verification:** test query con filtri composti.  
**Touched files:** `reader.py`, test.  
**Dependencies:** T014.

#### T071 CLI scaffold + `chronicle query`
**Scope:** `relic/chronicle/cli/main.py` (argparse top-level) + `cli/query.py`. Output JSON/JSONL/table.  
**Verification:** `chronicle query --trace X --format json` parses correttamente.  
**Touched files:** `cli/main.py`, `cli/query.py`, `tests/chronicle/test_cli_query.py`.  
**Dependencies:** T070, T023.

#### T072 `chronicle timeline`
**Touched files:** `cli/timeline.py`, test.  
**Dependencies:** T071.

#### T073 `chronicle decision`, `chronicle snapshot`
**Touched files:** `cli/decision.py`, `cli/snapshot.py`, test.  
**Dependencies:** T071.

#### T074 `chronicle provenance`
**Touched files:** `cli/provenance.py`, test.  
**Dependencies:** T071, T021.

#### T075 `chronicle stats`
**Touched files:** `cli/stats.py`, test.  
**Dependencies:** T071.

#### T076 `chronicle export` (cascade integration)
**Scope:** integra `ExportManager` + aggiunge sezioni chronicle.  
**Touched files:** `cli/export_cmd.py`, test.  
**Dependencies:** T071, conoscenza `relic/control/export.py`.

#### T077 `chronicle delete` (cascade integration)
**Touched files:** `cli/delete_cmd.py`, test.  
**Dependencies:** T071, T076, conoscenza `relic/control/delete.py`.

#### T078 `chronicle reaper`
**Touched files:** `cli/reaper.py`, test.  
**Dependencies:** T071, T022.

#### T079 `chronicle replay`
**Touched files:** `cli/replay_cmd.py`, `chronicle/replay.py`, test.  
**Dependencies:** T071, T020.

#### T080 `chronicle report --html`
**Scope:** singolo file HTML generato da Jinja2 template, include timeline + provenance graph (Graphviz SVG inline).  
**Touched files:** `cli/report_html.py`, template, test.  
**Dependencies:** T071-T079.

#### T081 Acceptance test suite
**Scope:** `tests/chronicle/test_acceptance.py` con 23 asserzioni `research.md` §16.  
**Touched files:** test.  
**Dependencies:** T080.

### Phase 5 — Optional / scaling

#### T090 OTLP adapter
**Touched files:** `exporters/otlp.py`, test.  
**Dependencies:** T014.

#### T091 OTel semconv mapper
**Touched files:** `adapters/otel_semconv.py`, test.  
**Dependencies:** T032.

#### T092 ECS exporter (opt)
**Touched files:** `adapters/ecs.py`, test.  
**Dependencies:** T070.

#### T093 PROV-O JSON-LD exporter (opt)
**Touched files:** `adapters/prov_o.py`, test.  
**Dependencies:** T021.

#### T094 DuckDB Parquet analytics tier
**Touched files:** `exporters/parquet.py`, test.  
**Dependencies:** T014.

#### T095 Docker compose Phoenix profile
**Touched files:** `docker-compose.yml` (additivo, profile `chronicle`).  
**Dependencies:** T090.

#### T096 TruLens consumer (opt)
**Scope:** background job che legge `eval_metric_computed` e calcola feedback functions.  
**Touched files:** `chronicle/feedback_consumer.py`, test.  
**Dependencies:** T048.

### Phase 6 — Governance (must, parallel a 4)

#### T100 Researcher-only mode (`forensic` capability)
**Touched files:** `chronicle/researcher_mode.py`, env var doc.  
**Dependencies:** T015.

#### T101 Encryption at-rest (S1+ snapshots, thinking files)
**Touched files:** `chronicle/encryption.py`, test.  
**Dependencies:** T020.

#### T102 OTLP whitelist enforcement
**Touched files:** `exporters/otlp.py` (regex check).  
**Dependencies:** T090.

#### T103 End-to-end deletion cascade test
**Touched files:** `tests/chronicle/test_e2e_deletion.py`.  
**Dependencies:** T077, T100, T101.

#### T104 Documentation
**Touched files:** `docs/chronicle/USAGE.md`, `docs/chronicle/GOVERNANCE.md`, `docs/chronicle/SCHEMAS.md`.  
**Dependencies:** T081.

---

## 17. Implementation order (critical path)

```
Phase 0  spike   : T001 ∥ T003 → T004                  [4-8h, validates assumption]
Phase 0  gate    : run migrations, verify schema visible, verify imports
Phase 0  finish  : T002 (HARD BLOCKER su T010)         [≤ 1 giorno]
Phase 1a parallel: T010 ∥ T011 ∥ T016                  [parallel-safe post T002+T004]
Phase 1b lineare : T012 → T013 → T014 → T015           [critical path]
Phase 2  parallel: T020 ∥ T021 ∥ T022 ∥ T023 ∥ T024    [post T015]
Phase 3  ordered : T031 → T032 → T033 → T035 → T036 → T045 → T060
                   (poi T034, T037-T044, T046-T059 qualunque ordine)
Phase 4  ordered : T070 → T071 → T072 ∥ T073 ∥ T074 ∥ T075 → T076 → T077 → T078 → T079 → T080 → T081
Phase 5  optional: T090-T096 post acceptance
Phase 6  parallel: T100-T104 paralleli a Phase 4
```

**Hard prerequisites (gate enforced):**
- T002 blocca T010 (decisione PrivacyLevel canonico prima di import nel schema).
- Spike gate (post T004) blocca tutto Phase 1: se SQL migration non applicabili, STOP.
- T016 blocca tutti i test Phase 1b+ (no boilerplate proliferation).
- T014 blocca Phase 2-3 (no event emission senza emitter).
- T015 blocca integration runtime (no API public).
- T070 blocca CLI (no read senza reader).
- T077 blocca acceptance T081 (delete cascade must work).
- T100-T101 devono passare prima release Phase 6.

**Rollback safety:** se Phase 1b (T012-T015) incontra blockers dopo settimane di lavoro, Phase 1a (schema + context + test infra) resta isolata e riusabile. Refactor del solo emitter non invalida 1a.

---

## 18. Constraints for coding agents

### 18.1 What agents MUST do

- Leggere §3 (areas to inspect first) prima di qualunque modifica.
- Verificare l'esistenza di funzioni/file con `Read`/`Glob`/`Bash ls` PRIMA di chiamarli.
- Usare `relic.artifacts.checksums.compute_checksum` per ogni hash, mai `hashlib.sha256(...).hexdigest()` inline.
- Importare via `try/except` in moduli runtime (fail-open).
- Wrappare `emit_event/emit_decision/emit_snapshot` calls in `try/except Exception` quando dentro path runtime critico.
- Aggiungere test per ogni nuovo modulo + per ogni integration in Phase 3.
- Run `pytest tests/chronicle/` localmente prima di commit.
- Mantenere `mypy` clean su `relic/chronicle/`.
- Documentare break-changes in `docs/chronicle/CHANGELOG.md`.
- Riusare enum esistenti: `PrivacyLevel`, `ConsentType`, `ConsentScope`, `CorrectionType`, `IncidentSeverity`, `IncidentStatus`, `ArtifactType`.

### 18.2 What agents MUST NOT invent

- **Nuovi DB**: tutto va via `relic/db/` con migration numerate.
- **Nuovo hashing**: usa `relic.artifacts.checksums`.
- **Nuovi enum sensitivity**: usa `PrivacyLevel`.
- **Nuovi consent type**: usa `ConsentType`.
- **Nuovi delete/export manager**: usa `DeleteManager` / `ExportManager`.
- **Nuovi privacy gateway**: i privacy decision sono già in `relic/privacy/`; Chronicle li *mirror-a* in events.
- **Nuove tabelle** non documentate qui (parlane prima in un nuovo task design).
- **Nuovi field** in event schema senza schema_version bump.
- **Schema serialization custom** (use Pydantic `model_dump_json(sort_keys=True)` consistently).

### 18.3 What agents MUST NOT modify without evidence

- **`relic/control/{consent,delete,export,incident}.py`**: solo extension non-breaking (aggiungere metodo, non rimuovere). PR review umana obbligatoria.
- **`relic/artifacts/types.py`, `registry.py`, `checksums.py`**: zero modifiche senza ADR scritto.
- **`relic/db/migrations/` esistenti**: mai modificare migration già applicata.
- **`relic/persistence.py`**: solo aggiungere alias `PrivacyLevelAlias = PrivacyLevel` se serve, mai cambiare enum values.
- **`relic/correction/propagation.py`**: aggiungere `emit_event` calls è ok; cambiare logica `apply_correction` no.
- **`relic/gumi_plugin/cron_wiring.py:_evaluate_decision`** logica gate: ordine e behavior immutabili.

### 18.4 Quando chiedere prima di agire

Se un task richiede:

- Modifica di un file ≥ 200 LoC fuori dallo scope `relic/chronicle/`.
- Cambio di firma di funzione pubblica.
- Rimozione di codice (anche se deprecated).
- Aggiunta di dipendenza Python non già in `requirements*.txt`.
- Modifica `pyproject.toml` o `setup.py`.

→ NON eseguire. Documenta come open question in PR description e chiedi review umana.

### 18.5 PR / commit hygiene

- Un task = un PR. Mai bundle T031 + T032 in stesso PR.
- Commit message stile Conventional Commits: `feat(chronicle): emit cron_fired events (T031)`.
- Branch naming: `chronicle/T0NN-short-desc`.
- PR description deve elencare: task ID, file toccati, test aggiunti, acceptance criteria coperti.

---

## 19. Definition of done (per task)

Un task è "done" quando:

1. ✅ Tutti i file dichiarati in "Touched files" esistono e contengono il codice atteso.
2. ✅ I test dichiarati passano: `pytest tests/chronicle/test_<feature>.py -v`.
3. ✅ Linter pulito: `ruff check relic/chronicle/`.
4. ✅ Type check pulito: `mypy relic/chronicle/<file>.py`.
5. ✅ Nessuna regressione nelle test suite esistenti: `pytest tests/ -k "not chronicle"`.
6. ✅ Per integration tasks (Phase 3): emit event verificato manualmente con `chronicle query --since 5m` post-esecuzione.
7. ✅ PR description rispetta §18.5.

Un task è "blocked" quando:

- ❌ Una dipendenza dichiarata non è ancora done.
- ❌ Un assumption del task design risulta falso (es. file path non esiste): aprire issue con dettaglio.
- ❌ Test failure non risolvibile senza modificare codice fuori scope dichiarato.

In tutti i casi blocked: **non workaround**. Documentare e fermarsi.

---

## 20. Glossario rapido

- **trace_id**: UUID del trace distribuito (cross-process).
- **run_id**: UUID di una invocazione pipeline (cron fire, eval run, bootstrap).
- **session_id**: UUID di una conversazione utente-agente.
- **event**: fatto avvenuto, atomico, immutabile.
- **decision**: scelta presa, con input/alternatives/evidence/rationale.
- **snapshot**: fotografia di state a un istante, con chaining `previous_snapshot_id`.
- **provenance edge**: arco grafo PROV-O tra entità (event/snapshot/artifact) e artifact derivato.
- **sensitivity**: `PrivacyLevel` (SAFE/S2/S1/S0).
- **consent_basis**: `ConsentType` (MEMORY_STORAGE/ANALYTICS/ROLEPLAY/DATA_SHARING).
- **retention_policy**: `RetentionPolicy` enum.
- **capture-time consent**: gate prima di scrivere, non dopo.
- **fail-open**: errore nel tracer non blocca path principale.
- **dual-write**: SQLite + JSONL mirror per resilienza.
- **researcher mode**: capability che apre S1+ inspection (audit-logged).
- **forensic mode**: massimo livello, raw thinking, secret detector off (USE ISOLATED).
- **legacy JSONL**: i 7 file pre-Chronicle, mantenuti in dual-write per 3 release.

---

## 21. Riferimenti incrociati

- `docs/chronicle/legacy/research_v1_scaffold.md` — scaffold ricerca iniziale (OTel + Phoenix + Langfuse).
- `docs/chronicle/legacy/agentic_dev_v1_scaffold.md` — scaffold plan iniziale (14 step).
- `docs/chronicle/research.md` — research esteso (questo è il companion).
- `docs/chronicle/INVENTORY.md` — (da scrivere in T001) mappa moduli Relic.
- `docs/chronicle/PRIVACY_TRACE_RECONCILIATION.md` — (T002) decisione su unificazione `PrivacyTrace`.
- `docs/chronicle/USAGE.md` — (T104) esempi CLI.
- `docs/chronicle/GOVERNANCE.md` — (T104) policy retention/consent/audit.
- `docs/chronicle/SCHEMAS.md` — (T104) full schema reference.
- `docs/chronicle/CHANGELOG.md` — (continuous) bump schema_version + breaking changes.
