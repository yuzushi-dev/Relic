# T002 — PrivacyTrace Reconciliation Proposal

**Task:** T002 — PrivacyTrace reconciliation proposal  
**Data:** 2026-05-16  
**Stato:** decisione architetturale — NESSUN codice modificato in questo documento  
**Dipendenza:** T001 (INVENTORY.md)  
**Blocks:** T010 (Pydantic schema), T012 (redaction), T013 (consent gate), T014 (emitter), e tutti i Phase 3 integration tasks

---

## 1. Context — i due PrivacyTrace

Sono state identificate due classi `PrivacyTrace` in codebase:

| | **Opzione A** | **Opzione B** |
|--|--|--|
| **Path** | `relic/privacy/trace.py` | `relic/persistence.py:84` |
| **Design** | `@dataclass` | Pydantic model |
| **Usato da** | `relic/privacy/gateway.py` (legacy PR04) | `relic/privacy_gate.py` (attivo), `MemoryPersistence.store()` |
| **Schema** | `decision_id`, `decision`, `category`, `confidence`, `redacted`, `rehydration_blocked`, `final_output_blocked`, `timestamp`, `metadata` | `trace_id`, `stage`, `content_hash`, `privacy_level: PrivacyLevel`, `policy_applied`, `timestamp`, `rehydration_context` |
| **PrivacyLevel** | ❌ assente | ✅ `PrivacyLevel` enum (S0/S1/S2/SAFE) |
| **Hash contenuto** | ❌ assente | ✅ SHA-256 |
| **Stage tracking** | ❌ assente | ✅ (input_scan / rehydration / output_gate) |
| **Rehydration blocked** | ✅ | ❌ assente |
| **Dataclass fields** | ✅ | ✅ |

### 1.1 Perché esistono due versioni

- **Opzione A** (`privacy/trace.py`): introdotta con PR04 come schema minimale per il privacy gateway. Dataclass, leggera, orientata decisioni testuali del gateway.
- **Opzione B** (`persistence.py`): introdotta successivamente come parte del sistema `MemoryPersistence` per tracciare ogni block memory con privacy level + content hash.

### 1.2 Catene di import

```
Opzione A chain:
  relic/privacy/__init__.py      → exporta PrivacyTrace, write_trace
  relic/privacy/gateway.py       → import PrivacyTrace, write_trace (producono privacy_trace.jsonl)
  T024 legacy migration         → legge privacy_trace.jsonl

Opzione B chain:
  relic/persistence.py           → PrivacyTrace è definito qui (inline, non re-exportato)
  relic/privacy_gate.py          → import PrivacyTrace, PrivacyLevel (attivo, production)
  MemoryPersistence.store()      → crea PrivacyTrace Opzione B per ogni block
  MemoryPersistence._append_trace() → scrive in privacy_trace.jsonl
  T024 legacy migration          → deve distinguere i due formati
```

**Importante:** `relic/privacy_gate.py` usa Opzione B. `relic/privacy/gateway.py` usa Opzione A. Entrambi scrivono in `~/.relic/privacy_trace.jsonl` MA con schemi diversi. Questo è un bug reale — il file contiene righe con schema misto.

---

## 2. Analisi — quale mantenere come canonico

### 2.1 Criteri di valutazione

| Criterio | Opzione A | Opzione B | Punteggio |
|----------|-----------|-----------|-----------|
| PrivacyLevel integrato | ❌ assente — servirebbe join esterno | ✅ first-class | B +1 |
| Stage tracking (input/rehydration/output) | ❌ assente | ✅ serve per audit completo | B +1 |
| Content hash per deduplicazione | ❌ assente | ✅ essenziale per Chronicle | B +1 |
| Usato da production privacy gate | ❌ solo legacy gateway | ✅ `privacy_gate.py` (attivo) | B +1 |
| Pydantic model (validation, serialization) | ❌ dataclass | ✅ Pydantic | B +1 |
| Dipendenze esistenti (quanti file lo importano) | 2 (`privacy/__init__.py`, `privacy/gateway.py`) | 1 (`privacy_gate.py`) | pari |
| Compatibilità con Chronicle events | richiede arricchimento esterno | già pronto | B +1 |
| Schema stabile (quante versioni) | v1 | v1 | pari |

### 2.2 Verdetto: **Opzione B (`relic/persistence.py:PrivacyTrace`) è il source-of-truth canonico**

**Ragioni decisive:**
1. `relic/privacy_gate.py` è il modulo attivo per il privacy gate — Opzione B è già integrata con `PrivacyLevel` (S0/S1/S2/SAFE), che è esattamente il sensitivity label di Chronicle.
2. Stage tracking (`input_scan` → `rehydration` → `output_gate`) è essenziale per ricostruire la catena di decisioni privacy. Opzione A non ha questo concetto.
3. Content hash (SHA-256) è prerequisito per deduplicazione eventi e per il `payload_hash` di Chronicle. Opzione A non lo fornisce.
4. Pydantic model offre validation + serialization integrata — meglio del mix dataclass + `asdict()`.

**Opzione A viene deprecata ma conservata** per T024 (legacy migration — deve leggere `privacy_trace.jsonl` che contiene righe Opzione A). Post-T024, `relic/privacy/trace.py` può essere deprecato ufficialmente.

---

## 3. Piano di migrazione

### Fase 1 — Immediate (T002 output)

1. **Documentare** questo documento come decisione architetturale (fatto).
2. **Nessun codice modificato** ora — la migrazione avviene in T010 e T024.

### Fase 2 — T010 (Pydantic schema models)

`relic/chronicle/schema.py` importa:
```python
from relic.persistence import PrivacyLevel  # ✅ source-of-truth
# NON importare PrivacyTrace da qui — Chronicle emette Event, non PrivacyTrace
```

Il campo `event.sensitivity: PrivacyLevel` usa esattamente l'enum canonico. Nessuna copia locale.

### Fase 3 — T024 (legacy JSONL migration)

Il migration adapter per `privacy_trace.jsonl` deve:
1. Distinguere righe Opzione A (hanno campo `decision`, `category`, `confidence`) da righe Opzione B (hanno `stage`, `content_hash`, `privacy_level`).
2. Convertire entrambi i formati in `Event(event_type="privacy_decision", ...)`:
   - Opzione A: map `decision` → `payload["decision"]`, infer privacy_level da `metadata` o default S2.
   - Opzione B: map direttamente `privacy_level` → `sensitivity`, `stage` → `payload["stage"]`.
3. Idempotenza: skip se `payload_hash` (SHA-256 di `json.dumps(row, sort_keys=True)`) già presente.

### Fase 4 — Post Phase 1 (opzionale, fuori scope T0xx attuali)

Deprecare ufficialmente `relic/privacy/trace.py`:
1. Avviso in docstring che Opzione A è deprecated.
2. `relic/privacy/gateway.py` migrato a Opzione B (proporre PR separato).
3. Rimuovere re-export da `relic/privacy/__init__.py`.

**Non fare ora.** Rischio: potrebbe rompere qualcosa non coperto da test. Valutare in Phase 5.

---

## 4. Tabella mapping — Opzione A → Opzione B (per T024)

| Opzione A field | Opzione B field | Note |
|-----------------|-----------------|------|
| `decision_id` | `trace_id` | rename semantico |
| `decision` | — | va in `payload["gateway_decision"]` |
| `category` | — | va in `payload["content_category"]` |
| `confidence` | — | va in `payload["decision_confidence"]` |
| `redacted` | — | va in `payload["redacted"]` |
| `rehydration_blocked` | — | va in `payload["rehydration_blocked"]` |
| `final_output_blocked` | — | va in `payload["final_output_blocked"]` |
| `timestamp` | `timestamp` | pari |
| `metadata` | — | flatten in `payload["metadata"]` |
| — | `stage` | non presente in A → default `"unknown"` |
| — | `content_hash` | non presente in A → calcolato da payload JSON canonico |
| — | `privacy_level` | non presente in A → inferito da `redacted` + `final_output_blocked` |
| — | `policy_applied` | non presente in A → `"legacy_pr04"` |

### PrivacyLevel inference da Opzione A

```
if final_output_blocked → S0_HARD_VIOLATION
elif rehydration_blocked → S1_QUARANTINE
elif redacted → S2_WARNING
else → SAFE
```

---

## 5. Import path per Phase 1 (T010-T015)

```python
# ✅ CORRETTO
from relic.persistence import PrivacyLevel

# ❌ SBAGLIATO — Opzione A non ha PrivacyLevel
from relic.privacy.trace import PrivacyTrace  # usare solo in T024
```

Per `write_trace()` (legacy migration only):
```python
# Solo in T024, per leggere privacy_trace.jsonl legacy
from relic.privacy.trace import write_trace as legacy_write_trace
```

---

## 6. Open questions (ancora da risolvere)

1. **Dual schema in `privacy_trace.jsonl`**: dopo che T024 converte le righe Opzione A, il file `privacy_trace.jsonl` conterrà ancora righe Opzione B (scritte da `MemoryPersistence`). Il migration è solo one-way (JSONL → SQLite). Non riscriviamo il JSONL. Accettabile?

2. **`relic/privacy/gateway.py` → Opzione B**: questo gateway è ancora usato in qualche path di produzione o è già sostituito da `relic/privacy_gate.py`? Se è ancora active, serve migration PR prima di deprecare Opzione A. **Servono test esistenti per verificarlo.**

3. **`privacy_trace.jsonl` path**: è in `~/.relic/privacy_trace.jsonl` (root) o in `~/.relic/subjects/<id>/privacy_trace.jsonl` (per subject)? Dipende da dove `MemoryPersistence._append_trace()` scrive. Verificare in `relic/persistence.py:_append_trace`.

---

## 7. Decisione finale

| Scelta | Decisione |
|--------|-----------|
| **Source-of-truth PrivacyTrace** | Opzione B — `relic/persistence.py:PrivacyTrace` |
| **Source-of-truth PrivacyLevel** | `relic/persistence.py:PrivacyLevel` (già era così) |
| **Opzione A deprecation** | conservata per T024, deprecata post Phase 1 |
| **Chronicle schema import** | `from relic.persistence import PrivacyLevel` |
| **Migration legacy JSONL** | T024 gestisce entrambi i formati |

**Implementazione immediata:** T010 importa `PrivacyLevel` da `relic.persistence`. Fine.

---

*Documento generato da T002 (2026-05-16). Nessun codice modificato.*
