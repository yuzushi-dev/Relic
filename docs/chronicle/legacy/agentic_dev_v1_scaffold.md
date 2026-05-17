# Chronicle: Istruzioni per Sviluppo Agentico

**Versione:** 1.0 — 2026-05-16  
**Riferimento architettura:** `docs/chronicle/RESEARCH.md`  
**Stack:** OTel SDK + JSONL primary store + SQLite index + Phoenix viewer

---

## Regole Operative per l'Agente

1. **Fail-open obbligatorio:** ogni punto di trace usa `try/except Exception` attorno al codice Chronicle. Un'eccezione nel trace NON deve mai bloccare il percorso principale.
2. **Zero contenuto raw:** mai loggare prompt, risposte LLM, messaggi utente. Solo hash SHA-256 e metriche numeriche.
3. **Trace ID propagato via contextvars:** non via argomenti di funzione.
4. **Nessun import circolare:** il modulo `relic/chronicle/` non importa da `relic/gumi/`, `relic/hermes_plugin/`, ecc.
5. **Privacy subject_id:** usare solo l'ID pseudonimo (es. `"daniele"`), mai email o telefono.
6. **Implementazione incrementale:** ogni step è indipendente e deployabile. Non rompere funzionalità esistenti.

---

## Step 0: Prerequisiti e Verifica Ambiente

```bash
# Verifica struttura target
ls /home/cristina/Scrivania/relic-oss/relic/
# Deve esistere: gumi/, gumi_plugin/, hermes_plugin/, cac/, profile/, checkin/

# Verifica Python disponibile
python3 --version  # >= 3.10

# Installa dipendenze Chronicle
pip install \
  opentelemetry-sdk>=1.32.0 \
  opentelemetry-exporter-otlp-proto-http>=1.32.0 \
  opentelemetry-exporter-otlp-proto-grpc>=1.32.0

# Verifica installazione
python3 -c "from opentelemetry import trace; print('OTel OK')"
```

---

## Step 1: Crea il Modulo `relic/chronicle/`

### 1.1 `relic/chronicle/__init__.py`

```python
from .tracer import get_tracer, start_span, ChronicleTracer
from .context import get_trace_id, new_trace_id, set_trace_id

__all__ = [
    "get_tracer",
    "start_span",
    "ChronicleTracer",
    "get_trace_id",
    "new_trace_id",
    "set_trace_id",
]
```

### 1.2 `relic/chronicle/context.py`

```python
import uuid
from contextvars import ContextVar

_TRACE_ID: ContextVar[str | None] = ContextVar("chronicle_trace_id", default=None)
_SPAN_ID: ContextVar[str | None] = ContextVar("chronicle_span_id", default=None)
_TRACEPARENT: ContextVar[str | None] = ContextVar("chronicle_traceparent", default=None)


def new_trace_id() -> str:
    return uuid.uuid4().hex


def new_span_id() -> str:
    return uuid.uuid4().hex[:16]


def get_trace_id() -> str | None:
    return _TRACE_ID.get()


def set_trace_id(trace_id: str) -> None:
    _TRACE_ID.set(trace_id)


def get_span_id() -> str | None:
    return _SPAN_ID.get()


def set_span_id(span_id: str) -> None:
    _SPAN_ID.set(span_id)


def get_traceparent() -> str | None:
    return _TRACEPARENT.get()


def make_traceparent(trace_id: str, span_id: str) -> str:
    return f"00-{trace_id}-{span_id}-01"


def set_traceparent_from_ids(trace_id: str, span_id: str) -> None:
    _TRACEPARENT.set(make_traceparent(trace_id, span_id))
```

### 1.3 `relic/chronicle/exporters.py`

```python
import json
import sqlite3
import threading
from datetime import date
from pathlib import Path


class JSONLSpanExporter:
    """Esporta span come righe JSONL in ~/.relic/chronicle/traces-YYYY-MM-DD.jsonl."""

    def __init__(self, base_dir: Path):
        self._base_dir = base_dir
        self._lock = threading.Lock()
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _current_file(self) -> Path:
        today = date.today().isoformat()
        return self._base_dir / f"traces-{today}.jsonl"

    def export(self, span_dict: dict) -> None:
        try:
            with self._lock:
                with open(self._current_file(), "a", encoding="utf-8") as f:
                    f.write(json.dumps(span_dict, ensure_ascii=False) + "\n")
        except Exception:
            pass  # fail-open: trace loss preferibile a crash

    def flush(self) -> None:
        pass


class SQLiteSpanExporter:
    """Esporta span in un SQLite a ~/.relic/chronicle/traces.db."""

    DDL = """
    CREATE TABLE IF NOT EXISTS spans (
        trace_id     TEXT NOT NULL,
        span_id      TEXT PRIMARY KEY,
        parent_span_id TEXT,
        op           TEXT NOT NULL,
        span_kind    TEXT,
        workflow     TEXT,
        subject_id   TEXT,
        started_at   TEXT,
        ended_at     TEXT,
        duration_ms  REAL,
        decision     TEXT,
        status       TEXT,
        error        TEXT,
        attributes   TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_trace    ON spans(trace_id);
    CREATE INDEX IF NOT EXISTS idx_op       ON spans(op);
    CREATE INDEX IF NOT EXISTS idx_subject  ON spans(subject_id);
    CREATE INDEX IF NOT EXISTS idx_started  ON spans(started_at);
    CREATE INDEX IF NOT EXISTS idx_workflow ON spans(workflow);
    """

    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._lock = threading.Lock()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.executescript(self.DDL)

    def export(self, span_dict: dict) -> None:
        try:
            # Campi top-level estratti per indexing; tutto il resto in attributes JSON
            known = {"trace_id", "span_id", "parent_span_id", "op",
                     "openinference.span.kind", "gen_ai.workflow.name", "subject_id",
                     "started_at", "ended_at", "duration_ms", "decision", "status", "error"}
            attributes = {k: v for k, v in span_dict.items() if k not in known}
            row = (
                span_dict.get("trace_id"),
                span_dict.get("span_id"),
                span_dict.get("parent_span_id"),
                span_dict.get("op"),
                span_dict.get("openinference.span.kind"),
                span_dict.get("gen_ai.workflow.name"),
                span_dict.get("subject_id"),
                span_dict.get("started_at"),
                span_dict.get("ended_at"),
                span_dict.get("duration_ms"),
                span_dict.get("decision"),
                span_dict.get("status", "ok"),
                span_dict.get("error"),
                json.dumps(attributes, ensure_ascii=False),
            )
            with self._lock:
                with sqlite3.connect(str(self._db_path)) as conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO spans VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        row,
                    )
        except Exception:
            pass  # fail-open
```

### 1.4 `relic/chronicle/tracer.py`

```python
import hashlib
import os
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

from .context import (
    get_trace_id, get_span_id, new_trace_id, new_span_id,
    set_trace_id, set_span_id, set_traceparent_from_ids,
)
from .exporters import JSONLSpanExporter, SQLiteSpanExporter


def _default_chronicle_dir() -> Path:
    relic_home = os.environ.get("RELIC_HOME", os.path.expanduser("~/.relic"))
    return Path(relic_home) / "chronicle"


class ChronicleTracer:
    """Singleton tracer per il sistema Chronicle."""

    _instance: "ChronicleTracer | None" = None

    def __init__(self, chronicle_dir: Path | None = None):
        base = chronicle_dir or _default_chronicle_dir()
        self._jsonl = JSONLSpanExporter(base)
        self._sqlite = SQLiteSpanExporter(base / "traces.db")
        self._otlp_enabled = False
        self._otlp_exporter = None
        self._setup_otlp()

    def _setup_otlp(self) -> None:
        """Configura OTLP exporter se Phoenix/Jaeger disponibile."""
        endpoint = os.environ.get("CHRONICLE_OTLP_ENDPOINT")
        if not endpoint:
            return
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.resources import Resource, SERVICE_NAME
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            resource = Resource.create({SERVICE_NAME: "relic-hermes"})
            provider = TracerProvider(resource=resource)
            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
            )
            trace.set_tracer_provider(provider)
            self._otlp_enabled = True
        except Exception:
            pass

    @classmethod
    def get(cls) -> "ChronicleTracer":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def emit(self, span: dict) -> None:
        """Emette uno span a tutti gli exporter configurati."""
        try:
            self._jsonl.export(span)
            self._sqlite.export(span)
        except Exception:
            pass

    @contextmanager
    def span(
        self,
        op: str,
        *,
        kind: str = "CHAIN",
        workflow: str | None = None,
        subject_id: str | None = None,
        attrs: dict[str, Any] | None = None,
        parent_span_id: str | None = None,
    ) -> Generator[dict, None, None]:
        """Context manager che crea uno span e lo emette all'uscita."""
        trace_id = get_trace_id()
        if trace_id is None:
            trace_id = new_trace_id()
            set_trace_id(trace_id)

        span_id = new_span_id()
        old_span_id = get_span_id()
        set_span_id(span_id)
        set_traceparent_from_ids(trace_id, span_id)

        effective_parent = parent_span_id or old_span_id

        span: dict[str, Any] = {
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": effective_parent,
            "op": op,
            "openinference.span.kind": kind,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "ok",
            "error": None,
        }
        if workflow:
            span["gen_ai.workflow.name"] = workflow
            span["gen_ai.agent.name"] = "hermes"
        if subject_id:
            span["subject_id"] = subject_id
        if attrs:
            span.update(attrs)

        t0 = time.monotonic()
        try:
            yield span
        except Exception as exc:
            span["status"] = "error"
            span["error"] = type(exc).__name__
            raise
        finally:
            duration_ms = (time.monotonic() - t0) * 1000
            span["ended_at"] = datetime.now(timezone.utc).isoformat()
            span["duration_ms"] = round(duration_ms, 3)
            set_span_id(old_span_id)
            self.emit(span)


def get_tracer() -> ChronicleTracer:
    return ChronicleTracer.get()


@contextmanager
def start_span(op: str, **kwargs) -> Generator[dict, None, None]:
    with get_tracer().span(op, **kwargs) as s:
        yield s


def sha256_hash(content: str) -> str:
    return "sha256:" + hashlib.sha256(content.encode()).hexdigest()[:16]
```

---

## Step 2: Instrumenta `_evaluate_decision()` in `cron_wiring.py`

**File:** `relic/gumi_plugin/cron_wiring.py`  
**Funzione target:** `_evaluate_decision()` — linea ~453  
**Funzione target:** `emit_decision_event()` — linea ~507  
**Funzione target:** `make_decision()` — linea ~534

### 2.1 Aggiungi import in cima al file (dopo gli import esistenti)

```python
# Chronicle tracing — fail-open import
try:
    from relic.chronicle import start_span, get_trace_id, new_trace_id, set_trace_id
    from relic.chronicle.context import get_span_id, get_traceparent
    _CHRONICLE = True
except Exception:
    _CHRONICLE = False
    def start_span(*a, **kw):  # noqa: E306
        from contextlib import nullcontext
        return nullcontext({})
```

### 2.2 Modifica `_evaluate_decision()`

Wrappa ogni gate check con un helper `_timed_gate()` definito come inner function. L'obiettivo è loggare `name`, `result`, `duration_ms`, `timestamp_ms` per ogni gate senza modificare la logica esistente.

**Pattern esatto da applicare:**

Prima della prima istruzione di `_evaluate_decision()`, aggiungi:

```python
import time as _time

_gates: list[dict] = []

def _timed_gate(name: str, fn, *args, detail: dict | None = None):
    t0 = _time.monotonic()
    ts_ms = _time.time() * 1000
    result = fn(*args)
    duration_ms = (_time.monotonic() - t0) * 1000
    entry = {
        "name": name,
        "result": result,
        "duration_ms": round(duration_ms, 3),
        "timestamp_ms": round(ts_ms, 3),
    }
    if detail:
        entry["detail"] = detail
    _gates.append(entry)
    return result
```

Poi sostituisci ogni gate check con la versione `_timed_gate`. Esempio:

```python
# PRIMA:
if not _is_pro_checkin_allowed(subject_id):
    return RuntimeDecision.NO_REPLY, ["subject_paused"]

# DOPO:
if not _timed_gate("pro_checkin_allowed", _is_pro_checkin_allowed, subject_id):
    return RuntimeDecision.NO_REPLY, ["subject_paused"], _gates
```

Ripeti per tutti i gate: `quiet_hours`, `platform_allowlist`, `subject_paused`, `continuity_scope_paused`, `delivery_window_open`, `media_type_selection`.

**Nota:** la firma di `_evaluate_decision()` deve restituire anche `_gates` come terzo elemento. Aggiorna il chiamante `make_decision()` di conseguenza.

### 2.3 Modifica `emit_decision_event()`

Aggiungi il campo `gates` e il `trace_id` nell'evento:

```python
def emit_decision_event(
    decision: RuntimeDecision,
    reason_codes: list[str],
    subject_id: str,
    gumi_instance_id: str,
    hermes_profile_id: str,
    metadata: dict | None = None,
    gates: list[dict] | None = None,
    duration_ms: float | None = None,
) -> None:
    import time as _t
    from datetime import datetime, timezone

    event = {
        "trace_id": get_trace_id() if _CHRONICLE else None,
        "span_id": get_span_id() if _CHRONICLE else None,
        "op": "cron_decision",
        "openinference.span.kind": "CHAIN",
        "gen_ai.workflow.name": "cron_checkin",
        "gen_ai.agent.name": "hermes",
        "gen_ai.conversation.id": hermes_profile_id,
        "subject_id": subject_id,
        "gumi_instance_id": gumi_instance_id,
        "hermes_profile_id": hermes_profile_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision.value,
        "reason_codes": reason_codes,
        "gates": gates or [],
        "duration_ms": duration_ms,
        "source": (metadata or {}).get("source", "no_agent_cron"),
        "status": "ok",
    }

    # Scrivi nel JSONL esistente (retrocompatibile)
    _write_decision_event_jsonl(event)  # funzione esistente, passa event

    # Scrivi anche in Chronicle
    if _CHRONICLE:
        try:
            from relic.chronicle import get_tracer
            get_tracer().emit(event)
        except Exception:
            pass
```

### 2.4 Output `traceparent` da `make_decision()`

Alla fine di `make_decision()`, dopo la chiamata a `emit_decision_event()`, aggiungi:

```python
# Propaga trace context a Hermes via stdout (W3C traceparent)
if _CHRONICLE:
    try:
        tp = get_traceparent()
        if tp and decision == RuntimeDecision.DELIVER:
            print(f"X-Trace-Context: {tp}")
    except Exception:
        pass
```

---

## Step 3: Instrumenta `_call_llm()` in `llm_narrator.py`

**File:** `relic/gumi/llm_narrator.py`  
**Funzione target:** `_call_llm()` — linea ~439

### 3.1 Aggiungi import

```python
try:
    from relic.chronicle import start_span, sha256_hash
    _CHRONICLE = True
except Exception:
    _CHRONICLE = False
```

### 3.2 Wrappa `_call_llm()`

Identifica la struttura attuale (linee ~439-464). Il pattern è:
1. Costruisce `payload` con `model`, `messages`, `temperature`, `max_tokens`
2. Fa HTTP POST all'endpoint Ollama
3. Legge `data["choices"][0]["message"]["content"]`
4. Legge `data.get("usage", {})`

Aggiungi wrapping timing attorno alla chiamata HTTP:

```python
def _call_llm(self, prompt: str, ...) -> str:
    import time as _t
    import hashlib

    t_start = _t.monotonic()
    prompt_hash = "sha256:" + hashlib.sha256(prompt.encode()).hexdigest()[:16]

    try:
        # ... codice esistente per costruire payload e fare la chiamata ...
        response = requests.post(...)  # linea esistente
        t_end = _t.monotonic()
        total_ms = (t_end - t_start) * 1000

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        thinking_tokens = usage.get("thinking_tokens", 0)
        gen_time_s = total_ms / 1000
        tps = round(output_tokens / gen_time_s, 2) if gen_time_s > 0 and output_tokens > 0 else 0.0

        response_hash = "sha256:" + hashlib.sha256(content.encode()).hexdigest()[:16]

        if _CHRONICLE:
            try:
                from relic.chronicle import get_tracer, get_trace_id, get_span_id
                span = {
                    "trace_id": get_trace_id(),
                    "span_id": __import__("uuid").uuid4().hex[:16],
                    "parent_span_id": get_span_id(),
                    "op": "llm_call",
                    "openinference.span.kind": "LLM",
                    "gen_ai.operation.name": "chat",
                    "gen_ai.provider.name": "ollama",
                    "gen_ai.request.model": self.model,
                    "gen_ai.response.model": data.get("model", self.model),
                    "gen_ai.request.temperature": payload.get("temperature"),
                    "gen_ai.request.max_tokens": payload.get("max_tokens"),
                    "gen_ai.request.stream": False,
                    "gen_ai.response.finish_reasons": [
                        data.get("choices", [{}])[0].get("finish_reason", "stop")
                    ],
                    "gen_ai.usage.input_tokens": input_tokens,
                    "gen_ai.usage.output_tokens": output_tokens,
                    "gen_ai.usage.reasoning.output_tokens": thinking_tokens,
                    "gen_ai.usage.tokens_per_second": tps,
                    "gen_ai.response.time_to_first_chunk_ms": None,
                    "total_duration_ms": round(total_ms, 3),
                    "prompt_hash": prompt_hash,
                    "response_hash": response_hash,
                    "response_length_chars": len(content),
                    "reasoning_present": bool(data.get("choices", [{}])[0]
                                              .get("message", {}).get("reasoning")),
                    "retry_attempt": 0,
                    "call_site": f"{self.__class__.__name__}._call_llm",
                    "started_at": __import__("datetime").datetime.now(
                        __import__("datetime").timezone.utc).isoformat(),
                    "ended_at": __import__("datetime").datetime.now(
                        __import__("datetime").timezone.utc).isoformat(),
                    "error": None,
                    "status": "ok",
                }
                get_tracer().emit(span)
            except Exception:
                pass

        return content

    except Exception as exc:
        if _CHRONICLE:
            try:
                from relic.chronicle import get_tracer, get_trace_id, get_span_id
                t_end = _t.monotonic()
                span = {
                    "trace_id": get_trace_id(),
                    "span_id": __import__("uuid").uuid4().hex[:16],
                    "parent_span_id": get_span_id(),
                    "op": "llm_call",
                    "openinference.span.kind": "LLM",
                    "gen_ai.request.model": self.model,
                    "total_duration_ms": round((_t.monotonic() - t_start) * 1000, 3),
                    "prompt_hash": prompt_hash,
                    "error": type(exc).__name__,
                    "status": "error",
                    "started_at": __import__("datetime").datetime.now(
                        __import__("datetime").timezone.utc).isoformat(),
                }
                get_tracer().emit(span)
            except Exception:
                pass
        return ""  # comportamento esistente
```

---

## Step 4: Instrumenta Memory Provider

**File:** `relic/hermes_plugin/memory_provider.py`  
**Metodi target:** `prefetch()` (linea ~87), `sync_turn()` (linea ~122)

### 4.1 Import

```python
try:
    from relic.chronicle import get_tracer, get_trace_id, get_span_id
    _CHRONICLE = True
except Exception:
    _CHRONICLE = False
```

### 4.2 Wrappa `prefetch()`

Dopo la chiamata al `ContinuityService` che restituisce i marker, aggiungi:

```python
if _CHRONICLE:
    try:
        import time as _t, uuid as _uuid
        from datetime import datetime, timezone
        admitted = [m for m in markers if not m.get("blocked")]
        blocked = [m for m in markers if m.get("blocked")]
        block_reasons: dict[str, int] = {}
        for m in blocked:
            reason = m.get("block_reason", "unknown")
            block_reasons[reason] = block_reasons.get(reason, 0) + 1
        span = {
            "trace_id": get_trace_id(),
            "span_id": _uuid.uuid4().hex[:16],
            "parent_span_id": get_span_id(),
            "op": "memory_operation",
            "openinference.span.kind": "RETRIEVER",
            "operation_type": "prefetch",
            "namespace": self.namespace,
            "subject_id": self.subject_id,
            "markers_requested": len(markers),
            "markers_admitted": len(admitted),
            "markers_blocked": len(blocked),
            "block_reasons": block_reasons,
            "duration_ms": round(prefetch_duration_ms, 3),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "ok",
        }
        get_tracer().emit(span)
    except Exception:
        pass
```

### 4.3 Wrappa `sync_turn()`

```python
if _CHRONICLE:
    try:
        import uuid as _uuid
        from datetime import datetime, timezone
        span = {
            "trace_id": get_trace_id(),
            "span_id": _uuid.uuid4().hex[:16],
            "parent_span_id": get_span_id(),
            "op": "memory_operation",
            "openinference.span.kind": "TOOL",
            "operation_type": "sync_turn",
            "namespace": self.namespace,
            "subject_id": self.subject_id,
            "duration_ms": round(sync_duration_ms, 3),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "ok",
        }
        get_tracer().emit(span)
    except Exception:
        pass
```

---

## Step 5: Instrumenta Hook Dispatch

**File:** `relic/hermes_plugin/hooks.py`  
**Funzione target:** la funzione di dispatch degli hook (linee ~17-24)

### 5.1 Wrappa ogni hook call

```python
def _dispatch_hook(hook_name: str, context: dict) -> dict | None:
    handler = _REGISTERED.get(hook_name)
    if handler is None:
        return None

    t0 = __import__("time").monotonic()
    input_chars = len(str(context))
    error = None
    result = None

    try:
        result = handler(context)
    except Exception as exc:
        error = type(exc).__name__

    duration_ms = (__import__("time").monotonic() - t0) * 1000
    output_chars = len(str(result)) if result is not None else 0
    blocked = result is not None and str(result).strip().startswith("[SILENT]")

    try:
        from relic.chronicle import get_tracer, get_trace_id, get_span_id
        import uuid as _uuid
        from datetime import datetime, timezone
        span = {
            "trace_id": get_trace_id(),
            "span_id": _uuid.uuid4().hex[:16],
            "parent_span_id": get_span_id(),
            "op": "hook_execution",
            "openinference.span.kind": "GUARDRAIL",
            "hook_name": hook_name,
            "input_chars": input_chars,
            "output_chars": output_chars,
            "output_type": "context_injection" if hook_name == "pre_llm_call" else "transform",
            "blocked": blocked,
            "block_reason": "silent_response" if blocked else None,
            "duration_ms": round(duration_ms, 3),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "error": error,
            "status": "error" if error else "ok",
        }
        get_tracer().emit(span)
    except Exception:
        pass

    return result
```

---

## Step 6: Instrumenta CAC Controller

**File:** `relic/cac/controller.py`  
**Funzione target:** `evaluate()` — linea ~70

### 6.1 Aggiungi import Chronicle

```python
try:
    from relic.chronicle import get_tracer, get_trace_id, get_span_id
    _CHRONICLE = True
except Exception:
    _CHRONICLE = False
```

### 6.2 Emetti trace dopo `_write_trace()` (linea ~121)

```python
if _CHRONICLE:
    try:
        import uuid as _uuid
        from datetime import datetime, timezone
        span = {
            "trace_id": get_trace_id(),
            "span_id": _uuid.uuid4().hex[:16],
            "parent_span_id": get_span_id(),
            "op": "cac_decision",
            "openinference.span.kind": "GUARDRAIL",
            "memory_id": str(result.memory_id),
            "memory_hash": result.memory_hash,
            "severity": result.severity.value if result.severity else None,
            "decision": result.decision.value if result.decision else None,
            "skip_reason": result.skip_reason,
            "quarantine_until": str(result.quarantine_until) if result.quarantine_until else None,
            "duration_ms": round(cac_duration_ms, 3),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "status": "ok",
        }
        get_tracer().emit(span)
    except Exception:
        pass
```

---

## Step 7: Instrumenta DeliveryGate in `hermes_runtime.py`

**File:** `relic/hermes_runtime.py`  
**Classe target:** `DeliveryGate` — linea ~165  
**Metodo target:** `enforce()` — linea ~249

### 7.1 Emetti trace alla fine di `enforce()`

```python
if _CHRONICLE:
    try:
        import uuid as _uuid
        from datetime import datetime, timezone
        span = {
            "trace_id": get_trace_id(),
            "span_id": _uuid.uuid4().hex[:16],
            "parent_span_id": get_span_id(),
            "op": "delivery",
            "openinference.span.kind": "TOOL",
            "platform": platform,
            "subject_id": subject_id,
            "gate_decision": decision.value,
            "gate_reason_codes": reason_codes,
            "media_type": media_type,
            "message_length_chars": message_length,
            "duration_ms": round(delivery_duration_ms, 3),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "ok" if decision.value == "ALLOW" else "blocked",
        }
        get_tracer().emit(span)
    except Exception:
        pass
```

---

## Step 8: Configura il Viewer Phoenix

### 8.1 Aggiungi servizio `chronicle` al docker-compose (con profile opzionale)

**File:** `docker-compose.yml` (o crea `docker-compose.chronicle.yml`)

```yaml
services:
  chronicle:
    image: arizephoenix/phoenix:latest
    profiles:
      - chronicle
    ports:
      - "6006:6006"
    volumes:
      - chronicle_data:/phoenix
    environment:
      - PHOENIX_WORKING_DIR=/phoenix
    restart: unless-stopped

volumes:
  chronicle_data:
```

Avvio: `docker compose --profile chronicle up -d chronicle`

### 8.2 Configura OTLP endpoint

Per inviare trace a Phoenix, imposta prima del processo Relic:

```bash
export CHRONICLE_OTLP_ENDPOINT="http://localhost:6006/v1/traces"
```

Oppure aggiungi a `.env` del progetto.

### 8.3 Alternativa: otel-tui (no Docker)

```bash
go install github.com/ymtdzzz/otel-tui@latest
export CHRONICLE_OTLP_ENDPOINT="http://localhost:4317"
otel-tui &
```

---

## Step 9: Strumenti CLI di Query

### 9.1 Script `chronicle-query`

Crea `relic/chronicle/cli.py`:

```python
#!/usr/bin/env python3
"""CLI per query trace Chronicle."""
import argparse
import json
import sqlite3
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Query Chronicle trace store")
    sub = parser.add_subparsers(dest="cmd")

    q = sub.add_parser("query", help="Query SQLite traces")
    q.add_argument("--op", help="Filtra per op (es. llm_call, cron_decision)")
    q.add_argument("--subject", help="Filtra per subject_id")
    q.add_argument("--last", default="24h", help="Finestra temporale (es. 1h, 7d)")
    q.add_argument("--limit", type=int, default=50)
    q.add_argument("--db", default=None)

    s = sub.add_parser("stats", help="Statistiche aggregate")
    s.add_argument("--op", required=True)
    s.add_argument("--db", default=None)

    args = parser.parse_args()

    import os
    relic_home = os.environ.get("RELIC_HOME", os.path.expanduser("~/.relic"))
    db_path = args.db or str(Path(relic_home) / "chronicle" / "traces.db")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    if args.cmd == "query":
        where_clauses = []
        params = []
        if args.op:
            where_clauses.append("op = ?")
            params.append(args.op)
        if args.subject:
            where_clauses.append("subject_id = ?")
            params.append(args.subject)
        interval_map = {"1h": "1 hour", "24h": "1 day", "7d": "7 days", "30d": "30 days"}
        interval = interval_map.get(args.last, "1 day")
        where_clauses.append(f"started_at > datetime('now', '-{interval}')")
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        rows = conn.execute(
            f"SELECT * FROM spans WHERE {where_sql} ORDER BY started_at DESC LIMIT ?",
            params + [args.limit],
        ).fetchall()
        for row in rows:
            print(json.dumps(dict(row), ensure_ascii=False))

    elif args.cmd == "stats":
        rows = conn.execute(
            """
            SELECT status, COUNT(*) as count,
                   ROUND(AVG(duration_ms),1) as avg_ms,
                   ROUND(MIN(duration_ms),1) as min_ms,
                   ROUND(MAX(duration_ms),1) as max_ms
            FROM spans WHERE op = ?
            GROUP BY status
            """,
            [args.op],
        ).fetchall()
        for row in rows:
            print(json.dumps(dict(row), ensure_ascii=False))


if __name__ == "__main__":
    main()
```

Aggiungi a `setup.py` o `pyproject.toml`:
```toml
[project.scripts]
chronicle-query = "relic.chronicle.cli:main"
```

---

## Step 10: Test e Verifica

### 10.1 Test unitario del tracer

**File:** `tests/chronicle/test_tracer.py`

```python
import json
import tempfile
from pathlib import Path

import pytest

from relic.chronicle.tracer import ChronicleTracer
from relic.chronicle.context import set_trace_id


def test_span_emits_to_jsonl():
    with tempfile.TemporaryDirectory() as tmpdir:
        tracer = ChronicleTracer(chronicle_dir=Path(tmpdir))
        set_trace_id("test_trace_abc")

        with tracer.span("test_op", kind="LLM", subject_id="test") as span:
            span["gen_ai.usage.input_tokens"] = 100

        # Leggi file JSONL
        files = list(Path(tmpdir).glob("traces-*.jsonl"))
        assert len(files) == 1
        line = files[0].read_text().strip()
        data = json.loads(line)
        assert data["op"] == "test_op"
        assert data["trace_id"] == "test_trace_abc"
        assert data["gen_ai.usage.input_tokens"] == 100
        assert data["duration_ms"] >= 0
        assert data["status"] == "ok"


def test_span_fail_open_on_error():
    with tempfile.TemporaryDirectory() as tmpdir:
        tracer = ChronicleTracer(chronicle_dir=Path(tmpdir))
        with pytest.raises(ValueError):
            with tracer.span("fail_op") as span:
                raise ValueError("test error")
        # Il trace deve essere scritto comunque con status=error
        files = list(Path(tmpdir).glob("traces-*.jsonl"))
        data = json.loads(files[0].read_text().strip())
        assert data["status"] == "error"
        assert data["error"] == "ValueError"


def test_nested_spans():
    with tempfile.TemporaryDirectory() as tmpdir:
        tracer = ChronicleTracer(chronicle_dir=Path(tmpdir))
        set_trace_id("nested_trace")

        with tracer.span("parent_op") as parent:
            parent_span_id = parent["span_id"]
            with tracer.span("child_op") as child:
                assert child["parent_span_id"] == parent_span_id
                assert child["trace_id"] == "nested_trace"
```

### 10.2 Verifica integrazione end-to-end

```bash
# Avvia Phoenix
docker run -d --name chronicle-phoenix -p 6006:6006 arizephoenix/phoenix:latest

# Imposta endpoint
export CHRONICLE_OTLP_ENDPOINT="http://localhost:6006/v1/traces"

# Esegui un cron manuale
cd /home/cristina/Scrivania/relic-oss
python3 -c "
from relic.chronicle.context import set_trace_id
from relic.chronicle.tracer import new_trace_id
set_trace_id(new_trace_id())
from relic.gumi_plugin.cron_wiring import make_decision
result = make_decision('daniele', 'gumi-daniele', 'gumi-daniele')
print('Decision:', result)
"

# Verifica JSONL
ls -la ~/.relic/chronicle/
cat ~/.relic/chronicle/traces-$(date +%Y-%m-%d).jsonl | jq .

# Query SQLite
chronicle-query query --op cron_decision
chronicle-query stats --op llm_call

# Verifica Phoenix UI
open http://localhost:6006
```

### 10.3 Checklist verifica

- [ ] File JSONL creato in `~/.relic/chronicle/traces-{today}.jsonl`
- [ ] SQLite creato in `~/.relic/chronicle/traces.db`
- [ ] `trace_id` consistente attraverso cron_decision → llm_call → memory_operation
- [ ] `parent_span_id` corretto per ogni span figlio
- [ ] Nessun contenuto raw di prompt/risposta nei trace
- [ ] Phoenix UI mostra trace a `http://localhost:6006`
- [ ] `chronicle-query stats --op llm_call` restituisce avg_ms, min_ms, max_ms
- [ ] Failure nel tracer non blocca il percorso principale (test: rimuovi write permission su ~/.relic/chronicle/)

---

---

## Step 11: Conversation Turn Tracing

### 11.1 Dove hookarsi

Hermes gestisce ogni messaggio in entrata/uscita attraverso il suo sistema di routing. Il punto di injection per il turn tracing è l'hook `post_llm_call` (fire-and-forget) e l'eventuale hook di ricezione messaggi (se disponibile).

Se non esiste un hook di ricezione, il turn tracing si basa su:
1. **Messaggi agent:** ogni LLM call che produce output non-SILENT → turn agente tracciato contestualmente al `LLMCallTrace`
2. **Messaggi subject:** il pre_llm_call hook riceve il messaggio del subject come parte del context — si può estrarne la lunghezza (non il contenuto)

### 11.2 Codice da aggiungere a `hermes_plugin/hooks.py`

Nell'hook `post_llm_call`, che è fire-and-forget, aggiungi:

```python
def _trace_conversation_turn(
    *,
    session_id: str,
    subject_id: str,
    hermes_profile_id: str,
    author: str,
    message_length_chars: int,
    previous_message_ts: str | None,
    is_proactive: bool,
    hour_of_day: int,
    day_of_week: int,
) -> None:
    """Emette un ConversationTurnTrace. Chiamata fire-and-forget."""
    try:
        import uuid
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        response_latency_ms = None
        if previous_message_ts:
            prev_dt = datetime.fromisoformat(previous_message_ts)
            response_latency_ms = (now - prev_dt).total_seconds() * 1000

        from relic.chronicle import get_tracer, get_trace_id, get_span_id
        span = {
            "trace_id": get_trace_id(),
            "span_id": uuid.uuid4().hex[:16],
            "parent_span_id": get_span_id(),
            "op": "conversation_turn",
            "openinference.span.kind": "CHAIN",
            "session_id": session_id,
            "subject_id": subject_id,
            "hermes_profile_id": hermes_profile_id,
            "author": author,
            "message_length_chars": message_length_chars,
            "response_latency_ms": response_latency_ms,
            "response_latency_h": round(response_latency_ms / 3600000, 2) if response_latency_ms else None,
            "is_proactive": is_proactive,
            "hour_of_day": hour_of_day,
            "day_of_week": day_of_week,
            "started_at": now.isoformat(),
            "status": "ok",
        }
        get_tracer().emit(span)
    except Exception:
        pass
```

### 11.3 Estrai session_id dal contesto Hermes

Hermes mantiene un session ID per ogni conversazione. Localizzarlo in `hermes_runtime.py` (cerca `session_id` o equivalente) e propagarlo a `ConversationTurnTrace`. Se non esiste un session_id stabile, generarne uno come `SHA256(profile_id + date)[0:16]`.

### 11.4 Calcolo response_latency per messaggi subject

Nel `pre_llm_call` hook, il messaggio del subject è disponibile (almeno la sua lunghezza). Recupera il timestamp dell'ultimo messaggio agent da Chronicle SQLite:

```python
def _get_last_agent_message_ts(subject_id: str) -> str | None:
    """Legge da SQLite l'ultimo messaggio agent per il subject."""
    try:
        import sqlite3, os
        from pathlib import Path
        relic_home = os.environ.get("RELIC_HOME", os.path.expanduser("~/.relic"))
        db = Path(relic_home) / "chronicle" / "traces.db"
        conn = sqlite3.connect(str(db))
        row = conn.execute(
            """SELECT started_at FROM spans
               WHERE op = 'conversation_turn'
                 AND subject_id = ?
                 AND json_extract(attributes, '$.author') = 'agent'
               ORDER BY started_at DESC LIMIT 1""",
            [subject_id],
        ).fetchone()
        return row[0] if row else None
    except Exception:
        return None
```

---

## Step 12: Topic Classification

Il topic classifier gira in modo **asincrono** rispetto al percorso principale. Non deve mai bloccare la delivery.

### 12.1 `relic/chronicle/topic_classifier.py`

```python
"""
Topic classifier asincrono per Chronicle.
Legge l'ultimo turn da SQLite, classifica con LLM leggero, scrive TopicTrace.
NON accede al contenuto raw dei messaggi — solo metadati aggregati per sessione.
"""
import hashlib
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

TOPIC_TAXONOMY = [
    "personal_life", "work_creative", "music_performance",
    "food_cooking", "spiritual_practice", "relationships",
    "emotional_state", "future_plans", "current_events",
    "meta_conversation", "practical_logistics",
]

CLASSIFIER_PROMPT = """Sei un sistema di classificazione topic per conversazioni.
Analizza il seguente estratto (solo metadati, non contenuto raw) e assegna fino a 3 topic dalla lista:
{taxonomy}

Metadati sessione:
- Turni totali: {turns}
- Lunghezze messaggi (chars): subject={subject_chars}, agent={agent_chars}
- Ora del giorno: {hour}
- Giorno settimana: {dow}

Restituisci SOLO JSON: {{"topics": ["topic1", "topic2"], "confidence": {{"topic1": 0.9, "topic2": 0.7}}}}
"""


def classify_session_topics_async(
    session_id: str,
    subject_id: str,
    hermes_profile_id: str,
    session_metadata: dict,
    llm_endpoint: str,
    model: str,
) -> None:
    """Fire-and-forget: classifica topic in background thread."""
    def _run():
        try:
            _do_classify(session_id, subject_id, hermes_profile_id,
                         session_metadata, llm_endpoint, model)
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()


def _do_classify(
    session_id: str,
    subject_id: str,
    hermes_profile_id: str,
    metadata: dict,
    llm_endpoint: str,
    model: str,
) -> None:
    import requests

    prompt = CLASSIFIER_PROMPT.format(
        taxonomy=", ".join(TOPIC_TAXONOMY),
        turns=metadata.get("total_turns", 0),
        subject_chars=metadata.get("avg_subject_chars", 0),
        agent_chars=metadata.get("avg_agent_chars", 0),
        hour=metadata.get("hour_of_day", 0),
        dow=metadata.get("day_of_week", 0),
    )

    try:
        resp = requests.post(
            f"{llm_endpoint}/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 150,
            },
            timeout=10,
        )
        content = resp.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        topics = parsed.get("topics", [])
        confidence = parsed.get("confidence", {})
        usage = resp.json().get("usage", {})
    except Exception:
        return

    from relic.chronicle import get_tracer
    span = {
        "trace_id": hashlib.sha256(session_id.encode()).hexdigest()[:32],
        "span_id": uuid.uuid4().hex[:16],
        "parent_span_id": None,
        "op": "topic_classification",
        "openinference.span.kind": "LLM",
        "session_id": session_id,
        "subject_id": subject_id,
        "hermes_profile_id": hermes_profile_id,
        "topics_detected": topics,
        "topic_confidence": confidence,
        "dominant_topic": topics[0] if topics else None,
        "classifier_model": model,
        "classifier_tokens": usage.get("total_tokens", 0),
        "classified_at": datetime.now(timezone.utc).isoformat(),
        "status": "ok",
    }
    get_tracer().emit(span)
```

### 12.2 Trigger del classifier

Alla fine di ogni sessione (quando il `session.ended_by` è settato), chiama:
```python
from relic.chronicle.topic_classifier import classify_session_topics_async
classify_session_topics_async(
    session_id=session.session_id,
    subject_id=subject_id,
    hermes_profile_id=hermes_profile_id,
    session_metadata={
        "total_turns": session.total_turns,
        "avg_subject_chars": session.subject_message_avg_chars,
        "avg_agent_chars": session.agent_message_avg_chars,
        "hour_of_day": session.start_hour,
        "day_of_week": session.start_dow,
    },
    llm_endpoint=os.environ.get("OLLAMA_ENDPOINT", "http://localhost:11434/v1"),
    model=os.environ.get("CHRONICLE_CLASSIFIER_MODEL", "qwen3.5-plus"),
)
```

---

## Step 13: Engagement Snapshot Job

### 13.1 `relic/chronicle/engagement_analytics.py`

```python
"""
Calcola metriche aggregate di engagement da SQLite Chronicle.
Eseguito periodicamente (ogni 6 ore) come cron job separato.
"""
import json
import os
import sqlite3
import statistics
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path


def compute_engagement_snapshot(
    subject_id: str,
    hermes_profile_id: str,
    period_days: int = 7,
    db_path: str | None = None,
) -> dict:
    relic_home = os.environ.get("RELIC_HOME", os.path.expanduser("~/.relic"))
    db = db_path or str(Path(relic_home) / "chronicle" / "traces.db")
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    since = (datetime.now(timezone.utc) - timedelta(days=period_days)).isoformat()

    # Sessioni nel periodo
    sessions = conn.execute(
        """SELECT * FROM spans
           WHERE op = 'conversation_session'
             AND subject_id = ?
             AND started_at > ?""",
        [subject_id, since],
    ).fetchall()

    # Turn del subject
    subject_turns = conn.execute(
        """SELECT * FROM spans
           WHERE op = 'conversation_turn'
             AND subject_id = ?
             AND json_extract(attributes, '$.author') = 'subject'
             AND started_at > ?""",
        [subject_id, since],
    ).fetchall()

    # Turn dell'agent
    agent_turns = conn.execute(
        """SELECT * FROM spans
           WHERE op = 'conversation_turn'
             AND subject_id = ?
             AND json_extract(attributes, '$.author') = 'agent'
             AND started_at > ?""",
        [subject_id, since],
    ).fetchall()

    # Decisioni cron
    cron_decisions = conn.execute(
        """SELECT decision, COUNT(*) as cnt FROM spans
           WHERE op = 'cron_decision'
             AND subject_id = ?
             AND started_at > ?
           GROUP BY decision""",
        [subject_id, since],
    ).fetchall()

    # Calcola latenze subject
    subject_latencies_h = [
        row["attributes"] and json.loads(row["attributes"]).get("response_latency_h")
        for row in subject_turns
    ]
    subject_latencies_h = [x for x in subject_latencies_h if x is not None and x > 0]

    # Metriche sessioni
    n_sessions = len(sessions)
    agent_initiated = sum(
        1 for s in sessions
        if json.loads(s["attributes"] or "{}").get("initiator") == "agent"
    )

    # Metriche cron
    cron_by_decision = {row["decision"]: row["cnt"] for row in cron_decisions}
    delivered = cron_by_decision.get("DELIVER", 0)
    silent = cron_by_decision.get("NO_REPLY_SILENT", 0)
    total_cron = sum(cron_by_decision.values())

    # LLM metrics
    llm_spans = conn.execute(
        """SELECT duration_ms,
                  json_extract(attributes, '$."gen_ai.usage.tokens_per_second"') as tps,
                  json_extract(attributes, '$."gen_ai.context_fill_ratio"') as fill
           FROM spans
           WHERE op = 'llm_call'
             AND subject_id = ?
             AND started_at > ?""",
        [subject_id, since],
    ).fetchall()

    tps_values = [r["tps"] for r in llm_spans if r["tps"]]
    latency_values = [r["duration_ms"] for r in llm_spans if r["duration_ms"]]
    fill_values = [r["fill"] for r in llm_spans if r["fill"]]

    snapshot = {
        "trace_id": uuid.uuid4().hex,
        "span_id": uuid.uuid4().hex[:16],
        "op": "engagement_snapshot",
        "subject_id": subject_id,
        "hermes_profile_id": hermes_profile_id,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "period_days": period_days,
        "sessions_count": n_sessions,
        "total_turns": len(subject_turns) + len(agent_turns),
        "agent_initiated_sessions": agent_initiated,
        "subject_initiated_sessions": n_sessions - agent_initiated,
        "initiative_ratio": round(agent_initiated / n_sessions, 2) if n_sessions else None,
        "subject_response_rate": round(len(subject_latencies_h) / len(agent_turns), 2)
            if agent_turns else None,
        "subject_p50_response_latency_h": round(statistics.median(subject_latencies_h), 2)
            if subject_latencies_h else None,
        "subject_p90_response_latency_h": round(
            sorted(subject_latencies_h)[int(len(subject_latencies_h) * 0.9)], 2
        ) if len(subject_latencies_h) >= 5 else None,
        "avg_session_depth_turns": round(
            (len(subject_turns) + len(agent_turns)) / n_sessions, 1
        ) if n_sessions else None,
        "cron_windows_available": total_cron,
        "cron_windows_delivered": delivered,
        "cron_silent_rate": round(silent / total_cron, 3) if total_cron else None,
        "delivery_window_utilization": round(delivered / total_cron, 3) if total_cron else None,
        "context_fill_ratio_avg": round(statistics.mean(fill_values), 3) if fill_values else None,
        "llm_avg_tps": round(statistics.mean(tps_values), 1) if tps_values else None,
        "llm_avg_latency_ms": round(statistics.mean(latency_values), 1) if latency_values else None,
        "status": "ok",
    }

    # Emetti snapshot
    from relic.chronicle import get_tracer
    get_tracer().emit(snapshot)

    # Controlla alert
    _check_alerts(snapshot, conn, subject_id)

    return snapshot


def _check_alerts(snapshot: dict, conn, subject_id: str) -> None:
    """Emette AlertTrace per condizioni anomale."""
    alerts = []

    p50 = snapshot.get("subject_p50_response_latency_h")
    if p50 and p50 > 12:
        alerts.append({
            "alert_type": "engagement_decay",
            "severity": "warning",
            "metric": "subject_p50_response_latency_h",
            "current_value": p50,
            "threshold": 12,
        })

    silent_rate = snapshot.get("cron_silent_rate")
    if silent_rate and silent_rate > 0.35:
        alerts.append({
            "alert_type": "silent_rate_high",
            "severity": "warning",
            "metric": "cron_silent_rate",
            "current_value": silent_rate,
            "threshold": 0.35,
        })

    fill = snapshot.get("context_fill_ratio_avg")
    if fill and fill > 0.85:
        alerts.append({
            "alert_type": "context_pressure",
            "severity": "critical",
            "metric": "context_fill_ratio_avg",
            "current_value": fill,
            "threshold": 0.85,
        })

    initiative = snapshot.get("initiative_ratio")
    if initiative and initiative > 0.90:
        alerts.append({
            "alert_type": "initiative_imbalance",
            "severity": "warning",
            "metric": "initiative_ratio",
            "current_value": initiative,
            "threshold": 0.90,
        })

    from relic.chronicle import get_tracer
    from datetime import datetime, timezone
    import uuid
    for alert in alerts:
        span = {
            "trace_id": uuid.uuid4().hex,
            "span_id": uuid.uuid4().hex[:16],
            "op": "chronicle_alert",
            "subject_id": subject_id,
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "status": "ok",
            **alert,
        }
        get_tracer().emit(span)
```

### 13.2 Registra come cron job Hermes

Aggiungi a `hermes cron edit` un nuovo job:

```json
{
  "name": "chronicle_engagement_snapshot",
  "schedule": "0 */6 * * *",
  "script": "relic_chronicle_snapshot.sh",
  "profile": "gumi-daniele",
  "enabled": true
}
```

Script `~/.hermes/scripts/daniele/relic_chronicle_snapshot.sh`:
```bash
#!/bin/bash
python3 -c "
from relic.chronicle.engagement_analytics import compute_engagement_snapshot
snapshot = compute_engagement_snapshot('daniele', 'gumi-daniele', period_days=7)
print('Snapshot computed:', snapshot.get('sessions_count'), 'sessions')
"
```

---

## Step 14: Context Fill Ratio

Aggiungi questo attributo a ogni `LLMCallTrace` (Step 3). Richiede conoscenza del `max_context_tokens` del modello.

Nel `_call_llm()`, dopo aver letto `input_tokens` da `usage`:

```python
max_ctx = self.context_length or 1_000_000  # dal config
context_fill_ratio = round(input_tokens / max_ctx, 4) if max_ctx and input_tokens else None
# Aggiungi allo span LLM:
span["gen_ai.context_fill_ratio"] = context_fill_ratio
```

---

## Ordine di Implementazione Consigliato

```
── CORE INFRASTRUCTURE ──
Step 1  → relic/chronicle/ module (prerequisito di tutto)
Step 8  → Docker compose viewer (Phoenix — utile da subito)

── DECISION & LLM PIPELINE ──
Step 2  → cron_wiring.py (gate timing, decision trace)
Step 3  → llm_narrator.py (token/timing/tps/context_fill)
Step 14 → context_fill_ratio in LLMCallTrace
Step 4  → memory_provider.py
Step 5  → hooks.py (intervention rate)
Step 6  → cac/controller.py
Step 7  → hermes_runtime.py DeliveryGate

── CONVERSATION ANALYTICS ──
Step 11 → conversation_turn tracing (response latency, author, length)
Step 12 → topic_classifier.py (async, fire-and-forget)

── AGGREGATE ANALYTICS ──
Step 13 → engagement_analytics.py + cron snapshot + alert detection
Step 9  → CLI chronicle-query

── VERIFICATION ──
Step 10 → Test suite
```

**Stima complessità per step (in ore agente):**

| Step | Complessità | Note |
|------|------------|------|
| 1 | 1h | Nuovo modulo, nessuna dipendenza |
| 2 | 2h | Refactor firma _evaluate_decision + 7 gate wrap |
| 3 | 1.5h | Wrap _call_llm con timing |
| 4-7 | 1h ciascuno | Pattern ripetitivo |
| 8 | 0.5h | docker-compose edit |
| 9 | 1h | CLI semplice |
| 10 | 1.5h | Test suite |
| 11 | 2h | Dipende da come Hermes espone session_id |
| 12 | 1.5h | Classifier asincrono |
| 13 | 2h | Analytics + alert logic |
| 14 | 0.5h | Una riga in _call_llm |

---

## Variabili di Configurazione

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `CHRONICLE_OTLP_ENDPOINT` | non impostata (no OTLP) | URL endpoint OTLP (Phoenix/Jaeger) |
| `RELIC_HOME` | `~/.relic` | Directory base per tutti i file Relic |
| `CHRONICLE_DISABLED` | non impostata | Se impostata a `1`, disabilita tutto il tracing |

---

## Note per l'Agente

- **Non modificare** la logica di business esistente. Chronicle è puramente osservazionale.
- Se `get_trace_id()` restituisce `None`, crea un nuovo trace_id con `new_trace_id()` e impostalo con `set_trace_id()`. Questo avviene naturalmente nel `ChronicleTracer.span()`.
- Il campo `parent_span_id` può essere `None` per root span. Non è un errore.
- Per cron job (processo separato), ogni invocazione è un root span senza parent.
- `gen_ai.conversation.id` deve essere impostato al `hermes_profile_id` per correlare eventi dello stesso profilo nel tempo.
- I `scoring_factors` nel CACDecisionTrace sono float tra 0.0 e 1.0. Non loggare il testo che ha determinato il punteggio.
