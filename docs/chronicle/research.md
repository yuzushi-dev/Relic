# Chronicle — Research Document (extended pass)

**Data:** 2026-05-16  
**Stato:** documento di ricerca complementare a `docs/chronicle/legacy/research_v1_scaffold.md`. Non sostituisce il documento esistente: lo integra, ne corregge gap critici, e formalizza la separazione richiesta tra eventi, decisioni, snapshot di stato e artefatti derivati.

**Mandato:** progettare il livello di tracing/audit/inspection ("Chronicle per Relic") con riuso massimo di standard e infrastruttura già presente in Relic, evitando l'errore di ricostruire male ciò che esiste.

---

## 0. Indice

1. Scopo, scope, non-goal
2. Cosa Relic possiede già (mappatura completa dell'infrastruttura preesistente)
3. Critica del primo scaffold (`docs/chronicle/legacy/research_v1_scaffold.md` + `legacy/agentic_dev_v1_scaffold.md`)
4. Ricerca estesa: sistemi e standard non coperti dal primo scaffold
5. Modello canonico richiesto: eventi vs decisioni vs snapshot vs artefatti
6. Tassonomia eventi proposta
7. Identificatori e correlazione causale
8. Reasoning capture policy
9. Privacy, consenso, sicurezza, sensitivity, retention
10. Modello di storage: opzioni, raccomandazioni, migration path
11. Interoperabilità: cosa adottare, cosa rifiutare, cosa rimandare
12. Modello di ispezione (researcher UI / CLI)
13. Failure mode, rischi, mitigations
14. Open questions
15. Implementazione a fasi raccomandata
16. Acceptance criteria misurabili
17. Comparison table consolidata
18. Fonti

---

## 1. Scopo, scope, non-goal

### 1.1 Scopo

Costruire uno strato unico di osservabilità e audit per Relic + profili Hermes che permetta al ricercatore di:

- ricostruire qualunque sessione/run/decision in modo causale dal trace;
- ispezionare modello, tool, memoria, profilo, artefatti e flussi dati;
- esportare e cancellare per soggetto in conformità GDPR;
- distinguere tra **fatto avvenuto** (event), **scelta presa** (decision), **stato del mondo** (snapshot) e **output derivato** (artifact) con provenance verificabile;
- replicare l'esecuzione (replay) o almeno verificare la riproducibilità deterministica delle scelte.

### 1.2 Scope

**In scope:**
- runtime Relic (Python) e plugin Hermes;
- subsistemi: cron checkin, Hermes runtime, gumi LLM calls, CAC, profilo (bootstrap + editing), memoria (continuity, dynamics), privacy, safety, control (consent/delete/export/incident/pause), artifacts/registry/lineage, compiler, eval, correction;
- cattura locale-first (`~/.relic/chronicle/`) con opzionale export OTLP;
- API researcher-only di ispezione (CLI + UI minimale);
- governance (sensitivity labels, consent basis, retention, audit dell'audit).

**Out of scope (Phase 1):**
- distributed tracing multi-host (Relic è single-host local-first);
- archiviazione cloud cross-region;
- modelli ML di anomaly detection sul trace (può venire dopo come consumer);
- replay deterministico dei modelli (LLM non deterministici by design — si conserva il prompt_hash e i parametri, non si richiama).

### 1.3 Non-goal

- **Non** sostituire `relic/control/{consent,delete,export,incident}.py`: Chronicle li *riusa* come backend di policy, non li riscrive.
- **Non** sostituire `relic/artifacts/registry.py`: Chronicle vi *fa riferimento* per la provenance, non duplica.
- **Non** sostituire `relic/db/` (SQLite + migrations): Chronicle vi *aggiunge* tabelle eventi/spans, non crea un secondo DB scollegato.
- **Non** loggare contenuto raw di prompt, risposte LLM, messaggi utente, marker memoria.
- **Non** introdurre un vendor SaaS hard-coded.
- **Non** costruire una UI prima di aver stabilizzato lo schema eventi.

---

## 2. Inventario dell'infrastruttura preesistente in Relic

Il primo scaffold (`docs/chronicle/legacy/research_v1_scaffold.md`) elenca solo 7 file JSONL silos. La realtà del repo è molto più ricca. **Chronicle DEVE integrarsi con questa infrastruttura**, perché duplicare crea drift e violazioni di consent/delete contracts.

### 2.1 Modello dati e persistenza

| Modulo | Cosa fornisce | Implicazione per Chronicle |
|--------|---------------|---------------------------|
| `relic/db/__init__.py` + `db/loader.py` + `db/migrations/` | SQLite singolo con migrations versionate, `get_connection()`, `init_db()` | Chronicle aggiunge tabelle `chronicle_events`, `chronicle_decisions`, `chronicle_state_snapshots`, `chronicle_provenance_edges` come migration ordinata; nessun DB secondario. |
| `relic/schemas.py` | Pydantic models: `LineageMixin`, `PromptRecord`, `CorrectionRecord`, `ArtifactRecord`, `ConsentRecord`, `SchemaVersion` | Chronicle riusa `LineageMixin` per i propri record. `schema_version` già definito → Chronicle lo eredita per `schema_version` su eventi. |
| `relic/artifacts/types.py` | `ArtifactType`, `SchemaVersion`, `SourceSnapshotRef`, `LineageRef`, `CorrectionCutoff`, `Artifact`, `RuntimeProfilePack`, `AgentEmbodimentPack`, `InteractionPolicyPack` con `can_emit()` enforcement | Gli artefatti derivati Chronicle (snapshot di traccia, report engagement) sono `Artifact` validi, con `lineage_refs` che puntano agli eventi sorgente. |
| `relic/artifacts/registry.py` | `ArtifactRegistry` con index per type / lineage, `verify_integrity()` via checksum | Chronicle non gestisce artefatti propri: emette `ArtifactCreatedEvent` quando il registry registra qualcosa. |
| `relic/artifacts/checksums.py` | `compute_checksum`, `verify_checksum`, `hash_prompt`, `hash_hint`, `compute_structural_checksum`, `compute_delta_checksum` | Chronicle usa **queste funzioni** per tutti gli hash; nessuna implementazione hash separata. |
| `relic/compiler/lineage.py` | `ArtifactLineage` (artifact_id, source_snapshot_id, checksum, parent_lineage_refs), `LineageTracker.register/verify/get_all` | La provenance Chronicle si appoggia a `LineageTracker` per gli artefatti già tracciati; Chronicle aggiunge solo gli archi per eventi/decisioni che non sono artefatti. |

### 2.2 Governance

| Modulo | Cosa fornisce | Integrazione Chronicle |
|--------|---------------|----------------------|
| `relic/control/consent.py` | `ConsentManager`, `ConsentType` (MEMORY_STORAGE, ANALYTICS, ROLEPLAY, DATA_SHARING), `ConsentScope` (SESSION, SESSION_WITHIN_APP, PERMANENT), `consent_records` table | Ogni evento Chronicle ha `consent_basis` = `ConsentType` valore. Capture-time enforcement: se `check_consent` ritorna `False` per `ANALYTICS`, l'evento è scartato (o catturato in livello degradato — vedi §9). |
| `relic/control/delete.py` | `DeleteManager.dry_run/delete`, `DeleteScope` (PROMPT, SESSION, ALL), cascading invalidation di replication bundles ed eval cases | `chronicle delete --subject X` chiama `DeleteManager.delete(SESSION, target_id)` e in più cancella tutti i record `chronicle_events` con `subject_id=X`. Cascade nei `chronicle_provenance_edges`. |
| `relic/control/export.py` | `ExportManager` con `ExportFormat` (JSON/JSONL/Markdown), `ExportOptions.redact_content` | `chronicle export --subject X` aggiunge sezioni `chronicle_events`, `chronicle_decisions`, `chronicle_state_snapshots` allo stesso bundle export, con stessa policy di redaction. |
| `relic/control/incident.py` | `IncidentReporter`, `IncidentSeverity` (LOW/MEDIUM/HIGH/CRITICAL), `IncidentStatus` (OPEN/INVESTIGATING/QUARANTINED/RESOLVED/FALSE_POSITIVE), `QuarantinedArtifact` | Chronicle emette `incident_created` event quando l'IncidentReporter crea un incident. Quando un artefatto è quarantined, gli eventi correlati ottengono tag `quarantined_by=incident_id`. |
| `relic/control/pause.py` | flow di pausa subject | Eventi `subject_paused_*` (già visti nel cron_wiring gates). |
| `relic/correction/propagation.py` | `CorrectionPropagator`, `CorrectionEvent`, `CorrectionTrace`, `CorrectionType` (CONTENT_UPDATE / DELETION / REDACTION / PRIVACY_UPGRADE / FACTUAL_CORRECTION / FIRST_CORRECTION) | Chronicle registra `correction_applied` event per ogni `CorrectionEvent` con riferimento a `prompt_id` e `derived_artifacts_updated`. |
| `relic/privacy/trace.py` | `PrivacyTrace` (decision_id, decision, category, confidence, redacted, rehydration_blocked, final_output_blocked) → `privacy_trace.jsonl` | **Conflitto schema**: esiste anche `PrivacyTrace` in `persistence.py` con campi diversi (stage, content_hash, privacy_level). Chronicle DEVE unificare: un solo schema canonical. Vedi §6.7. |
| `relic/persistence.py` | `MemoryPersistence`, `PrivacyLevel` (S0_HARD_VIOLATION, S1_QUARANTINE, S2_WARNING, SAFE), `MemoryBlock`, `PrivacyTrace` (duplicato) | `PrivacyLevel` è il sensitivity label canonico per Chronicle. Vedi §9.2. |

### 2.3 Runtime e flussi

| Modulo | Funzione chiave | Da catturare in Chronicle |
|--------|----------------|--------------------------|
| `relic/gumi_plugin/cron_wiring.py` | `_evaluate_decision()`, `emit_decision_event()`, `make_decision()` → `decision_events.jsonl` | Già coperto dallo scaffold: gate timing, decision, reason_codes. **Aggiungere**: `decision_record` (vedi §5) — `selected_action` + `rejected_alternatives` per ogni gate fail. |
| `relic/gumi/llm_narrator.py` | `_call_llm()` Ollama HTTP | Coperto scaffold. **Aggiungere**: routing decisions (quale modello e perché). |
| `relic/hermes_plugin/memory_provider.py` | `prefetch()`, `sync_turn()` | Coperto scaffold. **Mancante**: distinzione tra memoria di tipo `marker continuity` (relic/gumi_continuity) e `dynamics` (relic/memory_dynamics) — schema unificato `memory_op` con `subtype`. |
| `relic/hermes_plugin/hooks.py` | dispatch hook `pre_llm_call`, `transform_llm_output` | Coperto scaffold. |
| `relic/hermes_plugin/soul_loader.py` | caricamento SOUL.md profilo | **Non coperto**: emettere `system_message_loaded` event con `soul_md_hash`, `profile_id`, `size_bytes`. |
| `relic/hermes_plugin/tool_permissions.py` | permission per tool calls Hermes | **Non coperto**: `tool_call_authorized` / `tool_call_denied` decision record. |
| `relic/hermes_plugin/context_injection.py` | iniezione context | Coperto scaffold come hook. |
| `relic/hermes_plugin/fail_safe.py` | fallback su errori | **Non coperto**: `fallback_triggered` event con `original_error`, `fallback_strategy`. |
| `relic/hermes_plugin/resume_hooks.py` | resume conversazione | **Non coperto**: `session_resumed` event con `last_session_id`, `gap_h`. |
| `relic/hermes_plugin/commands.py` | comandi slash Hermes | **Non coperto**: `command_invoked` event con `command_name`, `args_hash`. |
| `relic/gumi_plugin/cron_schedule.py` + `cron_tasks.py` | scheduling | **Non coperto**: `cron_scheduled` / `cron_fired` con drift_ms. |
| `relic/gumi_plugin/anti_repeat.py` + `relic/checkin/anti_repeat.py` | de-dup checkin | **Non coperto**: `anti_repeat_block` decision record. |
| `relic/gumi_plugin/critic.py` | OutputCritic | **Non coperto**: emettere `critic_decision` decision record (action: pass/modify/block + rationale). |
| `relic/gumi_plugin/checkin_media_dispatcher.py` | dispatch text/voice/image | Parzialmente coperto. **Aggiungere**: `media_dispatch_decision` con `eligible_types`, `roll`, `selected`. |
| `relic/gumi_plugin/tts.py`, `image_gen.py`, `lyria.py` | generazione media | **Non coperto**: `media_generated` events con `model`, `duration`, `output_hash`, `size_bytes`. |
| `relic/gumi_plugin/memory_sync.py` | sync memoria gumi↔backend | **Non coperto**: `memory_sync_event`. |
| `relic/checkin/scheduler.py` + `question_engine.py` + `facet_updater.py` | checkin assistito | **Non coperto**: `checkin_question_asked`, `checkin_facet_updated` con field+old_value_hash+new_value_hash. |
| `relic/cac/controller.py` | `evaluate()` admission decision | Coperto scaffold come CACDecisionTrace. |
| `relic/cac/trace.py` | `CACTraceWriter` → `cac_trace.jsonl` | Esiste. Chronicle lo legge per migration / lo affianca per dual-write. |
| `relic/cac/scoring.py` | scoring | **Da aggiungere**: `cac_scoring_breakdown` come sotto-evento (numeric only). |
| `relic/profile/bootstrap_tui.py` | bootstrap step machine | Coperto scaffold come `profile_bootstrap`. **Aggiungere**: `bootstrap_step_state_change` con from_state/to_state. |
| `relic/profile/registry.py` | profile read/write, `profile_edit_log.jsonl`, `delivery_decision_log.jsonl` | **Critico**: questa è la fonte primaria per `profile_diff` events. Vedi §6.10. |
| `relic/profile/baseline_artifact.py` | snapshot baseline profilo | Emettere come `state_snapshot` (§5.3). |
| `relic/profile/projection.py` | proiezione profilo runtime | `profile_projection_event`. |
| `relic/profile/inferred_fields.py` | inferenza campi profilo | `profile_inference_event` (decision record con evidenza). |
| `relic/profile/system_inference.py` | inferenza sistema | `system_inference_event`. |
| `relic/profile/_bootstrap_steps/{boundaries,consent,delivery_config,first_contact_controls}.py` | step bootstrap | Eventi `bootstrap_step_completed` per ogni step. |
| `relic/memory_dynamics/{decay,reinforcement,consolidation,association,projection,service,store}.py` | dinamiche memoria | **Non coperto scaffold**: `memory_decay_event`, `memory_reinforcement_event`, `memory_consolidation_event` con before/after metrics. |
| `relic/gumi_continuity/{admission,recall,events,store}.py` | marker continuity | Coperto come `memory_operation`, ma con tipo `continuity_marker`. |
| `relic/gumi_memory/providers/{byterover,hindsight,holographic,honcho}.py` | provider memoria esterni | **Non coperto**: `external_memory_call` events (provider, latency, redacted payload). |
| `relic/safety/escalation_notifier.py` → `escalation_log.jsonl` | escalation safety | Esiste. Chronicle lo affianca emettendo `safety_escalation` event. |
| `relic/eval/{harness,debug_bundle,replication_bundle,gumi_roleplay_metrics,memory_dynamics,...}.py` | pipeline eval | **Non coperto**: `eval_run_started`, `eval_case_executed`, `eval_metric_computed`. Critico per evaluation event category. |
| `relic/patterns/{policy_compiler,runtime_pack_sanitizer,confidence_caps,signal_extractor}.py` | pattern compilation | `pattern_compiled` artifact event. |
| `relic/compiler/{passes,pipeline,report,replication}.py` | compiler passes | Ogni pass è un evento `compiler_pass_executed` con input_hash → output_hash. |
| `relic/replication/` | replication bundle generation | `replication_bundle_generated` artifact event. |
| `relic/context_pack/{builder,render,trace}.py` | context pack building | `context_pack_built` con `included_refs` (hash di ciascun fragment). |
| `relic/lab/{dataset_card,eval_contract,train_contract,validate_dataset,promote_blocked}.py` | lab contracts | Eventi `dataset_validated`, `train_contract_evaluated`. |
| `relic/vault/` | vault ops | `vault_unlocked`, `vault_template_used` events (extra-sensitive — see §9). |

### 2.4 File JSONL già emessi (silos da unificare)

Il primo scaffold li elenca correttamente. Per riferimento: `~/.relic/decision_events.jsonl`, `cac_trace.jsonl`, `privacy_trace.jsonl`, `escalation_log.jsonl`, `bootstrap_session.jsonl`, `profile_edit_log.jsonl`, `delivery_decision_log.jsonl`. **Strategia**: dual-write (mantenere i JSONL legacy per retrocompatibilità + mirror nell'event store unificato) per N versioni, poi rimpiazzare.

### 2.5 Conclusione §2

Il primo scaffold sottostima massicciamente l'infrastruttura. Chronicle deve:

1. Riusare `relic/db/` (migrations) come unico DB di backing.
2. Riusare `relic/artifacts/`, `relic/compiler/lineage.py` per provenance artefatti.
3. Riusare `relic/control/{consent,delete,export,incident,pause}.py` come backend policy.
4. Riusare `relic/correction/propagation.py` come fonte di correction events.
5. Riusare `relic/persistence.py:PrivacyLevel` come sensitivity enum.
6. Unificare i due `PrivacyTrace` (privacy/trace.py + persistence.py) in un solo schema.
7. Espandere copertura agli oltre 25 sottosistemi sopra elencati, non limitarsi ai 7 del primo scaffold.

---

## 3. Critica del primo scaffold

| Area | Cosa lo scaffold dice | Problema | Correzione richiesta |
|------|----------------------|----------|----------------------|
| **Storage** | JSONL primario + SQLite indice ricostruito + Phoenix OTLP | Ignora che `relic/db/` esiste già con migrations e tabelle artefatti/consent/incident | Una sola DB SQLite con migration nuove per `chronicle_*`. JSONL solo come append-only audit secondario (forensic backup), non come primario. |
| **Schema eventi** | 12+ tipi di span (CronDecisionTrace, LLMCallTrace, ...) | Mancano fattorizzazione comune e separazione event/decision/state/artifact | Un solo `chronicle_event` table con `event_category` enum. Decisioni in `chronicle_decision` table (può joinare events su `event_id`). |
| **Privacy** | "MAI contenuto raw, solo hash SHA-256" | Regola corretta ma non considera `PrivacyLevel` esistente né `consent_basis` per evento | Ogni evento ha `sensitivity` (= PrivacyLevel), `consent_basis` (= ConsentType), `retention_policy` (enum). |
| **Trace ID** | UUID4 generato in cron, propagato via stdout traceparent W3C | Manca distinzione tra `trace_id` (cross-process), `run_id` (singola invocazione di una pipeline), `session_id` (conversazione cross-run). Manca `experiment_id`. | Vedi §7 ID model. |
| **Reasoning** | `prompt_hash`, `response_hash` | Manca politica esplicita su raw chain-of-thought (thinking tokens del modello) | Vedi §8: thinking content è S1 di default; solo metriche (token count) loggate; raw thinking opt-in researcher-only. |
| **Decisioni** | Mescolate dentro span "decision" generici | Non separa input osservabili, alternative scartate, evidenza | Schema `DecisionRecord` esplicito §5.2. |
| **State snapshot** | Solo "profile diff" implicito | Manca uno snapshot store ricostruibile a un istante | Tabella `chronicle_state_snapshots` §5.3. |
| **Artifact provenance** | Cita lineage_refs ma non spiega come Chronicle vi attinge | `compiler/lineage.py` esiste, va riusato | §5.4. |
| **Governance** | Sezione privacy generica | Manca retention, deletion-by-subject, audit dell'audit, researcher-only mode | §9 completo. |
| **Replay** | Non menzionato | User-requirement: ricostruzione causale di un run | §12 + §15 fase 4. |
| **Eval events** | Non menzionato | Modulo `relic/eval/` produce metriche che vanno tracciate | §6.13. |
| **Tool calls** | Generico "tool call" | Manca `tool_permissions.py` integrazione | §6.5 più dettagliato. |
| **OWASP / sicurezza** | Non menzionato | LLM apps hanno OWASP Top 10 (LLM01-LLM10) e ASI Top 10 (2026) | §9.7. |
| **Standard provenance** | Cita gen_ai.* OTel | Manca W3C PROV-O, OpenLineage che sono lo standard de-jure per data lineage | §4.1, §4.2. |
| **Auditing l'auditor** | Non menzionato | Chi accede al trace? Quando? Va loggato. | §9.6. |

---

## 4. Ricerca estesa: sistemi e standard non coperti

### 4.1 W3C PROV-O (Provenance Ontology) — standard de jure

Standard W3C 2013 (recommendation), tre classi core: `prov:Entity`, `prov:Activity`, `prov:Agent`; sette relazioni: `wasGeneratedBy`, `used`, `wasInformedBy`, `wasDerivedFrom`, `wasAssociatedWith`, `wasAttributedTo`, `actedOnBehalfOf`.

**Mappatura su Chronicle:**
- `Entity` = artifact (Relic `Artifact`), state snapshot, raw event payload.
- `Activity` = event (model_call, tool_call, memory_op, decision).
- `Agent` = subject_id, agent_id (hermes/gumi), system module.
- Le 7 relazioni si esprimono come righe in `chronicle_provenance_edges` con `relation_type` enum.

**Pro:** vocabolario stabile, interoperabile, serializzabile in JSON-LD/Turtle, espone l'audit a tool RDF/SPARQL.  
**Contro:** verbosity RDF, non-targettato per LLM-specific (no slot per token/temperature).  
**Decisione Relic:** adottare il **modello concettuale** PROV-O (Entity/Activity/Agent/relations) come spina dorsale dell'event taxonomy, ma serializzare in JSON nativo + colonne SQL. Esportatori opzionali PROV-JSON per chi vuole leggere in tool RDF.

### 4.2 OpenLineage + Marquez

OpenLineage (LF AI & Data) è uno standard per metadati di run/job/dataset, focus pipeline dati (Airflow, Spark, dbt). Marquez è la reference implementation (server + UI).

**Concetti:**
- `Job` = unità di lavoro (es. cron_decision pipeline, profile_bootstrap step).
- `Run` = esecuzione di un job (analogo run_id Chronicle).
- `Dataset` = input/output del job (analogo artifact / state snapshot Chronicle).
- Eventi: START, COMPLETE, FAIL, ABORT.
- Facets: estensioni tipizzate (es. `SchemaDatasetFacet`, `ColumnLineageDatasetFacet`).

**Pro:** schema JSON consolidato, server (Marquez) self-hostable, integra con OTel.  
**Contro:** orientato ETL/dati, non agentic; "dataset" non è naturale per messaggio singolo.  
**Decisione Relic:** **adattare** il pattern Job/Run/Dataset come **modello logico** per i workflow Relic (cron_checkin, profile_bootstrap, eval_harness, compiler_pipeline). Non adottare Marquez come backend; eventualmente esporre un esportatore OpenLineage opzionale.

### 4.3 Event Sourcing (ESAA e pattern classici)

ESAA (Event Sourcing for Autonomous Agents, arxiv 2602.23193 — 2026): agenti emettono **intenzioni strutturate** (validated JSON), un orchestratore deterministico le valida e persiste in `activity.jsonl` append-only, poi le proietta in una materialized view verificabile via hash (`esaa verify`).

**Pattern classici (Greg Young, Vaughn Vernon):**
- Append-only event log = source of truth.
- State è una **proiezione** ricostruita dagli eventi.
- Snapshots periodici per evitare di rigiocare l'intero log.
- CQRS: separa il write model (commands → events) dal read model (proiezioni).

**Pro per Relic:**
- Replay perfetto della pipeline non-LLM (decision gates, gate timing, memory ops): basta rigiocare eventi.
- Audit forense intrinseco.
- Hermes profile state può essere ricostruito dagli eventi di `profile_edit_log.jsonl`.

**Contro per Relic:**
- LLM calls non sono deterministici: non si possono "rieseguire" allo stesso modo. Conserviamo `prompt_hash`, `response_hash`, parametri, ma il replay è solo dello *stato*, non della risposta.
- Eventi crescono nel tempo → compaction / snapshot strategy serve.

**Decisione Relic:** event-sourcing-lite. Tutti gli stati derivati che si possono ricostruire (engagement aggregates, profile state, memory state) sono **proiezioni** dell'event store. Snapshot in `chronicle_state_snapshots` ogni N eventi o ogni cambio di major version del modello.

### 4.4 OCSF (Open Cybersecurity Schema Framework)

OCSF 1.x (Splunk + AWS + ~150 vendor) standardizza event class per security telemetry. Classi rilevanti per Chronicle:
- `Audit Activity` (6003) — comandi privilegiati, login, modifiche policy.
- `Account Change` (3001) — modifiche identità.
- `Compliance Finding` (2003) — violazioni policy.
- `Detection Finding` (2004) — alert security.

**Decisione Relic:** **non adottare OCSF come schema nativo** (è security-centric, overkill). Ma riusare i nomi delle categorie: `audit_activity` per Chronicle-access events; `compliance_finding` per privacy gate failures. Mapping documentato per future esportazione SIEM.

### 4.5 Elastic Common Schema (ECS)

ECS 8.x è uno schema flat (`event.action`, `event.outcome`, `user.id`, `host.name`, ...) maturo per log/metrics/security. Mantenuto da Elastic. ECS è esplicitamente compatibile con OpenTelemetry resource semantic conventions.

**Decisione Relic:** ECS è un eccellente *export target* (ELK stack adoption). Mantenere internamente schema Chronicle e fornire un convertitore `chronicle → ECS JSON` opzionale.

### 4.6 OWASP LLM Top 10 (2026) + ASI (Agent Security Initiative) Top 10

LLM01-LLM10: Prompt Injection, Sensitive Info Disclosure, Supply Chain, Data/Model Poisoning, Improper Output Handling, Excessive Agency, System Prompt Leakage, Vector/Embedding Weaknesses, Misinformation, Unbounded Consumption.

ASI Top 10 (2026, agenti): aggiunge T1 Agent Authorization Hijacking, T2 Memory Poisoning, T3 Multi-Agent Coordination Attack, T4 Tool Misuse, T5 Identity Confusion, ecc.

**Implicazione per Chronicle:** ogni evento deve permettere di rispondere alle domande OWASP:
- `tool_call` → input/output hash + permission_check_result (LLM06, T4).
- `memory_write` → admission decision (LLM03, T2).
- `agent_decision` → identity confirmation (T1, T5).
- `model_call` → `unbounded_consumption` flag se token > soglia (LLM10).

### 4.7 MLflow Tracing v3.0 (2026)

MLflow 3.0 ha aggiunto `mlflow.tracing` (auto-instrumentazione OpenAI/Anthropic/LangChain/LlamaIndex), formato `Trace` con spans/inputs/outputs/attributes; UI integrata in MLflow Tracking server.

**Pro:** se Relic già usa MLflow per experiment tracking, l'integrazione è naturale.  
**Contro:** Relic NON usa MLflow attualmente (verifica: nessun import in `relic/eval/`). Aggiungere MLflow significa portarlo come dipendenza pesante (server Tracking + backend store). Per local-first è eccessivo.  
**Decisione:** non adottare MLflow. Eventualmente come *adapter export*.

### 4.8 W&B Weave

Trace tree per LLM apps, integrato con W&B experiment tracking, **closed-source backend** (W&B Cloud o on-prem enterprise). API Python open. Forte UX ma cloud-bound.

**Decisione:** escluso (non self-hostable senza enterprise contract).

### 4.9 TruLens

Open source Snowflake-backed. Focus: feedback functions per valutare app LLM (groundedness, relevance, harmfulness). Memorizza app traces in SQLite locale (`leaderboard.sqlite`).

**Pro:** local-first, libreria pura Python, free.  
**Contro:** feedback functions sono prescritti e generano LLM calls aggiuntive (costo). Trace data model proprietario (`Record`).  
**Decisione:** considerare TruLens come **consumer** di trace Chronicle per la fase Eval (calcolare feedback su trace già catturati), non come backend di tracing.

### 4.10 Helicone

Proxy LLM (intercetta richieste HTTP a OpenAI/Anthropic, le logga). Self-hostable via Docker Compose (Postgres + ClickHouse + worker).

**Pro:** integration costo zero (cambio base URL).  
**Contro:** stack pesante (ClickHouse), proxy aggiunge latenza, non vede operazioni interne (memoria, profilo, decisioni).  
**Decisione:** escluso. Hermes non passa per un proxy HTTP esterno (Ollama è locale), e i tracing point critici sono **interni** non al confine HTTP.

### 4.11 ClickHouse / ClickStack

ClickHouse columnar, compressione 5-10x vs row-store, native OTLP exporter (collector → CH), UI ClickStack (2026) per logs/metrics/traces.

**Pro:** scalabilità eccezionale (miliardi di span/giorno).  
**Contro:** dipendenza server-side complessa, overkill per single-host Relic.  
**Decisione:** **non adottare in fase 1**. Documentare come path di migrazione per fase 5+ se il volume cresce (es. Relic multi-soggetto, ore di trace al giorno).

### 4.12 DuckDB + ducklake/duckdb-otlp

DuckDB è embedded analytics SQL (come SQLite ma columnar). `duckdb-otlp` (smithclay) legge OTLP files con schema ClickHouse-compatible.

**Pro:** zero server, file-based, query SQL columnar veloce su Parquet, schema OTel-aligned.  
**Contro:** non append-friendly come SQLite (richiede compaction); meno maturo come backend OTLP.  
**Decisione Relic:** **valido path intermedio** tra SQLite (fase 1) e ClickHouse (fase 5). Aggiungere come opzione `chronicle analytics` in fase 4 che genera Parquet rolling da JSONL e li interroga via DuckDB.

### 4.13 Open Source ADR / Decision Record patterns

Architectural Decision Records (Michael Nygard, 2011): markdown file template per record decisioni umane. Per Chronicle non si tratta di decisioni umane ma di decisioni runtime → però **lo schema ADR ispira** la struttura del `DecisionRecord`:
- Context (input osservabili)
- Decision (azione selezionata)
- Alternatives considered (alternative scartate)
- Consequences (output osservabili)
- Status (validated/superseded)

Vedi §5.2.

### 4.14 Phoenix evals (Arize) + DeepEval + RAGAS

Framework per valutazione automatica LLM output (hallucination, retrieval relevance, answer correctness). Producono `evaluation event` con punteggio numerico.

**Decisione:** evaluation events sono una **categoria nativa** Chronicle (§6.13). Phoenix/DeepEval possono essere adapter opzionali in fase 5 che leggono trace Chronicle e producono eval events.

### 4.15 GDPR + right to be forgotten — implicazioni operative

- Art. 17 (right to erasure): deve essere possibile cancellare tutti i dati di un soggetto entro 30 giorni. Per Chronicle: `chronicle delete --subject X` deve essere atomico e cascading.
- Art. 30 (record of processing): mantiene registro processing — il consent_basis su ogni evento serve esattamente a questo.
- Art. 5(1)(c) data minimization: solo dati necessari → giustifica policy "hash, mai raw".
- EU AI Act (effettivo 2026-08-02 per high-risk): DPIA, logging "appropriate" delle operazioni AI → Chronicle È quel logging.

**Decisione:** Chronicle nasce GDPR-aligned. `consent_basis`, `retention_policy`, `subject_deletion_cascade` sono first-class.

---

## 5. Modello canonico: separazione event / decision / state / artifact

Il task richiede esplicitamente di separare questi quattro tipi. Lo scaffold li mischia.

### 5.1 Raw event (`chronicle_event`)

Fatto avvenuto, atomico, immutabile. Esempi:
- `message_received` (utente → sistema)
- `model_called` / `model_returned`
- `tool_called` / `tool_returned`
- `memory_read` / `memory_write`
- `profile_read` / `profile_write_attempted`
- `error_raised`
- `retry_started`
- `fallback_triggered`
- `cron_fired`
- `hook_invoked`
- `consent_changed`
- `incident_opened`
- `correction_applied`

Schema base in §6.

### 5.2 Decision record (`chronicle_decision`)

Scelta presa da agente o regola. Distinta dall'evento perché esprime *perché* qualcosa è successo, non solo *che* è successo. Ogni `chronicle_decision` è collegato a uno o più `chronicle_event` (input/output).

```jsonc
{
  "decision_id": "uuid",
  "trace_id": "...",
  "run_id": "...",
  "actor_type": "agent|rule|user|system",
  "actor_id": "hermes|cron_evaluator|...",
  "decision_kind": "tool_selection|memory_admission|profile_update|delivery|hypothesis_selection|consent_check|...",
  "selected_action": {            // azione scelta, redatta
    "action_type": "...",
    "action_ref": "..."
  },
  "rejected_alternatives": [      // opzionale, quando disponibile
    {"action_type": "...", "action_ref": "...", "reason_rejected": "..."}
  ],
  "observable_inputs": {          // input osservabili (hash o numerici)
    "input_event_ids": ["..."],
    "feature_vector_hash": "sha256:...",
    "policy_version": "..."
  },
  "observable_outputs": {
    "output_event_ids": ["..."],
    "result_hash": "sha256:..."
  },
  "confidence": 0.87,             // 0..1 opzionale
  "uncertainty_notes": "...",     // short string
  "evidence_refs": ["event_id", "snapshot_id", "artifact_id"],
  "rationale_summary": "short text, no raw CoT",  // ≤ 280 char
  "consent_basis": "ANALYTICS",
  "sensitivity": "SAFE|S2|S1|S0",
  "validation_status": "pending|validated|superseded|disputed",
  "timestamp": "iso8601",
  "schema_version": "chronicle-decision/v1"
}
```

`rationale_summary` è **human-readable summary**, non chain-of-thought. Limite caratteri stretto. Non contiene contenuto sensibile o PII.

### 5.3 State snapshot (`chronicle_state_snapshot`)

Fotografia immutabile di uno stato del mondo a un istante. Permette ricostruzione retroattiva e diff. Esempi:

- `hermes_profile_state` (intero profilo Hermes a t)
- `memory_state` per namespace (lista marker attivi)
- `experiment_config` (config a inizio run)
- `agent_config` (config plugin a inizio sessione)
- `consent_state` (set consensi attivi per subject a t)

```jsonc
{
  "snapshot_id": "uuid",
  "snapshot_type": "hermes_profile|memory_namespace|experiment_config|agent_config|consent_state|...",
  "subject_id": "...",
  "scope_ref": "gumi-daniele",       // namespace/profile_id specifico
  "captured_at": "iso8601",
  "trigger_event_id": "...",         // evento che ha causato lo snapshot (es. profile_write_attempted)
  "previous_snapshot_id": "...",     // catena temporale per diff
  "content_hash": "sha256:...",      // hash del contenuto serializzato canonical
  "content_ref": "ref-to-relic-artifact-id-or-blob",  // dove leggere il contenuto raw (registry, blob store, redacted)
  "content_size_bytes": 4521,
  "diff_from_previous": {            // opzionale, calcolato
    "added_fields": ["..."],
    "removed_fields": ["..."],
    "changed_fields": [{"field": "...", "old_hash": "...", "new_hash": "..."}]
  },
  "consent_basis": "...",
  "sensitivity": "...",
  "retention_policy": "...",
  "schema_version": "chronicle-snapshot/v1"
}
```

Trigger di snapshot:
- ogni `profile_write` riuscita.
- ogni `consent_changed`.
- ogni `experiment_run_started`.
- snapshot periodico (1/giorno) per memoria namespace come baseline.

Storage: contenuto canonical serializzato in `~/.relic/chronicle/snapshots/{snapshot_id}.json` se < 1MB, altrimenti referenziato all'`ArtifactRegistry`. Riferimento, non duplicazione.

### 5.4 Derived artifact (`chronicle_artifact_provenance`)

Per artefatti generati (report, profile summary, portrait, eval output, JSON/Markdown export, transformed dataset) Relic ha già `Artifact` + `lineage_refs`. Chronicle aggiunge un **grafo di provenance** che lega artifact → eventi/snapshot/altri artifact che vi hanno contribuito.

```jsonc
{
  "provenance_edge_id": "uuid",
  "artifact_id": "uuid",     // FK relic artifact registry
  "from_node": {"node_type": "event|snapshot|artifact", "node_id": "..."},
  "to_node": {"node_type": "artifact", "node_id": "<artifact_id>"},
  "relation": "used|wasGeneratedBy|wasDerivedFrom|wasInformedBy",  // PROV-O vocab
  "contribution_role": "input|template|policy|filter|enricher",
  "weight": 1.0,             // se quantificabile
  "created_at": "iso8601"
}
```

L'`ArtifactRegistry` esistente emette un evento `artifact_registered` quando viene chiamato `register()`; Chronicle ascolta e genera gli edge a partire da `lineage_refs` + dal `trace_id` context attivo (eventi recenti dello stesso run).

---

## 6. Event taxonomy proposta

Schema base unico per tutti gli eventi. Subtype-specific fields nel JSON `payload`.

### 6.0 Common envelope

```jsonc
{
  "event_id": "uuid",
  "event_type": "stringa snake_case",       // es. "model_called", "memory_read"
  "event_category": "message|model|tool|memory|profile|decision|artifact|safety|privacy|consent|admin|eval|background|error|state_snapshot|provenance",
  "trace_id": "uuid",
  "run_id": "uuid",
  "session_id": "uuid|null",
  "parent_event_id": "uuid|null",
  "experiment_id": "uuid|null",
  "subject_id": "string|null",        // pseudonimo, mai PII
  "agent_id": "string|null",          // es. "hermes", "gumi"
  "profile_id": "string|null",        // hermes profile id
  "hermes_profile_id": "string|null", // alias quando differiscono
  "actor_type": "user|agent|system|rule|cron|external",
  "actor_id": "string|null",
  "source_module": "string",          // es. "relic.gumi_plugin.cron_wiring"
  "target_module": "string|null",
  "timestamp": "iso8601-with-microseconds",
  "duration_ms": "float|null",
  "input_refs": ["event_id|snapshot_id|artifact_id"],
  "output_refs": ["event_id|snapshot_id|artifact_id"],
  "payload_redacted": false,
  "payload_hash": "sha256:hex16",
  "payload": {},                      // schema dipende da event_type
  "sensitivity": "SAFE|S2|S1|S0",     // = relic.persistence.PrivacyLevel
  "visibility": "researcher|admin|subject_export",
  "consent_basis": "MEMORY_STORAGE|ANALYTICS|ROLEPLAY|DATA_SHARING|null",
  "retention_policy": "ephemeral|short_30d|standard_365d|extended_research|legal_hold",
  "tags": ["key:value"],
  "severity": "debug|info|warn|error|critical",
  "validation_status": "pending|validated|superseded|disputed|null",
  "error_code": "string|null",
  "retry_count": 0,
  "schema_version": "chronicle-event/v1"
}
```

**Note schema:**
- `payload_hash` calcolato su `payload` canonical JSON (sort_keys) per integrity. Riusa `relic.artifacts.checksums.compute_checksum`.
- `tags` è array di `"k:v"` strings (semplice grepping); evita JSON nested in colonne SQL.
- `event_category` è enum stretto per indicizzazione.
- `experiment_id` opzionale, popolato solo se l'evento avviene dentro un run di `relic/eval/harness.py`.

### 6.1 message_received / message_sent

```jsonc
"payload": {
  "platform": "telegram|discord|web|cli",
  "direction": "inbound|outbound",
  "media_type": "text|voice|image|video|sticker",
  "message_length_chars": 87,
  "message_length_seconds": null,    // per audio/video
  "language_detected": "it|en|null",
  "is_proactive": false,             // true per cron-initiated outbound
  "content_hash": "sha256:..."       // riusa hash_prompt
}
```

### 6.2 model_called / model_returned

(Sostituisce `LLMCallTrace` dello scaffold; arricchito.)

```jsonc
"event_type": "model_called",
"payload": {
  "provider": "ollama|anthropic|openai|...",
  "model_id": "qwen3.5-plus",
  "model_version_hash": "sha256:...",   // hash di model file se locale
  "operation": "chat|generate|embedding",
  "stream": false,
  "params": {
    "temperature": 0.85,
    "max_tokens": 512,
    "top_p": 0.9,
    "stop_sequences_hash": "sha256:..."
  },
  "prompt_hash": "sha256:...",
  "prompt_length_chars": 3421,
  "prompt_message_count": 7,            // per chat
  "context_fill_ratio": 0.72,
  "tools_offered_hashes": ["sha256:..."],  // se tool calling
  "call_site": "gumi.llm_narrator.generate_soul_md",
  "routing_decision_id": "uuid"         // FK a chronicle_decision se routing dinamico
}
```

```jsonc
"event_type": "model_returned",
"parent_event_id": "<model_called event_id>",
"payload": {
  "finish_reason": "stop|length|tool_calls|safety",
  "response_hash": "sha256:...",
  "response_length_chars": 142,
  "usage": {
    "input_tokens": 1847,
    "output_tokens": 63,
    "thinking_tokens": 0,
    "cache_read_input_tokens": 0,
    "cache_creation_input_tokens": 0,
    "tokens_per_second": 28.4
  },
  "time_to_first_token_ms": null,
  "total_duration_ms": 2218.5,
  "tool_calls_requested_count": 0,
  "reasoning_present": false,
  "reasoning_capture": "none|metrics_only|redacted_summary|raw_researcher_only"
}
```

`reasoning_capture` enum determina cosa è stato fatto del thinking content (vedi §8).

### 6.3 tool_called / tool_returned

```jsonc
"event_type": "tool_called",
"payload": {
  "tool_name": "search_memory|generate_image|send_telegram|...",
  "tool_namespace": "hermes|gumi|external",
  "tool_version": "...",
  "args_hash": "sha256:...",
  "args_schema_hash": "sha256:...",
  "permission_decision_id": "uuid",  // FK a chronicle_decision (autorizzazione)
  "permission_outcome": "allowed|denied",
  "permission_reason": "..."
}
```

```jsonc
"event_type": "tool_returned",
"parent_event_id": "<tool_called event_id>",
"payload": {
  "outcome": "success|error|timeout|denied",
  "result_hash": "sha256:...",
  "result_size_bytes": 2048,
  "result_truncated": false,
  "error_class": "string|null"
}
```

### 6.4 memory_read / memory_write / memory_decay / memory_consolidation

```jsonc
"event_type": "memory_read",
"payload": {
  "memory_kind": "continuity_marker|memory_dynamics_node|external_provider|context_pack_fragment",
  "namespace": "gumi-daniele",
  "operation_subtype": "prefetch|recall|search|sync_turn|...",
  "query_hash": "sha256:...",
  "markers_requested": 20,
  "markers_returned": 5,
  "markers_admission_breakdown": {
    "admitted": 5,
    "blocked": 15,
    "block_reasons": {"ttl_expired": 8, "recall_limit_reached": 4, "paused": 2, "burden_exceeded": 1}
  },
  "provider_id": "hindsight|byterover|holographic|honcho|null",
  "provider_latency_ms": 23.0
}
```

```jsonc
"event_type": "memory_write",
"payload": {
  "memory_kind": "...",
  "namespace": "...",
  "operation_subtype": "store|reinforce|associate|sync_turn",
  "marker_hash": "sha256:...",
  "marker_size_chars": 142,
  "admission_decision_id": "uuid",    // FK a CAC decision
  "decay_score_before": null,
  "decay_score_after": null,
  "reinforcement_delta": null
}
```

```jsonc
"event_type": "memory_decay",
"payload": {
  "memory_kind": "memory_dynamics_node",
  "namespace": "...",
  "marker_hash": "sha256:...",
  "decay_function": "exponential|linear|...",
  "decay_score_before": 0.83,
  "decay_score_after": 0.71,
  "elapsed_h_since_last_recall": 48.2
}
```

```jsonc
"event_type": "memory_consolidation",
"payload": {
  "namespace": "...",
  "consolidation_strategy": "merge|prune|...",
  "input_marker_hashes": ["sha256:..."],
  "output_marker_hash": "sha256:...",
  "removed_count": 3,
  "added_count": 1
}
```

### 6.5 profile_read / profile_write_attempted / profile_write_applied / profile_write_rejected

```jsonc
"event_type": "profile_write_attempted",
"payload": {
  "profile_id": "gumi-daniele",
  "writer_module": "relic.profile.registry",
  "field_path": "preferences.communication_tone",
  "previous_value_hash": "sha256:...",
  "proposed_value_hash": "sha256:...",
  "inferred_by": "system_inference|user_explicit|bootstrap|correction",
  "evidence_event_ids": ["..."],
  "confidence": 0.78
}
```

```jsonc
"event_type": "profile_write_applied",
"parent_event_id": "<profile_write_attempted>",
"payload": {
  "profile_id": "...",
  "field_path": "...",
  "decision_id": "uuid",            // decisione di applicare
  "snapshot_before_id": "...",
  "snapshot_after_id": "...",
  "diff_summary": {"added": [], "removed": [], "changed": ["preferences.communication_tone"]}
}
```

```jsonc
"event_type": "profile_write_rejected",
"parent_event_id": "<profile_write_attempted>",
"payload": {
  "rejection_reason": "low_confidence|consent_missing|policy_block|conflict_with_existing",
  "rejected_by": "system_inference_policy|consent_gate|user"
}
```

### 6.6 cron_fired / cron_scheduled / cron_drift

```jsonc
"event_type": "cron_fired",
"payload": {
  "schedule_expr": "*/30 * * * *",
  "scheduled_for": "2026-05-16T09:30:00Z",
  "fired_at": "2026-05-16T09:30:02.341Z",
  "drift_ms": 2341,
  "job_name": "gumi_proactive_checkin",
  "subject_id": "daniele"
}
```

### 6.7 privacy_decision (unifica `privacy/trace.py` + `persistence.py`)

Schema canonical che sostituisce i due `PrivacyTrace` esistenti:

```jsonc
"event_type": "privacy_decision",
"payload": {
  "stage": "input_scan|rehydration|output_gate|store",
  "content_hash": "sha256:...",
  "privacy_level_assigned": "S0|S1|S2|SAFE",
  "category": "PII|MEDICAL|FINANCIAL|BIOMETRIC|null",
  "confidence": 0.93,
  "redacted": false,
  "rehydration_blocked": false,
  "final_output_blocked": false,
  "policy_id": "default_v1.2",
  "policy_applied": "block_s0|quarantine_s1|warn_s2|pass"
}
```

### 6.8 consent_changed

```jsonc
"event_type": "consent_changed",
"payload": {
  "consent_type": "MEMORY_STORAGE|ANALYTICS|ROLEPLAY|DATA_SHARING",
  "scope": "SESSION|SESSION_WITHIN_APP|PERMANENT",
  "granted": true,
  "previous_state": "granted|denied|not_set",
  "expires_at": "iso8601|null",
  "consent_record_id": "uuid",
  "reason": "user_granted|user_revoked|expired|policy_enforced"
}
```

### 6.9 incident_opened / incident_status_changed / artifact_quarantined

```jsonc
"event_type": "incident_opened",
"payload": {
  "incident_id": "uuid",
  "severity": "low|medium|high|critical",
  "title": "...",
  "triggered_by_event_id": "...",
  "category": "privacy|safety|integrity|abuse|system"
}
```

### 6.10 correction_applied

```jsonc
"event_type": "correction_applied",
"payload": {
  "correction_id": "uuid",
  "correction_type": "CONTENT_UPDATE|DELETION|REDACTION|PRIVACY_UPGRADE|FACTUAL_CORRECTION|FIRST_CORRECTION",
  "target_prompt_id": "uuid",
  "derived_artifacts_updated": ["uuid"],
  "applied_at": "iso8601",
  "applied_by": "user|system|policy"
}
```

### 6.11 hook_invoked / hook_returned

```jsonc
"event_type": "hook_invoked",
"payload": {
  "hook_name": "pre_llm_call|transform_llm_output|post_llm_call|...",
  "input_size_chars": 0,
  "input_hash": "sha256:..."
}
```

```jsonc
"event_type": "hook_returned",
"parent_event_id": "<hook_invoked>",
"payload": {
  "output_size_chars": 843,
  "output_hash": "sha256:...",
  "decision_id": "uuid|null",
  "blocked": false,
  "modified": true
}
```

### 6.12 error_raised / retry_started / fallback_triggered

```jsonc
"event_type": "error_raised",
"payload": {
  "error_class": "TimeoutError",
  "error_code": "ERR_OLLAMA_TIMEOUT",
  "raising_module": "relic.gumi.llm_narrator",
  "is_recoverable": true,
  "stack_hash": "sha256:..."           // hash della stack trace, non la trace
}
```

```jsonc
"event_type": "fallback_triggered",
"payload": {
  "original_error_event_id": "...",
  "fallback_strategy": "use_cached_response|skip_model|silent",
  "fallback_module": "relic.hermes_plugin.fail_safe"
}
```

### 6.13 eval_run_started / eval_case_executed / eval_metric_computed

```jsonc
"event_type": "eval_case_executed",
"payload": {
  "experiment_id": "uuid",
  "case_id": "...",
  "case_name": "...",
  "input_hash": "sha256:...",
  "expected_hash": "sha256:...",
  "actual_hash": "sha256:...",
  "passed": true
}
```

```jsonc
"event_type": "eval_metric_computed",
"payload": {
  "experiment_id": "...",
  "metric_name": "groundedness|response_relevance|memory_recall_f1|...",
  "metric_value": 0.87,
  "metric_unit": "score|ratio|count|ms",
  "metric_method": "trulens|deepeval|local|...",
  "sample_size": 50
}
```

### 6.14 artifact_registered / artifact_quarantined / artifact_invalidated

```jsonc
"event_type": "artifact_registered",
"payload": {
  "artifact_id": "uuid",
  "artifact_type": "runtime_profile|agent_embodiment|interaction_policy|trace_export|engagement_snapshot",
  "checksum": "sha256:...",
  "lineage_ref_count": 3,
  "source_snapshot_id": "uuid"
}
```

### 6.15 background_job_started / background_job_completed

```jsonc
"event_type": "background_job_started",
"payload": {
  "job_name": "topic_classifier|engagement_snapshot|memory_consolidation|...",
  "job_kind": "scheduled|triggered|adhoc",
  "trigger_event_id": "..."
}
```

### 6.16 conversation_turn / conversation_session

(Già definiti scaffold §11. Adottati con minor adjust: aggiungere `consent_basis`, `sensitivity`, `parent_event_id`.)

### 6.17 chronicle_access_log (audit dell'audit)

```jsonc
"event_type": "chronicle_access",
"event_category": "admin",
"payload": {
  "accessor_id": "researcher_user|export_cli|automated_report",
  "access_kind": "query|export|delete|view",
  "target_filter": {"subject_id": "...", "trace_id": "...", "date_range": "..."},
  "rows_returned": 142,
  "result_hash": "sha256:..."           // per non-ripudiabilità del download
}
```

Critico: questi eventi devono **avere consent_basis = `null` ma `severity = warn`** se l'accesso è export massivo. Mai loggati come `debug`.

---

## 7. Identificatori e correlazione causale

| ID | Scope | Generato da | Esempio uso |
|----|-------|-------------|-------------|
| `trace_id` | cross-process distributed trace | OTel W3C, propagato via stdout header `X-Trace-Context` | unisce decision in Relic + LLM call in Hermes + delivery in dispatcher |
| `run_id` | singola invocazione di una pipeline (cron checkin, profile bootstrap, eval harness) | il modulo orchestratore | aggregare gate timing + LLM call + delivery di UNA fired |
| `session_id` | conversazione utente-agente (estesa nel tempo) | Hermes runtime | unire turn multipli sotto stessa sessione |
| `event_id` | evento atomico | uuid4 al momento dell'emissione | join con decision/snapshot |
| `parent_event_id` | gerarchia spans (causal-temporal) | event emitter | ricostruzione waterfall |
| `experiment_id` | run di evaluation harness | `relic.eval.harness` | aggregare metric per esperimento |
| `subject_id` | soggetto (utente pseudonimizzato) | preesistente in Relic | filtering, deletion |
| `agent_id` | agente logico (`hermes`, `gumi`, `cron_evaluator`, `cac_controller`) | costante per modulo | filter UI |
| `profile_id` / `hermes_profile_id` | profilo Hermes (`gumi-daniele`) | preesistente | correlare events stesso profile |
| `tool_call_id` | singola tool invocation | event_id di `tool_called` | join con `tool_returned` |
| `model_call_id` | singola model invocation | event_id di `model_called` | join con `model_returned` |
| `artifact_id` | artefatto registrato | preesistente in `ArtifactRegistry` | provenance graph |
| `memory_record_id` | marker memoria singolo | `gumi_continuity.events` | tracciare ciclo vita marker |
| `snapshot_id` | state snapshot | uuid4 | catena `previous_snapshot_id` |
| `decision_id` | decision record | uuid4 | join con events |
| `consent_record_id` | record consent | preesistente `consent_records.id` | join con events |
| `incident_id` | incident report | preesistente | quarantine link |
| `correction_id` | correction event | preesistente | propagation tracking |
| `schema_version` | versione schema evento | `chronicle-event/v1`, `chronicle-decision/v1`, `chronicle-snapshot/v1` | migration |

**Algoritmo di ricostruzione causale** (per il "puoi ricostruire un run in 3 step?"):

1. Dato `trace_id`, recupera tutti gli eventi `WHERE trace_id = ?` ordinati per `timestamp`.
2. Costruisci grafo orientato: nodi = events, archi da `parent_event_id`.
3. Aggancia decisioni (`chronicle_decision WHERE trace_id = ?`) ai loro `input_event_ids` / `output_event_ids`.
4. Aggancia snapshot (`chronicle_state_snapshot WHERE trigger_event_id IN ...`).
5. Aggancia artefatti via `chronicle_artifact_provenance WHERE from_node.node_id IN events`.

Risultato: un DAG completo del run.

---

## 8. Reasoning capture policy

Esplicita: cosa fare del thinking content / chain-of-thought del modello.

### 8.1 Default

Per ogni `model_returned` event, `reasoning_capture` ∈ {`none`, `metrics_only`, `redacted_summary`, `raw_researcher_only`}:

| Livello | Cosa è conservato | Quando attivo |
|---------|-------------------|---------------|
| `none` | nulla del thinking | default per modelli senza thinking esposto, o quando `consent_basis != ANALYTICS` |
| `metrics_only` | solo `thinking_tokens` count | default per modelli con thinking esposto (Qwen3 thinking, Claude extended thinking) |
| `redacted_summary` | summary umano del reasoning (≤ 280 char), generato dal modello stesso o estratto con regex pattern noti | opt-in researcher, attivo solo se `sensitivity ≤ S2` |
| `raw_researcher_only` | thinking content raw, criptato at-rest con chiave researcher | opt-in esplicito per debugging, mai default, audit access mandatory |

Per i decision record:
- `rationale_summary` è SEMPRE human-readable summary, MAI raw CoT.
- max 280 char.
- generato dal modulo che emette la decisione (regola, agente), non dal modello.

### 8.2 Cosa NON memorizzare mai

- chiavi API / token / credenziali (filtrare con regex secret-detector come `detect-secrets`).
- password, hash di password.
- raw biometric data.
- raw medical / psychological assessment.
- raw payload utente quando `sensitivity ≥ S1`.

Filtro applicato al confine `chronicle.emit()`: se il payload contiene pattern secret, l'evento è dropped e un `error_raised` con `error_code=CHRONICLE_SECRET_FILTERED` è emesso al suo posto.

### 8.3 Storage thinking opt-in

Quando `reasoning_capture = raw_researcher_only`:
- thinking content è in file separato `~/.relic/chronicle/thinking/{trace_id}/{event_id}.txt.enc`.
- AES-256-GCM con chiave da keyring locale (`relic-chronicle-researcher-key`).
- accesso loggato come `chronicle_access` event con `severity=warn`.
- retention massima 30 giorni, poi cancellazione automatica.

---

## 9. Privacy, consenso, sensitivity, retention

### 9.1 Principi (invarianti)

1. **Hash mai raw** per qualunque contenuto utente, marker, prompt, risposta.
2. **Pseudonimo mai PII** per identità subject.
3. **Capture-time consent enforcement**: se non c'è `ConsentType.ANALYTICS`, l'evento è dropped a livello di emit; non viene scritto, non viene messo in coda.
4. **Sensitivity-aware visibility**: eventi `S0/S1` non sono mai esposti in export "subject" mode (riservati a researcher mode).
5. **Retention by category**: ogni evento ha un `retention_policy`; un job di reaper pulisce all'expiry.
6. **Deletion cascading**: cancellare un soggetto cancella tutti i suoi eventi + decisioni + snapshot + provenance edges + thinking files.
7. **Audit dell'audit**: ogni accesso al trace è esso stesso un evento.

### 9.2 Sensitivity labels

Adottare l'enum esistente `relic.persistence.PrivacyLevel`:

| Label | Significato | Default visibility |
|-------|-------------|-------------------|
| `SAFE` | nessun rischio privacy | researcher + subject_export |
| `S2_WARNING` | overpersonalizzazione potenziale | researcher + subject_export con redaction |
| `S1_QUARANTINE` | richiede review | researcher only |
| `S0_HARD_VIOLATION` | contenuto da rigettare | quarantine, no inspection senza dual-control |

### 9.3 Consent basis (riusa enum esistente)

`relic.control.consent.ConsentType`: `MEMORY_STORAGE`, `ANALYTICS`, `ROLEPLAY`, `DATA_SHARING`.

- `ANALYTICS` consent è il default richiesto per eventi non-essenziali.
- Eventi `safety` (`incident_opened`, `privacy_decision` con S0) sono catturati anche senza consent (legittimo interesse → integrità sistema). Documentato come "legitimate interest" basis.
- `MEMORY_STORAGE` consent governa la cattura di `memory_write` con `marker_hash`.

### 9.4 Retention policies (proposte)

| Policy | Durata | Applicata a |
|--------|--------|-------------|
| `ephemeral` | finestra di trace (~1h post-run) | events di debug `severity=debug` |
| `short_30d` | 30 giorni | events `info` di routine (model_call, memory_op) |
| `standard_365d` | 365 giorni | events `info` con valore audit (decisioni, state snapshot) |
| `extended_research` | indefinita finché researcher attivo | events `experiment_id != null` |
| `legal_hold` | indefinita | incident con `severity ≥ HIGH`, decision_record disputed |

Job reaper: `chronicle reaper` (cron daily) elimina eventi expired. Il delete passa per `DeleteManager` per cascade su provenance.

### 9.5 Capture levels

Configurazione globale `CHRONICLE_CAPTURE_LEVEL`:

| Level | Cosa cattura |
|-------|--------------|
| `off` | nulla |
| `minimal` | solo `severity ≥ warn` e `event_category in {safety, privacy, consent, error}` |
| `standard` | tutto eccetto `severity=debug` |
| `verbose` | tutto incluso debug |
| `forensic` | standard + thinking raw + secret-detector disabled (USE ONLY IN ISOLATED DEV) |

### 9.6 Audit dell'audit

Ogni accesso al trace (query CLI, export, view UI) emette un `chronicle_access` event:
- `accessor_id`: chi (utente local, automated job)
- `access_kind`: query | export | delete | view
- `target_filter`: cosa è stato richiesto (filtri)
- `rows_returned`
- `result_hash`: hash del risultato (non-ripudiabilità)

Su volumi alti, batch + sampling: 1 evento per query, ma su export ≥ 100 record un evento per export.

### 9.7 OWASP alignment (response capability)

Per ogni rischio OWASP LLM/ASI Top 10, definire quale evento Chronicle risponde:

| OWASP | Domanda investigativa | Evento Chronicle |
|-------|----------------------|-----------------|
| LLM01 Prompt Injection | Quale input ha alterato il comportamento? | `message_received` con `content_hash`, `privacy_decision` |
| LLM02 Sensitive Info Disclosure | Quale risposta ha leakato? | `model_returned` + `privacy_decision` post-output |
| LLM03 Data Poisoning | Quale memory write ha contaminato? | `memory_write` + admission `decision_id` |
| LLM06 Excessive Agency | Quale tool è stato chiamato con quali privilegi? | `tool_called` + `permission_decision_id` |
| LLM07 System Prompt Leakage | SOUL.md è stato esposto? | `model_returned` + diff con SOUL.md hash |
| LLM10 Unbounded Consumption | Quale call ha consumato troppo? | `model_called` con `params.max_tokens` + `usage.output_tokens` |
| ASI T1 Auth Hijacking | Chi era l'attore? | `actor_id` + `actor_type` |
| ASI T2 Memory Poisoning | Quale fonte ha originato il marker? | `memory_write.evidence_event_ids` |

---

## 10. Storage: opzioni, raccomandazioni, migration path

### 10.1 Comparison matrix

| Opzione | Volume sostenibile | Query latency | Operational cost | Lock-in | Fit fase 1 | Fit fase 5 |
|---------|--------------------|--------------:|------------------|---------|-----------|------------|
| **Append-only JSONL** | low (10k/giorno) | seq scan | nullo | nessuno | sì (mirror) | no (deprec) |
| **SQLite** (riuso `relic/db/`) | mid (10M record) | indice OK | nullo | nessuno | **SÌ (primary)** | no (limite write) |
| **DuckDB su Parquet rolling** | high (100M record/giorno) | columnar OK | basso | nessuno | no (overkill) | **SÌ (analytics)** |
| **ClickHouse** | very high (1B+/giorno) | columnar molto OK | medio (server) | nessuno | no | candidato fase 6 |
| **OTel collector → file exporter** | high | n/a | basso | OTel | sì (mirror opzionale) | sì (export) |
| **Phoenix SQLite embedded** | mid | OK via UI | nullo | OpenInference | no (parallel store) | sì (viewer) |
| **Langfuse** | mid | OK | alto (6 servizi) | Langfuse schema | no | no |
| **PostgreSQL** | high | OK | medio | nessuno | no (no PG in Relic) | candidato se Relic adotta PG |
| **Neo4j** (graph) | mid | grafo OK | medio | Cypher | no | candidato fase 6 per provenance graph view |

### 10.2 Raccomandazione fase 1 (now)

**Singolo SQLite** (`relic/db/`) con nuove tabelle:
- `chronicle_events`
- `chronicle_decisions`
- `chronicle_state_snapshots`
- `chronicle_artifact_provenance` (edges)
- `chronicle_access_log`

JSONL **mirror append-only** (`~/.relic/chronicle/journal/YYYY-MM-DD.jsonl`) per:
- backup forense (immutable, grep-able);
- migration sorgente (ricostruzione SQLite se corrotto);
- archive long-term (tar+gzip rolling).

Il **trace_id ↔ traceparent W3C** è generato e propagato cross-process via stdout headers (come scaffold).

OTLP exporter opzionale (`CHRONICLE_OTLP_ENDPOINT`) per chi vuole UI Phoenix/Jaeger; nessuna dipendenza hard.

### 10.3 Raccomandazione fase 4-5

Aggiungere **DuckDB analytics layer**:
- esporta `chronicle_events` rolling weekly come Parquet (`~/.relic/chronicle/parquet/events-YYYY-WW.parquet`).
- DuckDB embedded (no server) interroga Parquet + SQLite live per analytics columnari (engagement snapshots, topic aggregates, OWASP queries).
- Mantiene SQLite per OLTP-style (insert event, query last 24h).

### 10.4 Raccomandazione fase 6 (se volume cresce)

ClickHouse via ClickStack containerizzato + OTel collector. Tutti i nuovi events emessi anche via OTLP. SQLite stays for last 7d hot tier. Migration documentata, non hard.

### 10.5 Migration path SQLite → DuckDB → ClickHouse

```
fase 1 (now)              fase 4               fase 6 (if needed)
─────────────────         ──────────           ───────────────────
JSONL journal     →  +  DuckDB Parquet  →  +  ClickHouse cluster
SQLite primary       SQLite live tier      SQLite hot 7d only
OTLP optional        OTLP optional         OTLP mandatory
```

Schema events versionato `chronicle-event/v1` → `v2` con migrator script. Mai backward-breaking; solo additive.

---

## 11. Interoperabilità

### 11.1 Cosa adottare

| Standard | Adozione | Modo |
|----------|----------|------|
| OpenTelemetry semconv `gen_ai.*` | sì | emettere come attributi span quando OTLP attivo |
| OpenInference `openinference.span.kind` | sì | emettere insieme a gen_ai.* per Phoenix compat |
| W3C Trace Context (traceparent) | sì | propagation cross-process |
| W3C PROV-O concept model | concettuale | tassonomia event → Entity/Activity/Agent |
| OpenLineage Job/Run/Dataset | concettuale | naming `job_name`, `run_id` |
| Elastic Common Schema | opzionale | export adapter |
| OCSF | opzionale | export adapter (security teams) |

### 11.2 Cosa rifiutare

| Strumento | Motivo |
|-----------|--------|
| LangSmith managed | costoso, no self-host free |
| W&B Weave | closed backend, lock-in |
| Helicone proxy | proxy aggiunge latenza, non vede internals |
| Langfuse full stack | troppo pesante (6 servizi) per local-first single-host |
| MLflow tracing | dipendenza pesante non già usata in Relic |

### 11.3 Cosa rimandare (opzionali)

| Tool | Fase | Caso d'uso |
|------|------|-----------|
| Phoenix Arize (Docker) | 4 | viewer locale potente |
| Jaeger all-in-one | 4 | dev waterfall |
| otel-tui | 4 | viewer no-Docker |
| TruLens | 5 | feedback function su trace |
| DeepEval | 5 | eval automatica |
| Marquez | 6 | data lineage view se Relic scala |
| Neo4j provenance | 6 | grafo provenance interrogabile Cypher |

---

## 12. Modello di ispezione

### 12.1 CLI primario (`chronicle`)

Sottocomandi pensati per researcher con session di terminale:

```bash
chronicle query --trace <trace_id>                      # tutto un trace
chronicle query --subject <id> --since 24h              # eventi subject
chronicle query --event-type model_called --since 7d
chronicle timeline --session <session_id>               # waterfall ASCII
chronicle decision --id <decision_id>                   # decision record full
chronicle snapshot --id <snapshot_id>                   # state snapshot
chronicle snapshot --diff <id_before> <id_after>        # diff
chronicle provenance --artifact <artifact_id>           # grafo provenance
chronicle replay --trace <trace_id>                     # riproduce timeline
chronicle stats --op model_called --window 7d           # aggregati
chronicle export --subject <id> --output ./bundle.tar   # passa via control/export
chronicle delete --subject <id> --dry-run               # passa via control/delete
chronicle reaper                                        # esegue retention
```

### 12.2 UI minimale (fase 4)

Opzionale, scelta:

| Opzione | Trade-off |
|---------|-----------|
| Phoenix (`docker run -p 6006:6006 arizephoenix/phoenix:latest`) | UI ricca agent-native, leve OTLP exporter, lock-in OpenInference schema |
| Streamlit single-file app | Custom, leve direttamente SQLite, lavoro ad-hoc |
| HTML statico generato da CLI (`chronicle report --html`) | Zero server, share via email |

**Default fase 4**: Phoenix come opt-in Docker (`docker compose --profile chronicle up`). HTML report come baseline (sempre disponibile).

### 12.3 Viste richieste

- session timeline (waterfall events)
- run timeline (singola pipeline)
- event detail view (JSON full + redacted view)
- causal graph view (DAG events + decisions + snapshots + artifacts)
- profile diff view (snapshot before/after)
- memory r/w view (filterable per namespace)
- tool call view (input/output hashes, permission outcome)
- model call view (tokens, latency, params)
- error/failure view (con retry chain + fallback)
- replayable run view (rigioca eventi non-LLM)
- artifact provenance view (subtree)
- filters per: type, agent, profile, session, sensitivity, severity, consent_basis
- full-text search (su payload_redacted = false content_hash matches — più realistico: per `event_type`, `error_code`, `tags`)
- JSON export
- Markdown export
- experiment summary
- run comparison
- profile version comparison

### 12.4 Minimum first version (fase 4)

- CLI: `query`, `timeline`, `decision`, `snapshot`, `provenance`, `stats`, `export`
- HTML report generator
- nessun web server

UI Phoenix come opt-in successivo.

---

## 13. Failure mode, rischi, mitigations

| Failure mode | Probabilità | Impatto | Mitigation |
|--------------|------------|---------|-----------|
| Chronicle tracer raises exception in hot path | media | bloccante per delivery | `emit()` wrap in `try/except`, log a stderr e drop |
| SQLite lock contention sotto carico | bassa | latenza aumenta | WAL mode + busy_timeout=5s + bulk insert in batch |
| JSONL file system full | bassa | bloccante | preflight check + monthly rotation + automatic gzip > 30d |
| Schema drift tra emitter e consumer | media | query rotte | `schema_version` enforced + migration script |
| Sensitive data leak in `payload` | bassa | critico | secret-detector at emit; CI test su sample events |
| Trace_id collision cross-process | quasi nulla (uuid4) | misleading correlation | non rilevante |
| Researcher accede senza audit | media | violazione audit dell'audit | audit log mandatory + sudo-style elevation per `forensic` access |
| Reaper cancella troppo (bug retention) | media | perdita evidenza | dry-run obbligatorio, conferma prima di delete > 1000 record |
| Decision record `rationale_summary` contiene CoT raw | media | leak PII | hard limit 280 char + secret-detector + auto-truncate |
| Profile snapshot raw contenuto sensibile | media | leak PII | snapshot referenzia `artifact_id`; il contenuto raw passa per `relic.privacy.gateway` |
| Topic classifier LLM call introduces own trace events loop | bassa | infinite loop | `event_kind != "background_job"` filter pre-classifier |
| Multi-subject in stessa sessione (test) | bassa | mix-up subject_id | enforce subject_id non-null per categorie message/profile/memory |
| Cron drift > 5 min | media | window mismatch | `cron_drift` event con `drift_ms`; alert se p95 > 60s |

---

## 14. Open questions

Da risolvere prima dell'implementazione (o esplicitamente accettate come "later"):

1. **Replay determinismo LLM**: vogliamo replay che richiama il modello (non deterministico) o solo replay dello stato derivato? **Proposta**: solo state replay; ri-call opzionale dietro flag.
2. **Snapshot retention**: snapshot di profilo si conservano in eterno o si compactano (keep N latest + monthly)? **Proposta**: keep all per 90d + 1/month dopo.
3. **Sensitive snapshot encryption**: snapshot con `sensitivity ≥ S1` devono essere criptati at-rest? **Proposta**: sì, AES-256-GCM con chiave da keyring.
4. **Researcher mode dual control**: accesso a `forensic` level richiede dual-key (2 utenti)? **Proposta**: opt-in flag, non default; documentato.
5. **Distribuzione trace_id cross-process**: stdout traceparent funziona ma fragile su lunghe pipe. Alternative? **Proposta**: aggiungere fallback su file `~/.relic/chronicle/run_context/{pid}.tp`.
6. **External memory provider tracing**: chiamate a Hindsight/Byterover/Honcho. Loggiamo provider e latency, ma serve catturare anche la risposta hash? **Proposta**: sì, `provider_response_hash`.
7. **Tool call args schema verification**: tracciare `args_schema_hash` per detection di tool drift? **Proposta**: sì.
8. **Phoenix vs Custom HTML**: priorità default UI? **Proposta**: HTML report sempre, Phoenix opt-in.
9. **Eval events sotto experiment**: `experiment_id` deve essere globale o per-eval-suite? **Proposta**: per-suite, harness genera.
10. **Backward compat con JSONL legacy**: per quante release dual-write? **Proposta**: 3 minor release.
11. **Cron drift alert threshold**: 5 min? 60s? **Proposta**: default warn > 60s, critical > 300s.
12. **Memory dynamics decay events**: ogni passo del decay è un evento, o solo crossing soglia? Volume potenziale alto. **Proposta**: solo crossing soglia (es. decay_score scende sotto 0.5) + snapshot mensile.
13. **Schema migration tool**: bisognoso? **Proposta**: sì, `chronicle migrate v1→v2` come Alembic-style.
14. **Subject identity rotation**: se subject_id cambia (es. dopo reset), come correlare passato? **Proposta**: tabella `subject_id_alias` con `since`/`until`.
15. **OTLP exporter privacy**: invio a Phoenix locale è ok; come prevenire invio accidentale a SaaS? **Proposta**: whitelist hostname (`localhost`, `127.0.0.1`, `phoenix.local`) hard-coded; override solo via env esplicito `CHRONICLE_ALLOW_EXTERNAL_OTLP=1`.

---

## 15. Implementazione a fasi raccomandata (vs scaffold attuale)

Il primo scaffold (`legacy/agentic_dev_v1_scaffold.md`) propone 14 step focalizzati su strumentazione code-points. È utile come riferimento ma manca le fasi 0 (integrazione preesistente), governance e replay. Phasing rivisto:

### Phase 0 — Repo & scaffold audit (must)
- Eseguire l'inventario §2 e formalizzarlo in repo (`docs/chronicle/INVENTORY.md`).
- Identificare punti di integrazione mandatory: `relic/db/`, `relic/artifacts/`, `relic/control/`, `relic/correction/`, `relic/persistence.py`.
- Riconciliare i due `PrivacyTrace` (privacy/trace.py + persistence.py) come schema canonico §6.7.

### Phase 1 — Trace schema & taxonomy (must)
- Definire schema canonical (§6).
- Aggiungere migration `relic/db/migrations/NN_chronicle_events.sql` con tabelle `chronicle_*`.
- Pydantic models `relic/chronicle/schema.py`.
- `schema_version` versioning.
- Sensitivity enum riusa `PrivacyLevel`; consent_basis riusa `ConsentType`.

### Phase 2 — Local append-only capture (must)
- `relic/chronicle/emitter.py`: dual-write SQLite + JSONL.
- `relic/chronicle/context.py`: contextvars per trace_id / run_id / session_id.
- Capture-time consent enforcement (chiama `ConsentManager.check_consent`).
- Secret detector + payload redaction.
- Test: 1k events sequential, integrity check, schema validation.

### Phase 3 — Runtime integration (must)
Ordine consigliato:
1. `cron_wiring.py` — emit_decision_event riscritto a emettere `chronicle_event` + `chronicle_decision`.
2. `llm_narrator.py` — model_called / model_returned events.
3. `memory_provider.py` — memory_read / memory_write.
4. `hooks.py` — hook_invoked / hook_returned.
5. `cac/controller.py` — admission decision + scoring breakdown.
6. `hermes_runtime.py:DeliveryGate` — delivery event.
7. `soul_loader.py` — system_message_loaded event.
8. `tool_permissions.py` — tool_called permission decision.
9. `fail_safe.py` — fallback_triggered.
10. `correction/propagation.py` — correction_applied.
11. `control/incident.py` — incident_opened.
12. `control/consent.py` — consent_changed.
13. `profile/registry.py` — profile_write_attempted/applied/rejected + snapshot trigger.
14. `profile/bootstrap_tui.py` — bootstrap step events.
15. `eval/harness.py` — eval_run_started / eval_case_executed.
16. `memory_dynamics/` — decay/reinforcement/consolidation events (gated by volume).
17. `gumi_continuity/events.py` — continuity marker lifecycle.
18. `gumi_memory/providers/*.py` — external_memory_call.
19. `gumi_plugin/critic.py` — critic_decision.
20. `gumi_plugin/{tts,image_gen,lyria}.py` — media_generated.

Ogni integrazione: fail-open, capture-time consent, sensitivity tag.

### Phase 4 — Inspection tools (must)
- CLI completo (`chronicle query/timeline/decision/snapshot/provenance/stats/export/delete/reaper`).
- HTML report generator (`chronicle report --html`).
- Replay primitivo (state-only).

### Phase 5 — Advanced (opt)
- OTLP adapter (Phoenix/Jaeger).
- DuckDB Parquet analytics tier.
- TruLens / DeepEval consumer (eval events).
- Causal graph view (HTML/Phoenix).

### Phase 6 — Governance (must, can be parallel to 4)
- Retention reaper.
- Audit dell'audit (`chronicle_access` mandatory).
- Subject deletion cascade end-to-end test.
- Researcher-only mode (`forensic` level).
- Encryption at-rest per `S1+` snapshot.

### Phase 7 — Scaling path (opt)
- ClickHouse adapter (se volume cresce).
- Neo4j provenance graph (se ispezione complessa).
- Marquez (se Relic adotta pipeline data orchestration).

---

## 16. Acceptance criteria misurabili

Dato un singolo messaggio utente, un researcher deve poter ricostruire l'intero percorso causale **in ≤ 3 ispezioni**:

1. `chronicle query --message-id <hash>` → trova `message_received` event con `trace_id`.
2. `chronicle timeline --trace <trace_id>` → vede waterfall completo: profile/memory/tool/model ops triggered.
3. `chronicle snapshot --diff <before> <after>` → vede profile change risultante.

**Criteri specifici, verificabili automaticamente in test:**

| # | Domanda | Query attesa | Criterio pass |
|---|---------|--------------|---------------|
| 1 | Cosa è successo nella session X? | `chronicle query --session X` | ritorna ≥ 1 message_received + ≥ 1 model_called + ≥ 1 message_sent |
| 2 | Quale agent ha agito? | `chronicle query --trace T --field actor_id` | distinct(actor_id) non vuoto |
| 3 | Quale modello? | `chronicle query --trace T --event-type model_called --field payload.model_id` | model_id non vuoto |
| 4 | Quale input al modello? | `payload.prompt_hash` | hash 64 hex, mai raw |
| 5 | Quale output? | `payload.response_hash` | hash 64 hex |
| 6 | Quale tool chiamato? | `chronicle query --trace T --event-type tool_called` | tool_name + args_hash |
| 7 | Cosa ha restituito il tool? | `--event-type tool_returned` | result_hash, outcome |
| 8 | Quali memory read? | `--event-type memory_read --trace T` | namespace + markers_returned |
| 9 | Quali memory write? | `--event-type memory_write --trace T` | namespace + admission_decision_id |
| 10 | Quale profile letto? | `chronicle query --event-type profile_read --trace T` | profile_id |
| 11 | Quale profilo modificato? | `--event-type profile_write_applied --trace T` | snapshot_before_id + snapshot_after_id |
| 12 | Cosa è cambiato nel profilo? | `chronicle snapshot --diff B A` | diff non vuoto |
| 13 | Quali decision record? | `chronicle query --event-category decision --trace T` | decisione con selected_action |
| 14 | Quale evidenza per la decisione? | `chronicle decision --id D` | evidence_refs non vuoto |
| 15 | Quali errori? | `--event-type error_raised --trace T` | error_class popolato |
| 16 | Retry/fallback? | `--event-type retry_started / fallback_triggered --trace T` | parent_event_id valorizzato |
| 17 | Quali artefatti generati? | `--event-type artifact_registered --trace T` | artifact_id presente |
| 18 | Eventi che hanno contribuito all'artefatto? | `chronicle provenance --artifact A` | grafo non vuoto |
| 19 | Quali dati sensibili? | `--sensitivity-min S2 --trace T` | filtra correttamente |
| 20 | Sotto quale consent? | `--field consent_basis --trace T` | consent_basis enum valido |
| 21 | Cosa è esportabile? | `chronicle export --subject X --dry-run` | conta record per categoria |
| 22 | Cosa cancellabile? | `chronicle delete --subject X --dry-run` | conta record per categoria + cascade |
| 23 | Cosa va retained? | `chronicle reaper --dry-run` | conta candidate per policy |

Test suite ogni domanda → asserzione. Aggregato in `tests/chronicle/test_acceptance.py`.

---

## 17. Tabella comparativa consolidata (vendor + standard)

| Sistema | Cosa fa bene | Cosa fa male per Relic | Riuso | Decisione |
|---------|--------------|------------------------|-------|----------|
| OpenTelemetry SDK | standard, vendor-neutral | spec gen_ai.* ancora Development | semconv + traceparent | adottare come emit layer opzionale |
| OTel `gen_ai.*` | model metrics standard | no nativo thinking | attributi span | sì come format |
| OpenInference | agent-native conventions | divergente da OTel | span.kind | sì in parallelo |
| W3C PROV-O | provenance standard | RDF verbose | modello concettuale | sì concettuale, no serializzazione default |
| OpenLineage / Marquez | data lineage, run/job/dataset | ETL-centric | naming pattern | sì naming, no Marquez backend |
| OCSF | security event standard | overkill | category names per security events | sì naming export adapter |
| Elastic Common Schema | flat schema log+sec mature | non LLM-native | export adapter | sì opt export |
| Event Sourcing (ESAA) | replay perfetto, audit | LLM non deterministico | proiezione state da events | sì design pattern |
| MLflow tracing v3 | esperimenti unificati | dipendenza pesante | export adapter | no |
| W&B Weave | UX | closed backend, cloud | nulla | escluso |
| TruLens | feedback functions | extra LLM cost | consumer di trace | sì opt consumer fase 5 |
| Helicone | proxy zero-config | proxy, vede solo HTTP | nulla | escluso |
| LangSmith | UI ricca | enterprise pricing | nulla | escluso |
| Langfuse OSS | UI ricca | 6 servizi pesante | OTLP target | rimandato |
| Phoenix Arize | open, agent-native, single Docker | OpenInference schema lock-in | OTLP target + UI | adottato come UI opt-in |
| Jaeger | waterfall semplice | volatile in-memory | OTLP dev | opt fase 4 |
| otel-tui | no-Docker terminal | UI limitata | dev fast view | opt fase 4 |
| DeepEval | eval framework | extra LLM cost | consumer fase 5 | sì opt |
| ClickStack / ClickHouse | scala miliardi span | server pesante | fase 6 backend | rimandato |
| DuckDB / ducklake | analytics zero-server | non append-friendly | fase 4 analytics | adottato come tier analytics |
| SQLite (relic/db/) | già presente, riusato | scrittura single-writer | primary store | **scelto** |
| JSONL append-only | trivial, audit forense | scan lento | mirror | **scelto come mirror** |
| Neo4j | grafo provenance | server | fase 6 | rimandato |
| `relic/control/consent.py` | already implements consent | — | backend policy | **mandatory riuso** |
| `relic/control/delete.py` | already cascading invalidate | — | deletion cascade | **mandatory riuso** |
| `relic/control/export.py` | already export+redact | — | export bundle | **mandatory riuso** |
| `relic/control/incident.py` | already quarantine | — | incident events | **mandatory riuso** |
| `relic/artifacts/registry.py` | already lineage_refs | — | artifact source-of-truth | **mandatory riuso** |
| `relic/compiler/lineage.py` | already tracker | — | provenance backbone | **mandatory riuso** |
| `relic/correction/propagation.py` | already correction trace | — | correction events | **mandatory riuso** |
| `relic/persistence.py:PrivacyLevel` | sensitivity enum | — | sensitivity labels | **mandatory riuso** |

---

## 18. Fonti

Standard e specifiche:
- [W3C PROV-O recommendation](https://www.w3.org/TR/prov-o/)
- [OpenLineage spec](https://openlineage.io/getting-started/) — [Marquez project](https://marquezproject.ai/)
- [OpenTelemetry gen_ai semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [W3C Trace Context (traceparent)](https://www.w3.org/TR/trace-context/)
- [OCSF schema](https://schema.ocsf.io/) — [How OCSF Became the Common Security Data Language for the AI Era](https://www.techbuddies.io/2026/04/05/how-ocsf-became-the-common-security-data-language-for-the-ai-era/)
- [Elastic Common Schema](https://www.elastic.co/guide/en/ecs/current/index.html)

Pattern e ricerca:
- [ESAA: Event Sourcing for Autonomous Agents (arxiv 2602.23193)](https://arxiv.org/abs/2602.23193)
- [AxonIQ: AI Agent Explainability and Event Sourcing](https://www.axoniq.io/blog/ai-agent-explainability-event-sourcing-infrastructure)
- [Agent observability complete guide 2026 — Braintrust](https://www.braintrust.dev/articles/agent-observability-complete-guide-2026)
- [OWASP Top 10 for AI Agents (ASI) 2026](https://dev.to/alessandro_pignati/the-owasp-top-10-for-ai-agents-your-2026-security-checklist-asi-top-10-cck)
- [OWASP LLM Top 10 2026](https://repello.ai/blog/owasp-llm-top-10-2026)

Tooling LLM observability:
- [OpenLLMetry GitHub](https://github.com/traceloop/openllmetry)
- [Phoenix / Arize GitHub](https://github.com/Arize-ai/phoenix) — [OpenInference GitHub](https://github.com/Arize-ai/openinference)
- [Langfuse self-hosting](https://langfuse.com/self-hosting)
- [MLflow tracing](https://mlflow.org/docs/latest/tracing/) — [MLflow alternatives 2026](https://futureagi.com/blog/mlflow-alternatives-2026)
- [W&B alternatives 2026](https://futureagi.com/blog/best-weights-and-biases-alternatives-2026)
- [TruLens GitHub](https://github.com/truera/trulens)
- [Helicone alternatives](https://tokenmix.ai/blog/helicone-alternative)
- [Best LLM Observability Tools 2026 — Firecrawl](https://www.firecrawl.dev/blog/best-llm-observability-tools)
- [LangSmith pricing](https://www.langchain.com/pricing)

Storage:
- [ClickHouse for OpenTelemetry traces](https://clickhouse.com/blog/how-we-used-clickhouse-to-store-opentelemetry-traces) — [ClickStack](https://clickhouse.com/clickstack)
- [duckdb-otlp by smithclay](https://github.com/smithclay/duckdb-otlp)
- [OpenTelemetry + DuckDB integration](https://www.influxdata.com/integrations/opentelemetry-duckdb/)

Privacy / GDPR:
- [GDPR Compliance 2026 guide — Secure Privacy](https://secureprivacy.ai/blog/gdpr-compliance-2026)
- [LLM GDPR compliance — Relyance AI](https://www.relyance.ai/blog/llm-gdpr-compliance)
- [Right to be Forgotten in LLMs (arxiv 2307.03941)](https://arxiv.org/pdf/2307.03941)
- [LLMs under GDPR — Dynamiq](https://www.getdynamiq.ai/post/balancing-innovation-and-privacy-llms-under-gdpr)
- [LLM compliance with GDPR — Milvus](https://milvus.io/ai-quick-reference/what-measures-ensure-llm-compliance-with-data-privacy-laws-like-gdpr)

Documenti complementari (scaffold preesistente):
- `docs/chronicle/legacy/research_v1_scaffold.md` (primo pass, OTel + Phoenix + Langfuse focus)
- `docs/chronicle/legacy/agentic_dev_v1_scaffold.md` (primo pass, 14 step implementazione)
