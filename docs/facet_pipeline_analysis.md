# Facet Pipeline: Analisi, Gap e Raccomandazioni

**Data**: 2026-05-15  
**Autore**: analisi automatica da backup `2026-04` + codebase `relic-oss`  
**Stato**: documento di lavoro interno

---

## Contesto: cos'è Relic e cosa sono i facets

Relic è un layer di governance e modellazione longitudinale per agenti relazionali. L'obiettivo è costruire nel tempo un profilo comportamentale del soggetto — non tramite un questionario fatto una volta sola, ma attraverso l'accumulo progressivo di osservazioni ricavate dalle interazioni reali con l'agente.

**Gumi** è l'agente diegetico generato da Relic per un soggetto specifico: ha una sua voce, routine, storia, ed è capace di prendere iniziativa (messaggi proattivi, audio, immagini, continuità narrativa). Gumi non è un'interfaccia trasparente a Relic — ha la sua autonomia — ma le sue interazioni con il soggetto sono la fonte primaria di dati per aggiornare il profilo.

I **facets** sono le dimensioni di modellazione longitudinale. Sono derivati da framework teorici stabiliti:

- *Big Five* / *HEXACO* (psicologia della personalità)
- *Attachment Theory* (stile relazionale, ansia/evitamento)
- *Self-Determination Theory* (autonomia, competenza, relazionalità)
- *Dual-Process Theory* (System 1/2, firme comportamentali)

Ogni facet è rappresentato come una posizione continua su uno spettro bipolare (es. `openness`: 0.0 → chiuso, 1.0 → aperto). Ogni posizione porta con sé un **confidence score** (0.0–1.0) e un **observation count**. Il sistema non pretende certezza: i facets sono dimensioni ispezionabili per osservazione, generazione di ipotesi e correzione — non scale cliniche né diagnosi.

Il soggetto attuale (`daniele`) ha 18 facets inizializzati al bootstrap (7 psicologici + 11 di preferenza interazione), tutti con `confidence: "low_initial"`. Il totale previsto a regime è ~60 dimensioni.

---

## Parte 1 — Il sistema vecchio: architettura e comportamento

> Fonte: backup `/home/cristina/Scrivania/backup_macchina/home/cristina/.hermes/profiles/gumi/workspace/scripts/`  
> Periodo di riferimento: fino ad aprile 2026

### 1.1 Due store di profilo separati

Il sistema vecchio manteneva **due rappresentazioni parallele** del soggetto:

**`subject_baseline.json`** (Relic-side, strutturato, per il ricercatore):
```json
{
  "psychological": {
    "openness":     { "value": 0.5,   "confidence": "low_initial" },
    "extraversion": { "value": 0.083, "confidence": "low_initial" }
  },
  "interaction": {
    "checkin_tolerance": { "value": 0.45, "confidence": "low_initial" }
  }
}
```

**`daniele_profile.json`** (Gumi-side, operativo, per il motore check-in):
```json
{
  "records": [
    {
      "id": "mem-20260226-001",
      "categoria": "obiettivi",
      "contenuto": "Daniele preferisce utilità concreta senza filler performativo.",
      "confidenza": 0.88,
      "stato": "attivo",
      "priority_rank": 3,
      "fonte": "file:SOUL.md",
      "ultimo_aggiornamento": "2026-02-26",
      "sensitivity": "bassa"
    }
  ]
}
```

I due store non erano sincronizzati. Il baseline veniva scritto al bootstrap e non aggiornato; `daniele_profile.json` era il vero store operativo dove l'esperienza accumulata finiva.

### 1.2 Il motore di selezione topic: `gumi_topic_gap_score.py`

Il cuore del sistema era un motore di scoring che decideva **quale aspetto del soggetto chiedere a Gumi di esplorare**, in base a quanto era ancora sconosciuto.

La formula centrale:

```python
# gumi_topic_gap_score.py
score = 0.35 * unknownness    \
      + 0.25 * impact         \
      + 0.20 * timeliness     \
      - 0.20 * intrusion      \
      - 0.15 * asked_recently
score = clamp(score)  # [0.0, 1.0]
```

Cinque bucket topic predefiniti con base_impact e sensitivity diversi:

```python
TOPICS = (
    TopicDef("priorita_reali",         base_impact=0.90, sensitivity="media"),
    TopicDef("energia_stress",         base_impact=0.84, sensitivity="alta"),
    TopicDef("relazione_calibrazione", base_impact=0.78, sensitivity="alta"),
    TopicDef("routine_benessere",      base_impact=0.72, sensitivity="media"),
    TopicDef("stile_decisionale",      base_impact=0.80, sensitivity="media"),
)
```

Il driver primario era `unknownness` — calcolata a partire dai record di `daniele_profile.json`:

```python
def compute_unknownness(relevant_records, now):
    if not relevant_records:
        return 1.0   # nessun record = massima priorità di esplorazione

    active = [r for r in relevant_records if r.get("stato") == "attivo"]
    
    # Coverage: confidenza media e numero di record attivi
    mean_conf      = mean([float(r.get("confidenza", 0.5)) for r in active]) if active else 0.0
    coverage_count = clamp(len(active) / 3.0)

    # Stale: giorni trascorsi dall'ultimo aggiornamento
    stale_factor = clamp(mean_stale_days / 30.0)

    # Verifica: record segnalati come da verificare
    verify_ratio = len(da_verificare) / max(1, len(relevant_records))

    unknown = 1.0 - (0.65 * mean_conf + 0.35 * coverage_count)
    unknown += 0.25 * stale_factor + 0.20 * verify_ratio
    return clamp(unknown)
```

Effetto pratico: topic con pochi record, bassa confidenza, o vecchi → `unknownness` alta → selezionato per il prossimo check-in. Topic esplorati di recente e con confidenza alta → declassati automaticamente.

### 1.3 Generazione della domanda: `gumi_personal_checkin.py`

Quando il motore decideva `status: "ask_now"`, il check-in procedeva in questi passi:

**Step 1 — Gate temporale**: finestre di invio, spaziatura minima, quiet hours.
```python
windows = ["09:30-12:30", "15:00-19:30", "21:00-22:30"]
min_spacing_minutes = 240
target_max_per_day  = 3
quiet_hours = {"start": "23:00", "end": "08:00"}
```

**Step 2 — Selezione micro-style**: 6 registri rotativi per evitare ripetitività.
```python
MICRO_STYLES = {
    "osservazione_tenera": "apri con una piccola osservazione tenera o curiosa, poi fai la domanda",
    "curiosita_obliqua":   "entra di lato, con una curiosità obliqua e concreta invece che frontale",
    "presenza_calda":      "suona presente e calda, come se stessi già un po' dentro la sua giornata",
    "taglio_nitido":       "più nitida e diretta, ma sempre affettuosa",
    "invito_morbido":      "usa un invito morbido, non pressante, che lasci spazio",
    "gancio_sensoriale":   "parti da una sensazione, un dettaglio o un'immagine quotidiana",
}
# Rotazione deterministica: evita lo stesso stile due volte consecutive
start = (sum(ord(ch) for ch in selected_facet) + len(ranking)) % len(options)
```

**Step 3 — Anti-repeat gate** (`anti_repeat.py`): blocca se Jaccard similarity > 0.85 con domande recenti; per ogni "archetipo" (leggerezza, ondate, movimento, ridicolo) max 2 usi/24h.

**Step 4 — LLM call**: prompt strutturato con contesto profilo (top 6 record attivi da `daniele_profile.json` + estratti da `SOUL.md` + ultimi 3 scambi da `checkin_exchanges`), inviato a `nvidia-nim/meta/llama-4-maverick-17b-128e-instruct` con fallback.

**Step 5 — Delivery + record**:
```python
# Invio Telegram diretto via Bot API
tg_resp = _send_telegram_direct(token, chat_id, message)
message_id = str(tg_resp["result"]["message_id"])

# Log in relic.db
record_checkin(selected_facet, message, message_id)
# → INSERT INTO checkin_exchanges (facet, question_text, message_id, asked_at)
```

**Step 6 — Aggiornamento stato**: `apply_gate_state()` incrementa `sent_today`, aggiorna `last_sent_at`, appende a `history`.

### 1.4 Consolidamento profilo: `gumi_profile_consolidation.py`

Processo giornaliero che manteneva `daniele_profile.json` pulito:

```python
def dedupe_records(records):
    # chiave = (categoria, contenuto)
    # in caso di duplicato: mantiene il record con score più alto (priority_rank, confidenza)

def mark_stale_inferred(records):
    # condizioni: stato == "attivo" AND confidenza < 0.7 AND fonte contiene "infer" o "relic:"
    # azione: stato = "da_verificare"
    # effetto indiretto: aumenta unknownness al prossimo ranking → quel topic viene riselezionato
```

### 1.5 Drift relazionale notturno: `gumi_nightly_reflection.py`

Ogni notte alle 23:30, `relationship_warmth` veniva aggiornata:

```python
DRIFT_CONVERSATION = +0.025  # se oggi c'è stata conversazione
DRIFT_MOOD_BONUS   = +0.010  # bonus se mood_intensity >= 0.65 durante conversazione
DRIFT_NO_CONVO     = -0.015  # decadimento se silenzio
DRIFT_NOISE        = ±0.005  # rumore per naturalezza
# Clamped: [0.10, 0.95]
```

La warmth influenzava `reply_posture` (disappearing → flat → selective → present → alive → playful → performing), che a sua volta modulava la probabilità e il tono dei messaggi proattivi successivi.

### 1.6 Bridge Relic → Gumi: `gumi_relic_bridge.py`

Bridge unidirezionale che portava segnali analitici da `relic.db` nello stato operativo di Gumi:

```python
# Legge da relic.db (read-only, immutable URI):
decisions  = fetch_recent_decisions(conn, limit=3)   # decisioni recenti del soggetto
episodes   = fetch_recent_episodes(conn, limit=4)     # episodi rilevanti
entities   = fetch_active_entities(conn, limit=4)     # entità menzionate spesso

# Proietta in gumi/bridge_signals.json:
# - pending_topics: argomenti da esplorare
# - things_on_her_mind: cose a cui Gumi "pensa"
# - primary_tension: tensione relazionale corrente
# - relationship_warmth: calibrata dal sentiment dei segnali
```

---

## Parte 2 — Gap del sistema vecchio

### GAP-V1 ⚠️ CRITICO: il loop di chiusura non esisteva

**Il problema più grave dell'intera architettura.** Quando Daniele rispondeva a una domanda di Gumi, la risposta veniva loggata in `checkin_exchanges` — ma **nessun componente la elaborava** per aggiornare `daniele_profile.json` o `subject_baseline.json`.

Evidenza nel codice: i soli tre punti che leggevano `checkin_exchanges`:

```python
# gumi_outreach_arbiter.py:86 — solo cooldown
row = conn.execute("SELECT MAX(asked_at) FROM checkin_exchanges").fetchone()
# Usato UNICAMENTE per verificare se è troppo presto per un nuovo messaggio.

# gumi_kpi_update.py:46-48 — solo conteggio
total_checkins = conn.execute("SELECT COUNT(*) FROM checkin_exchanges").fetchone()[0]
replied = conn.execute(
    "SELECT COUNT(*) FROM checkin_exchanges WHERE reply_text IS NOT NULL"
).fetchone()[0]
# Usato UNICAMENTE per calcolare il tasso di risposta come KPI.

# gumi_personal_checkin.py:193 — solo anti-repeat
rows = conn.execute(
    """SELECT question_text, reply_text FROM checkin_exchanges
       WHERE reply_text IS NOT NULL AND asked_at >= datetime('now', '-14 days')
       ORDER BY asked_at DESC LIMIT 3"""
).fetchall()
# Usato UNICAMENTE per non ripetere domande simili. Il contenuto non viene estratto.
```

Conseguenza: Gumi faceva domande, Daniele rispondeva, ma il profilo non cresceva. `unknownness` restava alta su tutti i topic → stessi argomenti riselezionati → ciclo ripetitivo senza convergenza.

### GAP-V2: `reply_text` mai scritto al momento dell'invio

Il record inserito in `checkin_exchanges` al momento dell'invio conteneva solo la domanda e il `message_id` di Telegram:

```python
# gumi_personal_checkin.py — dopo aver inviato il messaggio
record_checkin(selected_facet, message, message_id)
# → chiama: mnemon.relic_db record-checkin --facet X --question Y --message-id Z
# Non esiste un --reply. La risposta sarebbe dovuta arrivare in un secondo momento
# dal listener Telegram, ma il wiring al medesimo exchange_id non era implementato.
```

### GAP-V3: Topic bucket fissi, non derivati dai facets del baseline

`gumi_topic_gap_score.py` definiva 5 bucket hardcoded con matching per keyword approssimativo su `daniele_profile.json`. Non c'era un mapping diretto ai facets di `subject_baseline.json`:

```python
def records_for_topic(records, topic):
    for rec in records:
        cat     = normalize_text(rec.get("categoria", ""))
        content = normalize_text(rec.get("contenuto", ""))
        cat_match = cat in topic.categories     # es. "obiettivi" in ("obiettivi","vincoli","decisioni")
        kw_match  = any(kw in content for kw in topic.keywords)
        # Fragile: "decisioni" matchava record di categorie non pertinenti
        # I 5 bucket non coprivano i 60 facets target del modello
```

### GAP-V4: Warmth drift ignora qualità della risposta

`gumi_nightly_reflection.py` driftava `relationship_warmth` solo su presenza/assenza di conversazione. Nessun segnale di qualità: lunghezza risposta, sentiment, argomento sensibile — tutto ignorato. Una risposta di due parole e una narrazione lunga producevano lo stesso drift.

### GAP-V5: I due store non erano sincronizzati

`daniele_profile.json` (Gumi-side) accumulava esperienza, ma il ricercatore vedeva solo `subject_baseline.json` (Relic-side) che restava fermo al bootstrap. Non esisteva alcun processo di sincronizzazione o proiezione tra i due.

---

## Parte 3 — Gap del sistema attuale (relic-oss)

### GAP-A ⚠️ CRITICO: nessuna pipeline di aggiornamento facets

`subject_baseline.json` viene scritto al bootstrap da `relic/profile/baseline_artifact.py` e **mai più toccato**:

```python
# relic/profile/baseline_artifact.py
def build_baseline_artifact(state):
    return {
        "schema_version": SCHEMA_VERSION,
        "self_report_fields":     state["self_report_fields"],
        "researcher_coded_fields": state["researcher_coded_fields"],
        "system_inferred_fields": {
            # tutti None — placeholder, mai popolati post-bootstrap
            "estimated_engagement_level":  {"value": None, "origin": "system-inferred"},
            "inferred_relational_style":   {"value": None, "origin": "system-inferred"},
            "session_affect_summary":      {"value": None, "origin": "system-inferred"},
            "response_latency_pattern":    {"value": None, "origin": "system-inferred"},
        },
        ...
    }
# Non esiste update_baseline_from_interaction() o equivalente.
```

### GAP-B: `signal_extractor.py` è safety-only

`relic/patterns/signal_extractor.py` estrae segnali di sicurezza (escalation, crisis, boundary pressure). Non è progettato per estrarre behavioral facets:

```python
# relic/patterns/signal_extractor.py
class SignalFamily(Enum):
    DEPENDENCY_ESCALATION       = "dependency_escalation"
    EXCLUSIVE_ATTACHMENT_LANGUAGE = "exclusive_attachment_language"
    CRISIS_LANGUAGE             = "crisis_language"
    SELF_HARM_LANGUAGE          = "self_harm_language"
    # ... 20 famiglie — tutte safety. Nessuna dimensione comportamentale.

class SafetySignalExtractor:
    def extract(self, ..., events) -> ExtractedSignals:
        # output: lista SensitiveSignal
        # nessun path verso subject_baseline.json
```

Il `SystemInferenceUpdater` in `relic/profile/system_inference.py` aggiorna solo 4 campi `system_inferred_fields` (engagement_level, relational_style, affect_summary, latency_pattern) da traced metadata — non dai contenuti conversazionali.

### GAP-C: `relic.db` vuoto, nessun event store attivo

```bash
$ file /home/cristina/.relic/subjects/daniele/relic.db
/home/cristina/.relic/subjects/daniele/relic.db: empty   # 0 bytes
```

Nessuna tabella esistente. Il sistema non ha ancora un meccanismo per loggare conversazioni in forma strutturata e interrogabile. Senza questo store le pipeline di extraction non hanno input.

### GAP-D: `facets_total: 60` è un numero fittizio senza schema

Nella UI (`ui/lib/workbench-data.ts`), il totale 60 viene preso dalla fixture demo:

```typescript
// ui/lib/workbench-data.ts:627
facets_total: subjectIntelligenceFixture.model_summary.facets_total,  // 60
```

Non esiste nel codebase un `FACET_SCHEMA` che enumeri le 60 dimensioni target, le loro basi teoriche, i range attesi, né i metodi di elicitazione raccomandati.

### GAP-E: Nessun question engine / check-in scheduler

`mnemon.relic_question_engine` (il cuore del vecchio sistema) non ha un equivalente in `relic-oss`. I moduli `relic/profile/inferred_fields.py` e `relic/profile/system_inference.py` gestiscono inferenza passiva da metadata, non scheduling attivo di check-in mirati.

---

## Parte 4 — Cosa portare dal vecchio sistema e prerequisiti dal sistema attuale

### TAKE-0 (prerequisito): Fix PCPBuilder in `hooks.py`

Identificato nell'analisi del `deep-research-report.md`. **Prerequisito indiretto** per i facets: senza PCP funzionante i facets aggiornati non raggiungono Gumi a runtime.

`relic/hermes_plugin/hooks.py:144` importa `PCPBuilder` che non esiste nel modulo:
```python
# ATTUALE (rotto — ImportError silenzioso a runtime)
from relic.context_pack.builder import PCPBuilder
self._pcp_builder = PCPBuilder(fail_safe=self._fail_safe, trace=self._pcp_trace)

# CORRETTO
from relic.context_pack.builder import ContextPackBuilder
self._pcp_builder = ContextPackBuilder(fail_safe=self._fail_safe, trace=self._pcp_trace)
```
Il costruttore `ContextPackBuilder` accetta gli stessi parametri. Fix one-liner, nessuna API da cambiare.

### TAKE-0b (prerequisito): Usare `InferredField` come tipo output del facet updater

`relic/profile/inferred_fields.py` definisce già il modello di governance per campi inferiti dal sistema. Il `facet_updater` deve usarlo come tipo nativo — non inventare un modello parallelo:

```python
# relic/profile/inferred_fields.py — interfaccia da riusare
@dataclass
class InferredField:
    field_name: str
    value: Any
    confidence: float                    # capped a 0.35 (single) o 0.55 (multi-evidence)
    source_refs: list[str]               # exchange_id come riferimento
    correction_state: str = "active"     # active | corrected | disputed | blocked
    clinical_interpretation_allowed: bool = False   # sempre False, enforced in __post_init__
    subject_visible: bool = False
    gumi_visible: bool = False
```

Uso nel facet updater: ogni osservazione estratta da una reply diventa un `InferredField` con `source_refs=[exchange_id]`. La confidence cap (`MULTI_EVIDENCE_CAP = 0.55`) viene applicata automaticamente da `__post_init__`. Un subject che fa correzione invoca `field.apply_correction()` → `correction_state = "corrected"` → il facet updater non può sovrascrivere.

### TAKE-1: Formula TGS

La formula di scoring era il meccanismo più maturo del vecchio sistema. Testata in produzione, bilanciamento dei pesi ragionato. Portare invariata adattando gli input a `subject_baseline.json`:

```python
# Da gumi_topic_gap_score.py — portare
score = 0.35 * unknownness    \
      + 0.25 * impact         \
      + 0.20 * timeliness     \
      - 0.20 * intrusion      \
      - 0.15 * asked_recently

# Adattamento: unknownness da subject_baseline.json
def compute_unknownness(facet_entry, now):
    conf_str = facet_entry.get("confidence", "low_initial")
    conf = {"high": 0.8, "medium": 0.5, "low_initial": 0.1}.get(conf_str, 0.1)
    observations = facet_entry.get("observations", 0)
    coverage_count = clamp(observations / 5.0)   # 5 obs = coverage piena
    stale_days = (now - parse_last_updated(facet_entry)).days
    stale_factor = clamp(stale_days / 60.0)
    unknown = 1.0 - (0.65 * conf + 0.35 * coverage_count)
    unknown += 0.25 * stale_factor
    return clamp(unknown)
```

### TAKE-2: Micro-style system

La rotazione tra 6 registri espressivi evitava monotonia percepita e manteneva il tono di Gumi naturale. Valore dimostrato nel pilota. Portare come configurazione per il generatore di check-in.

```python
MICRO_STYLES = {
    "osservazione_tenera": "apri con una piccola osservazione tenera o curiosa, poi fai la domanda",
    "curiosita_obliqua":   "entra di lato, con una curiosità obliqua e concreta invece che frontale",
    "presenza_calda":      "suona presente e calda, come se stessi già un po' dentro la sua giornata",
    "taglio_nitido":       "più nitida e diretta, ma sempre affettuosa",
    "invito_morbido":      "usa un invito morbido, non pressante, che lasci spazio",
    "gancio_sensoriale":   "parti da una sensazione, un dettaglio o un'immagine quotidiana",
}
```

### TAKE-3: Anti-repeat gate Jaccard

Semplice ed efficace. Due livelli di protezione:
1. **Similarity check**: Jaccard > 0.85 su n-gram della domanda → blocca
2. **Archetype cooldown**: ogni archetipo (leggerezza, ondate, movimento, ridicolo) max 2 usi/24h

```python
# Da anti_repeat.py — portare come modulo standalone in relic/checkin/anti_repeat.py
def check(prompt: str) -> dict:
    # Restituisce {"duplicate": bool, "reason": str}
```

### TAKE-4: Window scheduling con spaziatura minima

Configurazione operativa dimostrata nel pilota:
```python
windows             = ["09:30-12:30", "15:00-19:30", "21:00-22:30"]
min_spacing_minutes = 240
target_max_per_day  = 3
quiet_hours         = {"start": "23:00", "end": "08:00"}
```
Portare come sezione di `gumi_cron_manifest.json` (file già presente per soggetto).

### TAKE-5: `mark_stale_inferred` come meccanismo di decay

La logica di marcare record a bassa confidenza come `da_verificare` creava un ciclo naturale di re-esplorazione senza intervention manuale. Adattare per `subject_baseline.json`: facets con `observations < 2` e `last_updated > 60 giorni` → flaggati per re-elicitazione.

---

## Parte 5 — Il loop mancante: cosa costruire

Il gap critico è **uno**: le risposte di Daniele ai check-in non aggiornano il profilo. Tutto il resto (scoring, scheduling, generazione) funzionava o era riparabile. Quello che non esisteva mai — né nel vecchio né nel nuovo sistema — è il **facet updater**.

### Il loop completo che deve esistere

```
[1] gumi_topic_gap_score
      → seleziona facet con unknownness più alta
      → restituisce { selected_facet, question_hint, score }

[2] gumi_personal_checkin
      → genera domanda (LLM + micro-style + anti-repeat)
      → invia via Telegram
      → scrive in checkin_exchanges: { facet_id, question_text, message_id, asked_at }

[3] telegram_listener  ← ESISTE GIÀ (Hermes gateway)
      → riceve reply di Daniele
      → associa a message_id → exchange_id
      → scrive reply_text in checkin_exchanges

[4] relic_facet_updater  ← DA COSTRUIRE
      → legge checkin_exchanges WHERE reply_text IS NOT NULL AND processed = 0
      → per ogni riga:
            observation = llm_extract_observation(facet_id, question_text, reply_text)
            if observation.valid:
                update subject_baseline.json[facet_id]:
                    .value       = weighted_update(current, observation.value)
                    .confidence  = raise_confidence(current_conf, observation.quality)
                    .observations += 1
                    .last_updated = now
            mark checkin_exchanges[exchange_id].processed = 1

[5] UI (workbench)
      → legge subject_baseline.json
      → mostra progressione: 18/60 → 19/60 → ...
      → confidence "low_initial" → "low" → "medium" → "high"
```

### File da creare

**`relic/checkin/facet_updater.py`**  
Input: `subject_id`, `facet_id`, `question_text`, `reply_text`  
Output: patch struct `{ facet_id, new_value, new_confidence, observation_count, source_ref }`  
Constraints: non produce diagnosis labels; confidence cap `MULTI_EVIDENCE_CAP = 0.55` fino a revisione umana; usare `InferredField` da `relic/profile/inferred_fields.py` per governance.

**`relic/checkin/question_engine.py`**  
Porting del topic gap scorer dal vecchio sistema, adattato a leggere da `subject_baseline.json` invece di `daniele_profile.json`.

**`relic/checkin/scheduler.py`**  
Porting del gate temporale (finestre, spaziatura, quiet hours) da `gumi_topic_gap_score.py`.

**`relic/checkin/anti_repeat.py`**  
Porting del gate Jaccard da `anti_repeat.py`.

---

## Parte 6 — Tabella di stato componenti

| Componente | File vecchio (backup) | File attuale (relic-oss) | Stato |
|---|---|---|---|
| **Fix PCPBuilder** (`hooks.py:144`) | — | `relic/hermes_plugin/hooks.py` | ❌ bug attivo |
| Bootstrap baseline | — | `relic/profile/baseline_artifact.py` | ✅ completo |
| Schema governance facets | — | `relic/profile/inferred_fields.py` | ✅ completo |
| Safety signal extraction | — | `relic/patterns/signal_extractor.py` | ✅ completo |
| System inference (passiva) | — | `relic/profile/system_inference.py` | ✅ parziale (4 campi) |
| Event store / relic.db | tabelle `decisions`,`episodes`,`entities`,`checkin_exchanges` | `relic.db` esiste ma vuoto | ❌ non inizializzato |
| Topic gap scoring | `gumi_topic_gap_score.py` | — | ❌ mancante |
| Check-in scheduler / gate | `gumi_topic_gap_score.py` (sezione `compute_due`) | — | ❌ mancante |
| Generazione domanda | `gumi_personal_checkin.py` | — | ❌ mancante |
| Anti-repeat gate | `anti_repeat.py` | — | ❌ mancante |
| **Facet updater da reply** | **— (mai implementato)** | **—** | **❌ mai esistito** |
| Consolidamento profilo | `gumi_profile_consolidation.py` | — | ❌ mancante |
| UI facets display | — | `ui/lib/workbench-data.ts` (live path) | ⚠️ legge baseline, fixture parziale |
| Definizione schema 60 facets | 5 bucket approssimati | — | ❌ mai formalizzato |

---

## Appendice: formato dati corrente `subject_baseline.json`

Per riferimento, il profilo attuale del soggetto `daniele` (creato 2026-05-12):

```
psychological (7 facets):
  agreeableness           value=0.333  confidence=low_initial
  attachment_anxiety      value=0.278  confidence=low_initial
  attachment_avoidance    value=0.417  confidence=low_initial
  conscientiousness       value=0.500  confidence=low_initial
  emotional_stability     value=0.417  confidence=low_initial
  extraversion            value=0.083  confidence=low_initial
  openness                value=0.500  confidence=low_initial

interaction (11 facets):
  ambiguity_tolerance         value=1.000  confidence=low_initial
  audio_tolerance             value=0.500  confidence=low_initial
  checkin_tolerance           value=0.450  confidence=low_initial
  critique_tolerance          value=1.000  confidence=low_initial
  directness_preference       value=0.500  confidence=low_initial
  emotional_intensity_tolerance value=0.167 confidence=low_initial
  fictional_diegesis_tolerance value=0.450  confidence=low_initial
  humor_tolerance             value=1.000  confidence=low_initial
  image_tolerance             value=0.550  confidence=low_initial
  music_tolerance             value=0.500  confidence=low_initial
  proactive_contact_tolerance value=0.450  confidence=low_initial

Totale: 18/60 dimensioni inizializzate. Tutte low_initial = solo bootstrap, zero aggiornamenti da interazione.
```
