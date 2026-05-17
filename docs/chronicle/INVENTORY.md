# Chronicle — Repository Inventory

**Data:** 2026-05-16  
**Stato:** T001 output — mappa completa dell'infrastruttura preesistente Relic.  
**Usare come:** reference per tutti i task Chronicle (T0xx). Ogni modulo elencato deve essere consultato prima di toccare codice.

---

## Convenzioni usate in questo documento

| Simbolo | Significato |
|---------|-------------|
| ✅ | riusato da Chronicle senza modifica |
| 🔗 | integrato via import (dipendenza obbligata) |
| ⚠️ | conflitto o gap documentato — azione richiesta |
| ❌ | non usare — fuori scope |

---

## 1. Database e migrations

### 1.1 Moduli core

| File | Ruolo | Integrazione Chronicle |
|------|-------|----------------------|
| `relic/db/__init__.py` | `get_connection()`, `init_db()` — connessione SQLite unica | ✅ source-of-truth per tutte le tabelle Chronicle |
| `relic/db/loader.py` | migration runner (`[0-9]*.sql` in ordine numerico) | ✅ Chronicle aggiunge `0003_chronicle_events.sql` etc. |
| `relic/db/migrations/0001_initial.sql` | tabelle base: prompts, corrections, artifacts, consent_records, schema_versions | 🔗 riferimento per struttura colonne + naming conventions |
| `relic/db/migrations/0002_control_incident.sql` | tabelle control: incidents, quarantined_artifacts, incidents_audit | 🔗 riferimento per naming + pattern FK |

**Nota:** solo 2 migration esistenti. Prossimo numero libero: `0003`.

### 1.2 Schema models

| File | Classi/Enum | Integrazione Chronicle |
|------|-------------|----------------------|
| `relic/schemas.py` | `LineageMixin` (lineage_id, created_at, updated_at), `PromptRecord`, `CorrectionRecord`, `ArtifactRecord`, `ConsentRecord`, `SchemaVersion` | 🔗 `LineageMixin` è il pattern base per i record Chronicle; `schema_version` già definito |
| `relic/artifacts/types.py` | `ArtifactType` (enum), `SchemaVersion`, `SourceSnapshotRef`, `LineageRef`, `CorrectionCutoff`, `Artifact`, `RuntimeProfilePack`, `AgentEmbodimentPack`, `InteractionPolicyPack` | 🔗 `ArtifactType` usato per provenance; `Artifact.can_emit()` enforcement; `lineage_refs` per provenance edges |
| `relic/artifacts/registry.py` | `ArtifactRegistry` — register/get/get_descendants/verify_integrity | ✅ event `artifact_registered` emesso quando registry.register() viene chiamato |
| `relic/artifacts/checksums.py` | `compute_checksum`, `verify_checksum`, `hash_prompt`, `hash_hint`, `compute_structural_checksum`, `compute_delta_checksum` | 🔗 **usare SEMPRE queste per hash — mai hashlib inline** |

### 1.3 Compiler lineage

| File | Ruolo | Integrazione Chronicle |
|------|-------|----------------------|
| `relic/compiler/lineage.py` | `ArtifactLineage` (artifact_id, source_snapshot_id, checksum, parent_lineage_refs), `LineageTracker.register/verify/get_all` | 🔗 provenance Chronicle si appoggia a `LineageTracker` per artefatti tracciati; archi per eventi/decisioni non-artefatti gestiti separatamente |

---

## 2. Governance (consent, delete, export, incident, privacy)

### 2.1 Enum reutilizzabili

| Enum | Definito in | Valori | Chronicle field |
|------|-------------|--------|----------------|
| `PrivacyLevel` | `relic/persistence.py:26` | `S0_HARD_VIOLATION`, `S1_QUARANTINE`, `S2_WARNING`, `SAFE` | `event.sensitivity` |
| `ConsentType` | `relic/control/consent.py:14` | `MEMORY_STORAGE`, `ANALYTICS`, `ROLEPLAY`, `DATA_SHARING` | `event.consent_basis` |
| `ConsentScope` | `relic/control/consent.py` | `SESSION`, `SESSION_WITHIN_APP`, `PERMANENT` | — |
| `IncidentSeverity` | `relic/control/incident.py:20` | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` | `event.severity` |
| `IncidentStatus` | `relic/control/incident.py:28` | `OPEN`, `INVESTIGATING`, `QUARANTINED`, `RESOLVED`, `FALSE_POSITIVE` | — |
| `ArtifactType` | `relic/artifacts/types.py:28` | `RUNTIME_PROFILE`, `ENGAGEMENT_SNAPSHOT`, `MEMORY_SNAPSHOT`, `CONTEXT_PACK`, `REPLICATION_BUNDLE`, `CORRECTION_TRACE`, `ORTHOGRAPHIC_RULES`, `CONTENT_ANALYSIS`, `SELF_ANALYSIS`, `SYSTEM_INFERENCE` | provenance target type |
| `CorrectionType` | `relic/correction/propagation.py:23` | `CONTENT_UPDATE`, `DELETION`, `REDACTION`, `PRIVACY_UPGRADE`, `FACTUAL_CORRECTION`, `FIRST_CORRECTION` | `correction_applied` event payload |

### 2.2 Manager reuse

| Manager | File | Metodi critici | Integrazione Chronicle |
|---------|------|----------------|----------------------|
| `ConsentManager` | `relic/control/consent.py` | `check_consent(consent_type, session_id)`, `record_consent()`, `get_active_consents()` | 🔗 `chronicle/consent_gate.py` chiama `check_consent` capture-time |
| `DeleteManager` | `relic/control/delete.py` | `dry_run(scope, target_id)`, `delete(scope, target_id)` | 🔗 `chronicle/cli/delete_cmd.py` chiama `DeleteManager` + cleanup tabelle Chronicle |
| `ExportManager` | `relic/control/export.py` | `export(output_path, options)`, `ExportFormat`, `ExportOptions.redact_content` | 🔗 `chronicle/cli/export_cmd.py` aggiunge JSONL eventi al bundle |
| `IncidentReporter` | `relic/control/incident.py` | `create()`, `update()`, `quarantine()`, `resolve()` | 🔗 `chronicle` emette `incident_opened` / `incident_status_changed` events |

### 2.3 Privacy — ⚠️ CONFLITTO CRITICO

**Due `PrivacyTrace` con schemi divergenti.**

#### Opzione A — `relic/privacy/trace.py` (PR04 legacy)

```python
@dataclass
class PrivacyTrace:
    decision_id: str
    decision: str              # label testuale della decisione
    category: str | None       # categoria di contenuto
    confidence: float          # 0..1
    redacted: bool
    rehydration_blocked: bool
    final_output_blocked: bool
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, str]
```

Persisted via `write_trace()` → JSONL (append-only). Schema minimalista, orientato privacy gateway decisions.

#### Opzione B — `relic/persistence.py:PrivacyTrace` (inline)

```python
class PrivacyTrace:
    trace_id: str
    stage: str                    # e.g., "input_scan", "rehydration", "output_gate"
    content_hash: str             # SHA-256 del contenuto originale
    privacy_level: PrivacyLevel   # S0/S1/S2/SAFE
    policy_applied: str
    timestamp: datetime
    rehydration_context: dict | None
```

Usato da `MemoryPersistence.store()` come audit trail di ogni block. Schema più strutturato, orientato memory blocks.

#### Conflitto

| Aspetto | Opzione A (privacy/trace.py) | Opzione B (persistence.py) |
|---------|------------------------------|----------------------------|
| Namespace | `relic.privacy` | `relic.persistence` |
| Design | dataclass | Pydantic |
| Campi privacy_level | ❌ assente | ✅ `PrivacyLevel` enum |
| Campi trace_id | ✅ | ✅ |
| Campi content_hash | ❌ assente | ✅ |
| Campi rehydration_blocked | ✅ | ❌ assente |
| Campi stage | ❌ assente | ✅ |
| Persistenza | JSONL (`write_trace()`) | `MemoryPersistence` DB |

#### Azione richiesta

T002 (PrivacyTrace reconciliation proposal) deve decidere:
1. Quale è il source-of-truth canonico.
2. Se serve un modulo unificato (`relic/privacy_core/`) o alias.
3. Come deprecare il perdente senza rompere chi già importa.

**Chronicle non deve creare un terzo `PrivacyTrace`.** Deve importare da quello canonico. T002 risolve.

---

## 3. Runtime e flussi dati

### 3.1 Hermes runtime

| File | Ruolo | Eventi da catturare |
|------|-------|---------------------|
| `relic/hermes_runtime.py` | Runtime principale, message routing, session management | `message_received`, `message_sent` |
| `relic/hermes_plugin/hooks.py` | Hook dispatcher (pre/post processi) | `hook_invoked` |
| `relic/hermes_plugin/soul_loader.py` | SOUL.md loading | `system_message_loaded` |
| `relic/hermes_plugin/tool_permissions.py` | Tool permission check | `tool_permission_check` |
| `relic/hermes_plugin/commands.py` | Command registration/execution | `command_invoked` |
| `relic/hermes_plugin/memory_provider.py` | Memory prefetch/sync | `memory_read`, `memory_write` |
| `relic/hermes_plugin/fail_safe.py` | Fallback logic | `fallback_triggered` |

### 3.2 Gumi — LLM e generazione

| File | Ruolo | Eventi da catturare |
|------|-------|---------------------|
| `relic/gumi/llm_narrator.py` | `_call_llm()` — entry point LLM | `model_called`, `model_returned` |
| `relic/gumi/personalization.py` | Prompt assembly | — |
| `relic/gumi/background_generator.py` | Background generation | — |

### 3.3 Gumi plugin — cron, decisioni, media

| File | Ruolo | Eventi/Decisioni |
|------|-------|-----------------|
| `relic/gumi_plugin/cron_wiring.py` | `_evaluate_decision`, `emit_decision_event`, `make_decision` — **CRITICAL** gate decisions | `cron_decision` (decision), `cron_fired` (event), `checkin_accepted`, `checkin_skipped`, `delivery_decision` |
| `relic/gumi_plugin/critic.py` | Critic agent decision | `critic_decision` (decision) |
| `relic/gumi_plugin/memory_sync.py` | Memory sync ops | `memory_sync_event` |
| `relic/gumi_plugin/tts.py`, `image_gen.py`, `lyria.py` | Media generation | `media_generated` |
| `relic/gumi_plugin/checkin_media_dispatcher.py` | Media dispatch decision | `media_dispatch_decision` |

### 3.4 Gumi continuity e memory

| File | Ruolo | Eventi |
|------|-------|--------|
| `relic/gumi_continuity/events.py` | Continuity marker lifecycle | `continuity_marker_lifecycle` |
| `relic/gumi_continuity/admission.py` | Marker admission decision | — |
| `relic/gumi_memory/providers/*.py` | External memory provider calls | `external_memory_call` |

### 3.5 Memory dynamics

| File | Ruolo | Eventi |
|------|-------|--------|
| `relic/memory_dynamics/decay.py` | Memory decay | `memory_decay` |
| `relic/memory_dynamics/reinforcement.py` | Memory reinforcement | `memory_reinforcement` |
| `relic/memory_dynamics/consolidation.py` | Memory consolidation | `memory_consolidation` |
| `relic/memory_dynamics/service.py` | Orchestratore dynamics | — |

---

## 4. Profile e bootstrap

| File | Ruolo | Eventi |
|------|-------|--------|
| `relic/profile/registry.py` | Profile read/write + `profile_edit_log.jsonl` | `profile_read`, `profile_write_attempted`, `profile_write_applied`, `profile_write_rejected` |
| `relic/profile/bootstrap_tui.py` | Bootstrap step machine + `bootstrap_session.jsonl` | `bootstrap_step_state_change` |
| `relic/profile/inferred_fields.py`, `relic/profile/system_inference.py` | Profile inference decisions | `profile_inference` (decision) |

---

## 5. CAC e safety

| File | Ruolo | Eventi |
|------|-------|--------|
| `relic/cac/controller.py` | Admission evaluate | `admission_evaluated` |
| `relic/cac/trace.py` | `CACTraceWriter` → `cac_trace.jsonl` | `cac_trace_recorded` |
| `relic/safety/escalation_notifier.py` | Safety escalation | `safety_escalation` |

---

## 6. Eval e lab

| File | Ruolo | Eventi |
|------|-------|--------|
| `relic/eval/harness.py` | Eval pipeline entry (genera `experiment_id`) | `eval_run_started`, `eval_case_executed`, `eval_metric_computed` |
| `relic/eval/replication_bundle.py` | Bundle creation | — |

---

## 7. Compiler e context pack

| File | Ruolo | Eventi |
|------|-------|--------|
| `relic/compiler/passes.py`, `relic/compiler/pipeline.py` | Compiler passes | `compiler_pass_executed` |
| `relic/context_pack/builder.py` | Context pack building | `context_pack_built` |

---

## 8. Correction e replication

| File | Ruolo | Eventi |
|------|-------|--------|
| `relic/correction/propagation.py` | `CorrectionPropagator`, `CorrectionEvent`, `CorrectionTrace`, `CorrectionType` | `correction_applied` |
| `relic/replication/bundle.py` | Bundle creation/loading | — |

---

## 9. Checkin

| File | Ruolo | Eventi |
|------|-------|--------|
| `relic/checkin/scheduler.py` | Checkin scheduling | `checkin_scheduled` |
| `relic/checkin/question_engine.py` | Question generation | — |
| `relic/checkin/facet_updater.py` | Facet updates | — |
| `relic/checkin/anti_repeat.py` | Anti-repeat logic | — |

---

## 10. Legacy JSONL files (7 totali)

Questi esistono già e Chronicle deve integrarli (dual-write + migration).

| File | Producer | Schema | Chronicle integration |
|------|----------|--------|---------------------|
| `~/.relic/decision_events.jsonl` | `gumi_plugin/cron_wiring.py` | v1 (decision + timestamp + action + confidence + rationale + rejected) | T024 — `migrate_decision_events()` |
| `~/.relic/cac_trace.jsonl` | `cac/trace.py` | v1 (prompt_hash + admission + score + profile_ref) | T024 — `migrate_cac_trace()` |
| `~/.relic/privacy_trace.jsonl` | `privacy/trace.py` (Opzione A) | v1 (decision_id + decision + category + confidence + redacted + blocked flags) | T024 — `migrate_privacy_trace()` |
| `~/.relic/escalation_log.jsonl` | `safety/escalation_notifier.py` | v1 (incident_id + severity + subject_id + action) | T024 — `migrate_escalation_log()` |
| `~/.relic/subjects/<id>/bootstrap_session.jsonl` | `profile/bootstrap_tui.py` | v1 (step + state + timestamp) | T024 — `migrate_bootstrap_session()` |
| `~/.relic/subjects/<id>/profile_edit_log.jsonl` | `profile/registry.py` | v1 (before_hash + after_hash + trigger + outcome) | T024 — `migrate_profile_edit_log()` |
| `~/.relic/subjects/<id>/delivery_decision_log.jsonl` | `gumi_plugin/cron_wiring.py` | v1 (delivery_decision + rationale) | T024 — `migrate_delivery_decision_log()` |

**Importante:** `privacy_trace.jsonl` usa l'Opzione A (dataclass in `privacy/trace.py`). Dopo T002, il migration adapter deve adattarsi al canonico scelto.

---

## 11. Directory structure di riferimento

```
relic/
├── db/                         ✅ SQLite unico, migration runner
│   ├── __init__.py
│   ├── loader.py
│   └── migrations/
│       ├── 0001_initial.sql
│       └── 0002_control_incident.sql
├── schemas.py                  ✅ LineageMixin
├── persistence.py              ✅ PrivacyLevel + Opzione B PrivacyTrace ⚠️
├── privacy/
│   ├── trace.py                ⚠️ Opzione A PrivacyTrace (conflitto)
│   ├── gateway.py
│   ├── inference.py
│   ├── pii.py
│   └── policy.py
├── control/
│   ├── consent.py              ✅ ConsentManager, ConsentType
│   ├── delete.py               ✅ DeleteManager
│   ├── export.py               ✅ ExportManager
│   └── incident.py             ✅ IncidentReporter, IncidentSeverity, IncidentStatus
├── artifacts/
│   ├── types.py                ✅ ArtifactType, Artifact, LineageRef
│   ├── registry.py             ✅ ArtifactRegistry
│   └── checksums.py            ✅ compute_checksum (OBBLIGATORIO per hash)
├── compiler/lineage.py         ✅ ArtifactLineage, LineageTracker
├── correction/propagation.py   ✅ CorrectionPropagator, CorrectionType
├── cac/
│   ├── controller.py           ✅ CAC admission
│   ├── trace.py                → cac_trace.jsonl
│   └── types.py
├── safety/escalation_notifier.py → escalation_log.jsonl
├── gumi/
│   ├── llm_narrator.py         ✅ _call_llm (entry LLM instrumentato)
│   └── ...
├── gumi_plugin/
│   ├── cron_wiring.py          ✅ _evaluate_decision (decision gate CRITICO)
│   ├── critic.py
│   └── ...
├── gumi_continuity/
│   └── events.py
├── gumi_memory/providers/
├── hermes_plugin/
│   ├── hooks.py                ✅ hook dispatcher
│   ├── soul_loader.py         → system_message_loaded
│   ├── tool_permissions.py    → tool_permission_check
│   ├── commands.py             → command_invoked
│   ├── memory_provider.py     → memory_read/memory_write
│   └── fail_safe.py
├── profile/
│   ├── registry.py             → profile_edit_log.jsonl
│   ├── bootstrap_tui.py        → bootstrap_session.jsonl
│   └── inferred_fields.py
├── memory_dynamics/
│   ├── decay.py
│   ├── reinforcement.py
│   └── consolidation.py
├── eval/harness.py             ✅ eval pipeline (experiment_id)
├── checkin/
├── compiler/
├── context_pack/
├── replication/
├── ui/
├── vault/
├── lab/
└── patterns/
```

---

## 12. Dipendenze enum — dove sono definiti (source of truth)

```
PrivacyLevel          → relic/persistence.py:26
ConsentType           → relic/control/consent.py:14
ConsentScope          → relic/control/consent.py
IncidentSeverity      → relic/control/incident.py:20
IncidentStatus        → relic/control/incident.py:28
ArtifactType          → relic/artifacts/types.py:28
CorrectionType        → relic/correction/propagation.py:23

PrivacyTrace (A)      → relic/privacy/trace.py:10  ⚠️ CONFLITTO
PrivacyTrace (B)      → relic/persistence.py        ⚠️ CONFLITTO
```

**Chronicle non definisce proprie copie di questi enum.** Importa sempre da qui.

---

## 13. Vincoli per ogni task T0xx

Prima di toccare un file, l'agente deve:
1. ✅ Verificare che il file esiste (Read/Glob/Bash ls).
2. ✅ Verificare che la funzione/classe target esiste e che la firma non è cambiata dall'ultima volta che questo documento è stato aggiornato.
3. ✅ Importare enum da `relic/persistence.py` (PrivacyLevel), `relic/control/consent.py` (ConsentType), etc. — mai definire copie locali.
4. ✅ Usare `relic.artifacts.checksums.compute_checksum` per ogni hash.
5. ✅ Importare `relic.db.get_connection` per accesso SQLite.
6. ❌ Non modificare nessun modulo elencato in questo documento senza task design separato e review umana.

---

## 14. Open questions (da risolvere in T002+)

1. **PrivacyTrace canonico**: Opzione A (`privacy/trace.py`) o Opzione B (`persistence.py`) o nuovo modulo unificato?
2. **JSONL legacy migration order**: i 7 file hanno formati diversi. Quale migrato per primo? Dipendenze tra loro?
3. **`cac_trace.jsonl` fields**: qual è lo schema esatto? Serve sample read per T024.
4. **`decision_events.jsonl` schema**: il piano dice v1 ma non ho letto il file. Serve sample per T024.
5. **Migration number**: `0003` è libero. Confirmare con `ls relic/db/migrations/`.

---

*Ultimo aggiornamento: 2026-05-16 (T001 spike)*
