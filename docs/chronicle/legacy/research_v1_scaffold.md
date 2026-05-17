# Chronicle: Full Tracing System for Relic/Hermes
## Research & Architecture Document

**Data:** 2026-05-16  
**Scope:** Osservabilità completa di ogni evento, decisione, generazione LLM, operazione memoria, consegna messaggi nel runtime Relic/Hermes.

---

## 1. Stato Attuale: Cosa Esiste Già

### 1.1 File JSONL di Audit Esistenti

Il codebase produce già 7 file JSONL di audit, ma tutti operano in silos separati senza correlazione:

| File | Produttore | Contenuto |
|------|-----------|-----------|
| `~/.relic/decision_events.jsonl` | `cron_wiring.py:emit_decision_event()` | Decisione cron (DELIVER/NO_REPLY/BLOCKED), reason_codes, subject_id |
| `cac_trace.jsonl` | `cac/trace.py:CACTraceWriter` | Decisioni ammissione memoria: severity, memory_hash, skip_reason |
| `privacy_trace.jsonl` | `persistence.py:PrivacyTrace` | Gate privacy: stage, content_hash, policy_applied |
| `~/.relic/subjects/{id}/escalation_log.jsonl` | `safety/escalation_notifier.py` | Segnali safety: tipo, subject_id, metodo escalation |
| `bootstrap_session.jsonl` | `profile/bootstrap_tui.py` | Flusso bootstrap profilo |
| `profile_edit_log.jsonl` | `profile/registry.py` | Modifiche ai campi profilo |
| `delivery_decision_log.jsonl` | `profile/registry.py` | Storico decisioni delivery |

### 1.2 Logging Strutturato Attuale

Tutti i moduli seguono il pattern di fallback:
```python
try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
```

### 1.3 Gap Critici

I file esistenti **non catturano**:
- **Nessun `trace_id` unificato** — impossibile correlare cron_decision → LLM call → delivery in un'unica traccia
- **Zero metriche LLM** — nessun token count, nessun timing, nessun TTFT, nessun tps
- **Timing per gate** — `_evaluate_decision()` ha 7 gate sequenziali, nessuno tempificato individualmente
- **Calcoli intermedi** — selezione media type, calcolo jitter, risoluzione timezone: tutti silenti
- **Timing operazioni memoria** — lettura/scrittura hindsight senza durata
- **Admission policy markers** — quali marker continuità sono stati ammessi/bloccati e perché
- **Hook timing** — durata pre_llm_call, transform_llm_output
- **Thinking tokens** — per modelli con ragionamento (qwen3 thinking mode)

---

## 2. Requisiti del Sistema Chronicle

### 2.1 Requisiti Funzionali

**Per ogni cron trigger:**
- Timestamp ms-precision di inizio/fine pipeline
- Timing individuale di ogni gate (`pro_checkin_allowed`, `quiet_hours`, `platform_allowlist`, `subject_paused`, `continuity_scope_paused`, `delivery_window_open`, `media_type_selection`)
- Calcolo jitter: `target_min` vs `now_min`, outcome
- Selezione media type: tipi eligibili, valore roll, selezione finale
- Decisione finale + reason_codes

**Per ogni chiamata LLM:**
- `input_tokens`, `output_tokens`, `thinking_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`
- `time_to_first_token_ms` (per streaming)
- `total_duration_ms`
- `tokens_per_second` (calcolato: `output_tokens / gen_time_s`)
- `model`, `provider`, `temperature`, `max_tokens`
- `prompt_hash` (SHA-256 del prompt, non il contenuto)
- `response_hash` (SHA-256 della risposta)
- `finish_reason`, `retry_attempt`
- `streaming: bool`

**Per ogni operazione memoria:**
- Tipo operazione: read / write / prefetch / sync_turn
- Namespace, key (hash)
- Durata ms
- Esito: hit / miss / blocked (con reason)
- Count marker ammessi vs bloccati (per prefetch)

**Per ogni hook:**
- Nome hook, timing ms
- Input/output size in caratteri
- Esito: pass / block / error

**Per ogni delivery:**
- Platform, subject_id
- Gate decision: ALLOW / BLOCK + reason
- Durata dispatch ms
- Media type effettivo consegnato

### 2.2 Requisiti Non Funzionali

- **Local-first**: nessun dato inviato a cloud di terze parti
- **Zero-overhead su failure**: ogni punto di tracing usa try/except, mai blocca il percorso principale
- **Correlazione**: `trace_id` (UUID4) propagato attraverso tutta la pipeline cron→LLM→delivery
- **Privacy-safe**: MAI contenuto raw prompt/risposta nei trace. Solo hash SHA-256.
- **Append-only**: JSONL come storage primario, immutabile
- **Queryable**: SQLite come indice secondario costruito dal JSONL

---

## 3. Survey Framework di Osservabilità

### 3.1 OpenTelemetry SDK + gen_ai.* Semantic Conventions

**Cos'è:** Standard CNCF per distributed tracing. Le semantic conventions `gen_ai.*` sono il namespace ufficiale per LLM.

**Status spec gen_ai.*** (maggio 2026): **Development/Experimental** — non ancora Stable, ma adottato de-facto da Datadog v1.37 e Grafana. Env var `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental` per opt-in.

**Attributi standardizzati rilevanti:**

| Attributo | Tipo | Note |
|-----------|------|------|
| `gen_ai.operation.name` | string | `chat`, `generate_content` |
| `gen_ai.provider.name` | string | `anthropic`, `openai`, `ollama` |
| `gen_ai.request.model` | string | modello richiesto |
| `gen_ai.response.model` | string | modello effettivo |
| `gen_ai.request.temperature` | double | |
| `gen_ai.request.max_tokens` | int | |
| `gen_ai.request.stream` | bool | |
| `gen_ai.usage.input_tokens` | int | |
| `gen_ai.usage.output_tokens` | int | |
| `gen_ai.usage.reasoning.output_tokens` | int | thinking tokens |
| `gen_ai.usage.cache_read.input_tokens` | int | token da cache |
| `gen_ai.usage.cache_creation.input_tokens` | int | token scritti in cache |
| `gen_ai.response.time_to_first_chunk` | double (s) | TTFT per streaming |
| `gen_ai.response.finish_reasons` | string[] | |
| `gen_ai.conversation.id` | string | correlazione sessione |
| `gen_ai.agent.name` | string | es. `hermes`, `gumi` |
| `gen_ai.workflow.name` | string | es. `cron_checkin`, `profile_bootstrap` |

**Metriche OTel (istogrammi):**
- `gen_ai.client.operation.duration` — durata totale call
- `gen_ci.client.operation.time_to_first_chunk` — TTFT histogram
- `gen_ai.client.token.usage` — token count histogram

**tokens_per_second:** NON è un attributo nativo OTel. Formula standard:
```python
tps = (output_tokens - 1) / (total_duration_s - ttft_s)
# → emettere come attributo custom: gen_ai.usage.tokens_per_second
```

**Prompts e completions:** Per privacy, la spec raccomanda di emettere come **span events** (opt-in), non come attributi span:
```python
span.add_event("gen_ai.client.inference.operation.details", {
    "gen_ai.input.messages": prompt_hash,   # hash, non contenuto
    "gen_ai.output.messages": response_hash,
})
```

**Pro:** Standard industria, vendor-agnostic, Datadog/Grafana nativi  
**Contro:** Spec ancora Development, no attributo nativo per thinking_tokens Ollama

---

### 3.2 Phoenix (Arize) — Consigliato come viewer locale

**GitHub:** https://github.com/Arize-ai/phoenix — 9.000+ stelle  
**Self-hostable:** Sì, completamente free e open-source  
**Storage:** SQLite di default (zero config), PostgreSQL in produzione  
**Licenza:** Apache 2.0

**Deploy in un comando:**
```bash
docker run -p 6006:6006 arizephoenix/phoenix:latest
# UI + OTLP collector su localhost:6006
```

**Convenzioni:** Usa `openinference.*` (es. `openinference.span.kind`) invece di `gen_ai.*`. Valori di `openinference.span.kind`:
`LLM`, `AGENT`, `CHAIN`, `TOOL`, `RETRIEVER`, `RERANKER`, `GUARDRAIL`, `EVALUATOR`, `EMBEDDING`, `PROMPT`

Questi valori mappano perfettamente sui subsistemi Hermes. Phoenix accetta anche OTLP raw con `gen_ai.*`.

**Strumento Python:**
```python
from phoenix.otel import register
tracer_provider = register(
    project_name="relic-hermes",
    endpoint="http://localhost:6006/v1/traces",
)
```

**Pro per Relic:** Singolo container Docker, SQLite zero-config, accetta OTLP standard, ottimo UI agent-native  
**Contro:** Convenzioni `openinference.*` divergono da OTel `gen_ai.*` (soluzione: emettere entrambi)

---

### 3.3 OpenLLMetry (Traceloop) — Consigliato per auto-instrumentazione

**GitHub:** https://github.com/traceloop/openllmetry — 7.100 stelle  
**Output:** Pure OTel OTLP — route a qualsiasi backend  
**Licenza:** Apache 2.0

Auto-instrumenta 15+ provider LLM. Per Relic (Ollama/OpenAI-compatible + Anthropic):
```bash
pip install opentelemetry-instrumentation-anthropic
# oppure
pip install opentelemetry-instrumentation-openai  # per Ollama via API compat
```

```python
from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor
AnthropicInstrumentor().instrument()
# Tutte le chiamate subsequent sono auto-tracciate
```

**Thinking tokens:** Issue aperta #2774 — non ancora nativo. Workaround: leggere manualmente da `usage.thinking_tokens` nella response Ollama.

**Pro:** Zero modifiche ai call site, output OTel puro, coverage provider più ampio  
**Contro:** `Traceloop.init()` di default invia al cloud Traceloop — usare i singoli package instrumentazione senza wrapper

---

### 3.4 Langfuse — Alternativa per UX ricca

**GitHub:** https://github.com/langfuse/langfuse  
**Self-host:** Sì via Docker Compose, completamente OSS  
**Licenza:** MIT  
**Architettura v3:** 6 servizi (langfuse-web, langfuse-worker, ClickHouse, PostgreSQL, Redis/Valkey, MinIO/S3)

**Pro:** Miglior UX self-hosted, gestione prompt, OTel-native in v3 (`http://localhost:3000/api/public/otel/v1/traces`)  
**Contro:** Pesante (ClickHouse è una dipendenza non-triviale), eccessivo per dev locale

---

### 3.5 Jaeger All-in-One — Alternativa viewer minimalista

```yaml
# docker-compose.yml (aggiunta al compose Relic)
jaeger:
  image: jaegertracing/all-in-one:1.76.0
  ports:
    - "16686:16686"   # UI waterfall
    - "4317:4317"     # OTLP gRPC
    - "4318:4318"     # OTLP HTTP
  environment:
    - COLLECTOR_OTLP_ENABLED=true
```

UI waterfall/flamegraph a `http://localhost:16686`. Storage in-memory (volatile). Per persistenza: `SPAN_STORAGE_TYPE=badger` + volume mount.

---

### 3.6 LangSmith — ESCLUSO

Self-host richiede contratto Enterprise (~$2.000-5.000/mese). Non viable per Relic OSS.

---

### 3.7 otel-tui — Viewer terminale (no Docker)

Single Go binary, riceve OTLP, mostra waterfall nel terminale:
```bash
go install github.com/ymtdzzz/otel-tui@latest
otel-tui  # ascolta su 4317, UI nel terminale
```

---

## 4. Confronto Framework

| Opzione | Stelle | Self-host free | Storage default | Setup | Ideale per |
|---------|--------|----------------|-----------------|-------|-----------|
| OTel SDK (manuale) | — | Sì | Qualsiasi | 10 righe | Controllo massimo |
| **Phoenix** ✓ | 9k+ | Sì | SQLite | `docker run` | Viewer OSS consigliato |
| **OpenLLMetry** ✓ | 7.1k | Sì (OTLP output) | Qualsiasi | `pip install` | Auto-instrumentazione |
| Langfuse | — | Sì | ClickHouse+PG | Compose 6 svc | UX ricca, pesante |
| Jaeger all-in-one | — | Sì | In-memory | `docker run` | Waterfall dev |
| LangSmith | 886 | No (Enterprise) | Managed | — | ESCLUSO |
| otel-tui | — | Sì | — | `go install` | No-Docker viewer |

---

## 5. Architettura Consigliata: Stack Chronicle

```
┌─────────────────────────────────────────────────────┐
│                  RELIC / HERMES RUNTIME              │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ cron_    │  │  LLM     │  │  memory/hooks/   │  │
│  │ wiring   │  │  calls   │  │  delivery/safety  │  │
│  └────┬─────┘  └────┬─────┘  └────────┬─────────┘  │
│       │             │                 │             │
│       └─────────────┴─────────────────┘             │
│                     │                               │
│            ┌────────▼────────┐                      │
│            │  ChronicleTracer  │  (thin OTel wrapper) │
│            │  - trace_id     │                      │
│            │  - span nesting │                      │
│            │  - gen_ai attrs │                      │
│            └────────┬────────┘                      │
└─────────────────────┼───────────────────────────────┘
                      │ OTLP gRPC/HTTP
          ┌───────────┼───────────┐
          │           │           │
    ┌─────▼────┐  ┌──▼──────┐ ┌──▼──────────┐
    │  JSONL   │  │ SQLite  │ │  Phoenix /  │
    │  file    │  │  index  │ │  Jaeger     │
    │ (primary │  │(query)  │ │  (UI)       │
    │ durable) │  └─────────┘ └─────────────┘
    └──────────┘
```

### Layer 1 — Strumentazione (ChronicleTracer)

Un modulo Python `relic/chronicle/tracer.py` che:
- Mantiene un OTel `TracerProvider` configurato con due exporter:
  1. `JSONLSpanExporter` → `~/.relic/chronicle/traces.jsonl` (durable, append-only)
  2. `OTLPSpanExporter` → Phoenix/Jaeger se disponibile (best-effort, fail-open)
- Espone un context manager `@trace_span(name, kind, attrs)` usabile in tutta la codebase
- Propaga `trace_id` via `contextvars.ContextVar` per cron jobs (no HTTP request)
- Emette attributi sia `gen_ai.*` (OTel standard) che `openinference.*` (Phoenix compat)

### Layer 2 — Storage Primario (JSONL)

File: `~/.relic/chronicle/traces.jsonl`  
Formato: una riga JSON per span, append-only.  
Rotazione: per data (`traces-2026-05-16.jsonl`).  
Backup: immutabile, grep-able, importabile in qualsiasi tool.

### Layer 3 — Indice SQLite

File: `~/.relic/chronicle/traces.db`  
Costruito all'avvio dal JSONL (idempotente, ricreabile).  
Permette query tipo: "tutti gli span LLM degli ultimi 7 giorni", "decisioni SILENT del profilo gumi-daniele", "latenza media per modello".

### Layer 4 — Viewer

Dev locale: **Phoenix** (`docker run -p 6006:6006 arizephoenix/phoenix:latest`)  
Fallback no-Docker: **otel-tui** (`go install github.com/ymtdzzz/otel-tui@latest`)  
Integrato nel compose Relic: opzione `--profile chronicle` nel docker-compose.yml

---

## 6. Schemi Evento

### 6.1 CronDecisionTrace

Prodotto da `_evaluate_decision()` e `emit_decision_event()` in `cron_wiring.py`.

```json
{
  "trace_id": "a9c3b99a7d2e4f1b8c3d5e6f7a8b9c0d",
  "span_id": "b7e2d4f1a3c5e8f0",
  "parent_span_id": null,
  "op": "cron_decision",
  "openinference.span.kind": "CHAIN",
  "gen_ai.workflow.name": "cron_checkin",
  "gen_ai.agent.name": "hermes",
  "gen_ai.conversation.id": "gumi-daniele",
  "subject_id": "daniele",
  "gumi_instance_id": "gumi-daniele",
  "hermes_profile_id": "gumi-daniele",
  "started_at": "2026-05-16T09:30:00.123Z",
  "ended_at": "2026-05-16T09:30:00.187Z",
  "duration_ms": 64.2,
  "decision": "DELIVER",
  "reason_codes": [],
  "gates": [
    {
      "name": "pro_checkin_allowed",
      "result": true,
      "duration_ms": 1.2,
      "timestamp_ms": 1747388400123.4
    },
    {
      "name": "quiet_hours",
      "result": false,
      "duration_ms": 0.8,
      "timestamp_ms": 1747388400124.6
    },
    {
      "name": "platform_allowlist",
      "result": true,
      "duration_ms": 0.9,
      "timestamp_ms": 1747388400125.5
    },
    {
      "name": "subject_paused",
      "result": false,
      "duration_ms": 0.7,
      "timestamp_ms": 1747388400126.4
    },
    {
      "name": "continuity_scope_paused",
      "result": false,
      "duration_ms": 0.6,
      "timestamp_ms": 1747388400127.1
    },
    {
      "name": "delivery_window_open",
      "result": true,
      "duration_ms": 3.4,
      "timestamp_ms": 1747388400127.7,
      "detail": {
        "window": "09:30-12:30",
        "target_min": 570,
        "now_min": 570,
        "jitter_applied_min": 0,
        "last_outbound_dt": "2026-05-15T23:18:00+02:00",
        "elapsed_since_outbound_h": 10.2
      }
    },
    {
      "name": "media_type_selection",
      "result": "text",
      "duration_ms": 12.1,
      "timestamp_ms": 1747388400131.1,
      "detail": {
        "eligible_types": ["text", "voice"],
        "roll_value": 0.73,
        "selected": "text"
      }
    }
  ],
  "source": "no_agent_cron",
  "status": "ok"
}
```

### 6.2 LLMCallTrace

Prodotto da `_call_llm()` in `gumi/llm_narrator.py` e da ogni altra chiamata LLM nel sistema.

```json
{
  "trace_id": "a9c3b99a7d2e4f1b8c3d5e6f7a8b9c0d",
  "span_id": "c1f5a2e3b4d6f8a0",
  "parent_span_id": "b7e2d4f1a3c5e8f0",
  "op": "llm_call",
  "openinference.span.kind": "LLM",
  "gen_ai.operation.name": "chat",
  "gen_ai.provider.name": "ollama",
  "gen_ai.request.model": "qwen3.5-plus",
  "gen_ai.response.model": "qwen3.5-plus",
  "gen_ai.request.temperature": 0.85,
  "gen_ai.request.max_tokens": 512,
  "gen_ai.request.stream": false,
  "gen_ai.response.finish_reasons": ["stop"],
  "gen_ai.usage.input_tokens": 1847,
  "gen_ai.usage.output_tokens": 63,
  "gen_ai.usage.reasoning.output_tokens": 0,
  "gen_ai.usage.cache_read.input_tokens": 0,
  "gen_ai.usage.cache_creation.input_tokens": 0,
  "gen_ai.usage.tokens_per_second": 28.4,
  "gen_ai.response.time_to_first_chunk_ms": null,
  "total_duration_ms": 2218.5,
  "prompt_hash": "sha256:3a7b9c2d...",
  "response_hash": "sha256:f1e2d3c4...",
  "response_length_chars": 142,
  "reasoning_present": false,
  "retry_attempt": 0,
  "call_site": "llm_narrator.generate_soul_md",
  "started_at": "2026-05-16T09:30:00.188Z",
  "ended_at": "2026-05-16T09:30:02.406Z",
  "error": null,
  "status": "ok"
}
```

### 6.3 MemoryOperationTrace

Prodotto da `memory_provider.py`, `persistence.py`, `cac/controller.py`.

```json
{
  "trace_id": "a9c3b99a7d2e4f1b8c3d5e6f7a8b9c0d",
  "span_id": "d3b8c9f2a5e7d9b1",
  "parent_span_id": "b7e2d4f1a3c5e8f0",
  "op": "memory_operation",
  "openinference.span.kind": "RETRIEVER",
  "operation_type": "prefetch",
  "namespace": "gumi-daniele",
  "subject_id": "daniele",
  "markers_requested": 20,
  "markers_admitted": 5,
  "markers_blocked": 15,
  "block_reasons": {
    "ttl_expired": 8,
    "recall_limit_reached": 4,
    "paused": 2,
    "burden_exceeded": 1
  },
  "duration_ms": 18.3,
  "started_at": "2026-05-16T09:30:00.300Z",
  "ended_at": "2026-05-16T09:30:00.318Z",
  "error": null,
  "status": "ok"
}
```

### 6.4 HookExecutionTrace

Prodotto da ogni hook registrato (`pre_llm_call`, `transform_llm_output`, `post_llm_call`).

```json
{
  "trace_id": "a9c3b99a7d2e4f1b8c3d5e6f7a8b9c0d",
  "span_id": "e4a7d8b1c6f2e9a3",
  "parent_span_id": "b7e2d4f1a3c5e8f0",
  "op": "hook_execution",
  "openinference.span.kind": "GUARDRAIL",
  "hook_name": "pre_llm_call",
  "input_chars": 0,
  "output_chars": 843,
  "output_type": "context_injection",
  "blocked": false,
  "block_reason": null,
  "duration_ms": 22.7,
  "started_at": "2026-05-16T09:30:00.190Z",
  "ended_at": "2026-05-16T09:30:00.213Z",
  "error": null,
  "status": "ok"
}
```

### 6.5 DeliveryTrace

Prodotto da `hermes_runtime.py:DeliveryGate` e dal dispatcher media.

```json
{
  "trace_id": "a9c3b99a7d2e4f1b8c3d5e6f7a8b9c0d",
  "span_id": "f5b9e2c3a7d4f1e8",
  "parent_span_id": "b7e2d4f1a3c5e8f0",
  "op": "delivery",
  "openinference.span.kind": "TOOL",
  "platform": "telegram",
  "subject_id": "daniele",
  "gate_decision": "ALLOW",
  "gate_reason_codes": [],
  "media_type": "text",
  "message_length_chars": 142,
  "duration_ms": 312.4,
  "started_at": "2026-05-16T09:30:02.450Z",
  "ended_at": "2026-05-16T09:30:02.762Z",
  "error": null,
  "status": "ok"
}
```

### 6.6 CACDecisionTrace

Prodotto da `cac/controller.py:evaluate()`.

```json
{
  "trace_id": "a9c3b99a7d2e4f1b8c3d5e6f7a8b9c0d",
  "span_id": "a1b2c3d4e5f6a7b8",
  "parent_span_id": "d3b8c9f2a5e7d9b1",
  "op": "cac_decision",
  "openinference.span.kind": "GUARDRAIL",
  "memory_id": "mem_abc123",
  "memory_hash": "sha256:9f3a2b1c...",
  "severity": "CLEAN",
  "decision": "ADMIT",
  "skip_reason": null,
  "scoring_factors": {
    "clinical_term_score": 0.0,
    "dependency_signal_score": 0.0,
    "disclosure_risk_score": 0.12
  },
  "quarantine_until": null,
  "duration_ms": 3.1,
  "started_at": "2026-05-16T09:30:00.301Z",
  "ended_at": "2026-05-16T09:30:00.304Z",
  "source": "prefetch",
  "status": "ok"
}
```

### 6.7 ProfileBootstrapTrace

Prodotto da `profile/bootstrap_tui.py` e `profile/registry.py`.

```json
{
  "trace_id": "b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6",
  "span_id": "c2d3e4f5a6b7c8d9",
  "parent_span_id": null,
  "op": "profile_bootstrap",
  "openinference.span.kind": "CHAIN",
  "gen_ai.workflow.name": "profile_bootstrap",
  "subject_id": "new_subject",
  "from_state": "draft",
  "to_state": "baseline_complete",
  "step_name": "baseline_questions",
  "duration_ms": 45230.0,
  "started_at": "2026-05-16T10:00:00.000Z",
  "ended_at": "2026-05-16T10:00:45.230Z",
  "error": null,
  "status": "ok"
}
```

---

## 7. Correlazione Trace Cross-Process

Il cron job Hermes è un processo separato da Relic. Per correlare:

### Pattern: traceparent in stdout

Il decision script `relic_no_agent_decision.sh` stampa il `traceparent` W3C come header aggiuntivo:
```
DELIVER
tipo: text
ora: 09:30 Europe/Rome
X-Trace-Context: 00-a9c3b99a7d2e4f1b8c3d5e6f7a8b9c0d-b7e2d4f1a3c5e8f0-01
```

Hermes estrae questo header e lo usa come context per il proprio LLM call span, creando la gerarchia:
```
cron_decision (relic process) → trace_id: a9c3b99a...
  └── llm_call (hermes process) → parent_span_id: b7e2d4f1...
      └── delivery (hermes process)
```

### Fallback: gen_ai.conversation.id

Senza propagazione traceparent, la correlazione avviene tramite:
- `gen_ai.conversation.id` = hermes_profile_id (`gumi-daniele`)
- `gen_ai.workflow.name` = tipo operazione
- Timestamp window: eventi entro ±5 secondi sono correlati

---

## 8. Privacy e Sicurezza del Sistema Trace

**Regole assolute (invarianti):**
1. MAI contenuto raw di prompt o risposta LLM nei trace
2. MAI PII del soggetto (nome reale, ID Telegram, email) nei trace
3. Solo hash SHA-256 per contenuto e identità sensibile
4. `subject_id` è pseudonimo (es. "daniele"), non email/telefono
5. File JSONL leggibili solo dall'owner (`chmod 600`)
6. `scoring_factors` in CACDecisionTrace: solo valori numerici, mai stringhe che descrivono il contenuto

**Campi sicuri da loggare:** timing, token counts, decision enums, reason_codes, hash, model names, template names, durate.

---

## 9. Strumenti di Query e Visualizzazione

### 9.1 CLI — klp

```bash
pip install klp-logviewer
klp ~/.relic/chronicle/traces.jsonl
# Con filtri:
klp --where 'op=="llm_call"' ~/.relic/chronicle/traces.jsonl
klp --where 'total_duration_ms>3000' --keys op,model,total_duration_ms,tokens_per_second traces.jsonl
```

### 9.2 CLI — ripgrep + jq

```bash
# Tutti i SILENT degli ultimi 7 giorni
rg '"decision": "NO_REPLY"' ~/.relic/chronicle/traces.jsonl | jq .

# Latenza media LLM
jq 'select(.op=="llm_call") | .total_duration_ms' traces.jsonl | awk '{s+=$1;c++} END {print s/c}'

# Token/sec per modello
jq 'select(.op=="llm_call") | {model: ."gen_ai.request.model", tps: ."gen_ai.usage.tokens_per_second"}' traces.jsonl
```

### 9.3 SQLite — Query strutturate

```sql
-- Decisioni ultime 24h per outcome
SELECT decision, COUNT(*), AVG(duration_ms)
FROM spans
WHERE op = 'cron_decision'
  AND started_at > datetime('now', '-1 day')
GROUP BY decision;

-- Gate più lento nella pipeline
SELECT gate_name, AVG(gate_duration_ms) as avg_ms
FROM gate_timings
GROUP BY gate_name ORDER BY avg_ms DESC;

-- LLM calls: tokens/sec per modello
SELECT model, AVG(tps), MIN(tps), MAX(tps), COUNT(*)
FROM llm_calls
GROUP BY model;
```

### 9.4 Phoenix UI

URL: `http://localhost:6006`  
View: waterfall trace, service graph, latency histogram, token cost  
Prerequisito: `docker run -p 6006:6006 arizephoenix/phoenix:latest`

---

## 10. Dipendenze Python

```
# requirements — chronicle subsystem
opentelemetry-sdk>=1.32.0
opentelemetry-exporter-otlp-proto-grpc>=1.32.0
opentelemetry-exporter-otlp-proto-http>=1.32.0
opentelemetry-instrumentation-anthropic>=0.60.0  # openllmetry
# oppure:
openinference-instrumentation-anthropic>=0.1.0   # arize phoenix
```

Opzionale (auto-instrumentazione Ollama/OpenAI-compatible):
```
opentelemetry-instrumentation-openai>=0.60.0
```

---

---

## 11. Analisi Conversazionale e Dinamiche Relazionali

Questa sezione copre le metriche che il tracing base (step 1-9) non cattura: la dimensione **temporale** delle interazioni, i **topic** trattati, e le **dinamiche relazionali** tra subject e agent.

### 11.1 Response Latency: Spread tra Messaggi

Due metriche distinte, spesso confuse:

| Metrica | Definizione | Segnale |
|---------|-------------|---------|
| **Agent response latency** | Tempo tra ultimo messaggio subject → risposta agent | Performance sistema + calibrazione cron |
| **Subject response latency** | Tempo tra messaggio agent → risposta subject | Engagement, interesse, disponibilità |

**Distribuzioni da tracciare (non solo media):**
- p50, p90, p95 per ogni direzione
- Distribuzione per fascia oraria (mattino vs sera)
- Distribuzione per giorno della settimana
- Trend nel tempo: la latenza del subject sta aumentando? (segnale disengagement)

**Schema ConversationTurnTrace** (nuovo):
```json
{
  "trace_id": "...",
  "span_id": "...",
  "op": "conversation_turn",
  "session_id": "session_abc123",
  "subject_id": "daniele",
  "hermes_profile_id": "gumi-daniele",
  "turn_number": 3,
  "author": "subject",
  "message_length_chars": 87,
  "response_latency_ms": 14400000,
  "response_latency_h": 4.0,
  "response_to_message_id_hash": "sha256:a1b2c3...",
  "hour_of_day": 22,
  "day_of_week": 5,
  "is_proactive": false,
  "started_at": "2026-05-16T22:11:00Z",
  "status": "ok"
}
```

**Schema SessionTrace** (nuovo):
```json
{
  "trace_id": "...",
  "op": "conversation_session",
  "session_id": "session_abc123",
  "subject_id": "daniele",
  "hermes_profile_id": "gumi-daniele",
  "started_at": "2026-05-16T21:00:00Z",
  "ended_at": "2026-05-16T23:30:00Z",
  "duration_min": 150,
  "total_turns": 8,
  "subject_turns": 4,
  "agent_turns": 4,
  "initiator": "agent",
  "subject_message_avg_chars": 92,
  "agent_message_avg_chars": 134,
  "subject_response_latency_median_ms": 180000,
  "agent_response_latency_median_ms": 1800000,
  "ended_by": "subject_silent",
  "status": "ok"
}
```

### 11.2 Topic Tracking

**Approccio:** classificazione asincrona e non-bloccante. Dopo ogni turn, un job background (non in-path) chiama un LLM leggero con un prompt di classificazione. Il risultato è una lista di topic tag — nessun contenuto raw.

**Tassonomia topic per Relic/Gumi (da adattare per profilo):**

Livello 1 (macro):
- `personal_life` — quotidianità, casa, routine
- `work_creative` — lavoro, progetti, creazioni
- `music_performance` — musica, concerti, pratica
- `food_cooking` — cucina, pasti, ricette
- `spiritual_practice` — spiritualità, meditazione, rituali
- `relationships` — famiglia, amici, dinamiche sociali
- `emotional_state` — stati d'animo, umore, riflessioni
- `future_plans` — progetti, aspettative, desideri
- `current_events` — notizie, mondo, opinioni
- `meta_conversation` — la conversazione stessa, Gumi, connessione
- `practical_logistics` — orari, appuntamenti, cose da fare

**Schema TopicTrace** (nuovo):
```json
{
  "trace_id": "...",
  "op": "topic_classification",
  "session_id": "session_abc123",
  "subject_id": "daniele",
  "turn_number": 3,
  "author": "subject",
  "topics_detected": ["music_performance", "emotional_state"],
  "topic_confidence": {"music_performance": 0.91, "emotional_state": 0.67},
  "dominant_topic": "music_performance",
  "classifier_model": "qwen3.5-plus",
  "classifier_tokens": 45,
  "classified_at": "2026-05-16T22:11:05Z",
  "status": "ok"
}
```

**Schema AggregatedTopicsTrace** (periodico, es. giornaliero):
```json
{
  "op": "topics_daily_aggregate",
  "subject_id": "daniele",
  "date": "2026-05-16",
  "subject_topics": {
    "emotional_state": 3,
    "music_performance": 2,
    "personal_life": 1
  },
  "agent_topics": {
    "music_performance": 2,
    "food_cooking": 2,
    "personal_life": 1
  },
  "topic_overlap_ratio": 0.67,
  "sessions_count": 2,
  "total_turns": 11
}
```

### 11.3 Angoli Ciechi Identificati

I seguenti aspetti **non sono visibili** con il tracing corrente e con le sole metriche ovvie:

#### 1. SILENT Rate Effettivo

Il tasso di `[SILENT]` è tracciato come gate individuale, ma manca il **tasso di SILENT per finestra di consegna consumata**. Se la finestra viene consumata ma l'LLM risponde `[SILENT]`, la finestra è bruciata. Metrica chiave:

```
delivery_window_utilization = turns_delivered / windows_opened
silent_waste_rate = silent_responses / (silent_responses + delivered_responses)
```

#### 2. Context Window Pressure

Per ogni chiamata LLM, il rapporto `input_tokens / max_context_tokens` indica quanto il context è pieno. Se questo tende al 100% nel tempo, significa che context injection + memory + SOUL.md stanno crescendo. Segnale precoce di degradazione qualità.

```json
"gen_ai.context_fill_ratio": 0.72
```

#### 3. Memory Injection Efficiency (Recall Rate)

Quanti dei marker continuità iniettati nel context vengono effettivamente "usati" nella risposta? Segnale proxy: un marker iniettato che non compare mai nelle sessioni successive come punto di riferimento ha recall basso. Non misurabile direttamente (no accesso risposta raw), ma si può misurare **marker TTL utilization**: quanti marker espirano senza mai essere richiamati.

#### 4. Hook Intervention Rate

`transform_llm_output` può modificare o bloccare la risposta LLM. Il tasso di intervento (modify + block / total calls) indica quanto spesso l'OutputCritic agisce. Un tasso alto indica problemi nel SOUL.md o nel modello; un tasso in aumento nel tempo indica deriva.

#### 5. Subject Engagement Decay

La latenza di risposta del subject che aumenta nel tempo è il segnale più precoce di disengagement. Non si vede guardando singole sessioni ma solo su trend 7-30 giorni. Richiede un time-series aggregato.

Metrica: `subject_response_latency_trend_7d` — differenza tra p50 della settimana corrente vs settimana precedente.

#### 6. Proactive/Responsive Ratio (Agent)

Quanti messaggi dell'agent sono **proattivi** (checkin cron) vs **reattivi** (risposte a messaggi subject)? Un ratio che si sbilancia verso solo-proattivi indica che il subject sta smettendo di iniziare conversazioni.

```
initiative_ratio = proactive_messages / total_agent_messages
```

#### 7. Session Depth Distribution

Il numero medio di turn per sessione indica la qualità dell'engagement. Sessioni con 1-2 turn sono "ping-pong" superficiali; sessioni con 8+ turn indicano conversazione profonda. Distribuzione, non media.

#### 8. Time-of-Day Subject Presence

Quando il subject è effettivamente presente e risponde? Questa distribuzione informa il sistema cron su quando è ottimale inviare proactive checkins. Attualmente il sistema usa delivery windows fisse — potrebbero non corrispondere all'availability reale del subject.

#### 9. Message Length Asymmetry

Se il subject invia messaggi sempre più brevi nel tempo mentre l'agent mantiene lunghezze simili, è un segnale di disengagement. Se l'agent invia messaggi molto più lunghi del subject, indica calibrazione sbagliata (SOUL.md noise rules non rispettate).

#### 10. Re-engagement Lag Post-Silence

Dopo periodi di silenzio del subject (>24h senza risposta), quanto impiega il subject a tornare? E cosa lo ha riportato? Questo informa su quale tipo di proactive message funziona come "pull back".

#### 11. Retry e Error Cascade

Quante volte l'LLM torna con errori di rete/timeout? Se il retry rate aumenta, indica problemi infrastruttura (Ollama overload, network). Non visibile nelle decisioni cron ma critico per affidabilità.

#### 12. Cron Drift

Il cron è configurato per girare ogni 30 minuti. Il sistema dovrebbe misurare lo **spread tra trigger pianificato e trigger effettivo** per rilevare drift del scheduler (es. quando Hermes è sotto carico).

---

## 12. Metriche Aggregate Periodiche

Queste metriche devono essere calcolate periodicamente (es. ogni 6 ore via un job separato) e scritte come snapshot in Chronicle:

### 12.1 Schema EngagementSnapshotTrace

```json
{
  "op": "engagement_snapshot",
  "subject_id": "daniele",
  "hermes_profile_id": "gumi-daniele",
  "computed_at": "2026-05-16T06:00:00Z",
  "period_days": 7,
  "sessions_count": 14,
  "total_turns": 89,
  "agent_initiated_sessions": 9,
  "subject_initiated_sessions": 5,
  "initiative_ratio": 0.64,
  "subject_response_rate": 0.78,
  "subject_p50_response_latency_h": 3.2,
  "subject_p90_response_latency_h": 18.4,
  "agent_p50_response_latency_h": 0.5,
  "subject_latency_trend": "+0.8h",
  "avg_session_depth_turns": 6.4,
  "avg_subject_msg_chars": 84,
  "avg_agent_msg_chars": 127,
  "message_length_asymmetry_ratio": 1.51,
  "cron_windows_available": 28,
  "cron_windows_delivered": 9,
  "cron_silent_rate": 0.14,
  "delivery_window_utilization": 0.32,
  "dominant_topics_subject": ["emotional_state", "music_performance"],
  "dominant_topics_agent": ["music_performance", "food_cooking"],
  "topic_overlap_ratio": 0.60,
  "silent_waste_windows": 3,
  "context_fill_ratio_avg": 0.68,
  "hook_intervention_rate": 0.03,
  "llm_avg_tps": 28.4,
  "llm_avg_latency_ms": 2200,
  "status": "ok"
}
```

### 12.2 Schema AlertTrace

Per segnalare automaticamente condizioni anomale (non bloccanti, solo osservazionali):

```json
{
  "op": "chronicle_alert",
  "subject_id": "daniele",
  "alert_type": "engagement_decay",
  "severity": "warning",
  "metric": "subject_p50_response_latency_h",
  "current_value": 18.4,
  "baseline_value": 3.2,
  "threshold_factor": 5.75,
  "description": "Subject response latency increased 5.7x vs baseline (3.2h → 18.4h) over last 7 days",
  "computed_at": "2026-05-16T06:00:00Z",
  "status": "ok"
}
```

**Alert types predefiniti:**
- `engagement_decay` — latenza risposta subject in aumento
- `silent_rate_high` — SILENT rate > 30%
- `context_pressure` — context fill ratio > 85%
- `hook_intervention_spike` — hook intervention rate > 15%
- `session_depth_drop` — avg session depth < 2 turn
- `initiative_imbalance` — initiative ratio > 90% (agent invia sempre, subject non inizia mai)
- `model_degradation` — tps scende > 30% rispetto baseline
- `cron_drift` — cron trigger delay > 5 min rispetto pianificato

---

## Fonti

- [OTel gen_ai Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [OTel gen_ai span attributes](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/)
- [OTel gen_ai agent spans](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/)
- [OTel Python instrumentation guide](https://opentelemetry.io/docs/languages/python/instrumentation/)
- [OTel Python context propagation](https://opentelemetry.io/docs/languages/python/cookbook/)
- [OpenLLMetry GitHub](https://github.com/traceloop/openllmetry)
- [opentelemetry-instrumentation-anthropic PyPI](https://pypi.org/project/opentelemetry-instrumentation-anthropic/)
- [Phoenix / Arize GitHub](https://github.com/Arize-ai/phoenix)
- [OpenInference GitHub](https://github.com/Arize-ai/openinference)
- [Phoenix quickstart tracing Python](https://arize.com/docs/phoenix/tracing/llm-traces-1/quickstart-tracing-python)
- [Langfuse GitHub](https://github.com/langfuse/langfuse)
- [Langfuse self-hosting](https://langfuse.com/self-hosting)
- [Langfuse Python decorator docs](https://langfuse.com/docs/sdk/python/decorators)
- [Langfuse ClickHouse architecture](https://langfuse.com/self-hosting/deployment/infrastructure/clickhouse)
- [LangSmith pricing](https://www.langchain.com/pricing)
- [Jaeger getting started](https://www.jaegertracing.io/docs/1.76/getting-started/)
- [otel-tui terminal viewer](https://dev.to/ymtdzzz/otel-tui-a-tui-tool-for-viewing-opentelemetry-traces-2e7n)
- [klp JSONL viewer GitHub](https://github.com/dloss/klp)
- [OTel 2026 stabilization roadmap](https://github.com/open-telemetry/semantic-conventions/issues/3330)
