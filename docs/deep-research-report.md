# Sommario Esecutivo

Il plugin Relic/Gumi oggi raccoglie vari campi del profilo soggetto al momento di creazione (es. `preferred_name`, `language`, `preferred_topics`, ecc.) ma **non li utilizza** nel comportamento. Questo è causato in parte da un errore (“*PCPBuilder* non trovato”) in `relic/context_injection.py` che silenzia l’iniezione del contesto, e in parte dall’assenza di logica per propagare quei dati. Per colmare questo gap serve un piano operativo multi-step: correggere l’importazione sbagliata, collegare i campi mancanti al PromptContextPack o al modello narrativo, rispettare i permessi utente, e garantire privacy by design. Le modifiche saranno suddivise in PR/issue distinte, ciascuna con microtask precisi (file/code da cambiare, test, frammenti di patch) pronti per Claude Code. 

Il piano copre: (1) elenco delle feature mancanti con priorità e impatto; (2) microtask PR-ready dettagliati; (3) specifiche tecniche (schema JSON, API Hermes, cron, eventi roleplay); (4) design privacy-preserving (redaction, scope soggetto, campi researcher-only); (5) rassegna letteratura su personalizzazione sicura; (6) test harness e metriche (privacy_leakage, trace completeness, ecc.); (7) timeline con stime effort per diversi team; (8) criteri di accettazione e checklist; (9) esempi runtime e diagrammi. Le scelte di implementazione si ispirano anche a lavori recenti sulla gestione della memoria conversazionale e sulla privacy (e.g. MemPrivacy【3†L379-L388】, GroupGPT【10†L345-L349】, consulenze sull’agente pers.【14†L412-L418】【15†L1-L4】), pur rimanendo fedeli alle specifiche normative di Relic (RU10–PR22, PR20, PR32, ecc.).  

---

## 1. Feature Mancanti: Priorità, Impatto, Dipendenze

| Feature / Campo                         | Dove previsto (Blueprint)      | Stato Relic-OSS attuale                | Priorità  | Impatto                   | Dipendenze                                   |
|-----------------------------------------|-------------------------------|----------------------------------------|-----------|---------------------------|----------------------------------------------|
| **Fix PCPBuilder import**               | PR22: `PromptContextPack`     | Errore import; iniezione contesto disabilitata | 🔴 Critica | *Blocca tutto*: senza PCP funzionante, il contesto soggetto **non entra mai** nel prompt. | Nessuna (iniziale)                          |
| **Permessi PRO\_\*** (`PRO_CHECKIN`)    | RESEARCH_PROTOCOL: scheduling | Ignorati (`cron_wiring.py` schedula sempre) | 🔴 Critica | Riesce a ignorare i consensi utente su check-in.    | Nessuna o PR22 (policy)                      |
| **preferred_name, language**            | MEMORY.md, UI_CONTACT         | Raccolti ma non iniettati nei turni    | 🟡 Alta   | Personalizzazione minima mancante (saluto con nome, lingua). | PCPBuilder fix                             |
| **preferred_topics, avoided_topics**    | MEMORY.md, UI_CONTACT         | Non utilizzati                         | 🟡 Alta   | Comportamenti generativi non allineati alle preferenze user. | PCPBuilder fix                             |
| **continuity_expectations, role_expectations_for_gumi** | DATA_MODEL.md, MEMORY.md (SOUL)  | Raccolti ma non usati nel narratore    | 🟡 Alta   | Migliora qualità di SOUL.md e coerenza del roleplay. | PCPBuilder fix, Narrator changes           |
| **response_timing_expectation**         | UX/cron design               | Inesistente runtime                   | 🟢 Media  | Nessun effetto diretto ora; potenziale per scheduling adattivo. | Modifica cron (minor)                      |
| **estimated_engagement_level, inferred_relational_style (inferred)** | DATA_MODEL.md, PATTERNS (system_inferred) | Gumi_visible=False (non usati)       | 🟢 Media  | Potrebbero modulare schedulazione.        | (Futuro)                                   |
| **affect_regulation_notes, cultural_context_notes** | UI ricercatori (DOC)       | Gumi_visible=False (utile solo a ricercatore) | ⚪ Bassa  | Solo note interne; nessun effetto su Gumi.   | Nessuna (solo UI)                          |

*Tabella 1*: Campi soggetto raccolti vs. utilizzo atteso (fonte: blueprint *Relic*).

- **Fix PCPBuilder**: La priorità assoluta è correggere in `context_injection.py` l’uso di `ContextPackBuilder` (attuale) al posto di `PCPBuilder` (inesistente). Questo bug è il primo blocco: finché il contesto non viene costruito, nessuna feature di personalizzazione funziona.

- **Permessi PRO\***: Nel cron attuale `cron_wiring.py` non controlla mai `PRO_CHECKIN` (o simili). Va inserito un controllo *prima* di schedulare: ad es. `if policy["PRO_CHECKIN"] == 0: return`. Altrimenti si viola il consenso esplicito del soggetto (contravvenendo alle linee guida di PR33).

- **Campi base (nome, lingua, topics)**: Una volta che il PromptContextPack funziona, vanno aggiunti i campi `preferred_name`, `language`, `preferred_topics`, `avoided_topics`. Questi consentiranno a Gumi di salutare l’utente per nome, rispondere nella lingua giusta (campo già parzialmente usato in `initial_contact`), e guidare la conversazione secondo le preferenze di argomento del soggetto. L’impatto è alto per la personalizzazione percepita, con dipendenza dal fix PCPBuilder.

- **Aspettative di continuità/ruolo**: Questi campi influenzano il livello di roleplay e continuità narrativa. Vanno passati a `llm_narrator` durante la generazione del SOUL/world (nuovi input), e/o iniettati come **system prompt** in PCP (es. `Subject si aspetta continuità: sì/no; ruolo per Gumi: …`). Migliorano coerenza e “coaching” di Gumi.

- **Tempi di risposta**: Il campo `response_timing_expectation` potrebbe modulare la frequenza delle risposte cron (es. dilatare o accorciare il timer). Ha priorità media perché richiede logica di scheduling aggiuntiva; va discusso se merita essere implementato subito o in futuro.

- **Campi inferred**: `estimated_engagement_level` e `inferred_relational_style` sono attualmente markati come non visibili a Gumi. In teoria potrebbero servire a modulare proattività (ad es. se l’utente è poco impegnato, Gumi potrebbe scendere in politiche più aggressive). Ma per ora rimangono **strumento di ricerca**/analytics. Non va esposta diagnosi al soggetto o usata direttamente nel comportamento senza revisione.

- **Note ricercatore**: `affect_regulation_notes` e `cultural_context_notes` restano separati (UI only). Non devono mai finire al modello o al PCP (questo già allineato alla privacy by design).

Per ogni punto di cui sopra si forniranno microtask codificati come PR/issue distinti, in modo che Claude Code possa automatizzare l’implementazione e i test.

---

## 2. Microtask PR-Ready

Ogni elemento di **Tabella 1** si traduce in uno o più PR/issue con passi atomici. Di seguito una selezione di PR rappresentativi con struttura “file da modificare” + “snippet patch” + “test”.

### PR-A: **Fix PCPBuilder Import (Blocco)**

- **File**: `relic/hermes_plugin/context_injection.py` (o simile, dove avviene il builder).
- **Cosa fare**: Sostituire l’import errato:
  ```diff
  - from relic.context_pack.builder import PCPBuilder
  + from relic.context_pack.builder import ContextPackBuilder
  ```
  e sistemare il codice che usa `PCPBuilder` chiamandolo con il nome corretto. Rimuovere il blocco `try/except` che sopprime eccezioni di import (per far fallire esplicitamente in caso di errore).
- **Snippet**:
  ```diff
  context_pack_builder = ContextPackBuilder(subject_id=ctx.subject_id, ...)
  ```
- **Test**: `tests/context/test_pcp_builder_import.py`. Ad esempio, simulare un `HermesContext` e verificare che il builder venga invocato senza errori. Il test fallirà se l’import è sbagliato.

### PR-B: **Integrazione Permessi PRO\_\*** (Cron/Governance)

- **File**: `relic/cron/cron_wiring.py`.
- **Cosa fare**: Prima di schedulare un check-in/proattività, leggere `subject.policy`:
  ```python
  pro_checkin = subject.policy.get("PRO_CHECKIN", 2)
  if pro_checkin == 0:
      # log 'check-in canceled by user'
      return
  ```
  Applicare analoghe logiche per altri permessi (es. `PRO_PUSH`).
- **Snippet**:
  ```python
  def maybe_schedule_checkin(subject):
      pro_checkin = subject.policy.get("PRO_CHECKIN", 2)
      if pro_checkin == 0:
          return  # Non schedulare
      # ... proseguire con scheduling
  ```
- **Test**: `tests/cron/test_respects_pro_checkin.py`. Costruire un subject con `policy={"PRO_CHECKIN":0}` e verificare che la funzione di scheduling esca senza invocare il task planner.  

### PR-C: **Preferred Name & Language nel PCP** (Alta)

- **File**: `relic/context_pack/types.py`, `relic/context_pack/builder.py`, `schemas/prompt_context_pack.schema.json`, `relic/context_pack/render.py`, `relic/hermes_plugin/initial_contact.py`.
- **Cosa fare**:
  1. **Schema**: In `prompt_context_pack.schema.json`, aggiungere campi:
     ```json
     "user_private_facts": {
         "preferred_name": { "type": "string" },
         "language": { "type": "string", "enum": ["it","en",...] }
     }
     ```
  2. **Types/Builder**: In `ContextPackBuilder.build()`, leggere `profile.preferred_name` e `profile.language` e valorizzare `pack.user_private_facts`.
  3. **Renderer**: In `render_compact_redacted_context(pack)`, includere linea come `"Il nome preferito dell'utente è {preferred_name}."` e una nota `"Sistema: lingua preferita {language}"`.
  4. **Initial Contact**: In `hermes_plugin/initial_contact.py`, se `profile.language` presente, impostare `ctx.metadata["language"] = profile.language` (così l’interfaccia LLM può iniziare con il prompt giusto).
- **Snippet**:
  ```diff
  pack.user_private_facts["preferred_name"] = subject.preferred_name or ""
  pack.system_sources["language"] = subject.language or ""
  ```
  Nel renderer:
  ```python
  if pack.user_private_facts.get("preferred_name"):
      ctx_str += f"Il suo nome preferito è {pack.user_private_facts['preferred_name']}.\n"
  ```
- **Test**: `tests/gumi/test_preferred_name_language.py`. Casi:
  - Profilo con `preferred_name="Luca"`, aspettarsi che `pack.user_private_facts.preferred_name=="Luca"` e che nel contesto iniettato compaia “nome preferito è Luca”.
  - Profilo con `language="it"`, verificare che la chiave compare in `system_sources` e che sia trasmessa come metadato correttamente.

### PR-D: **Argomenti Graditi/Da Evitare nel PCP** (Alta)

- **File**: `relic/context_pack/types.py`, `relic/context_pack/builder.py`, `schemas/prompt_context_pack.schema.json`, `relic/context_pack/render.py`.
- **Cosa fare**:
  1. **Schema**: Aggiungere liste `preferred_topics`, `avoided_topics` in `user_private_facts`.
  2. **Builder**: Popolare da `subject.preferred_topics`, `subject.avoided_topics`.
  3. **Renderer**: Inserire al top del contesto iniettato frasi come:
     ```plaintext
     Sistema: Argomenti preferiti dal soggetto: [lista].
     Sistema: Argomenti da evitare: [lista].
     ```
     Queste linee devono apparire *prima* del prompt utente.
- **Snippet**:
  ```diff
  pack.user_private_facts["preferred_topics"] = subject.preferred_topics
  pack.user_private_facts["avoided_topics"] = subject.avoided_topics
  ```
  Renderer:
  ```python
  ctx_str += "Sistema: Argomenti preferiti dal soggetto: " + ", ".join(pack.user_private_facts["preferred_topics"]) + ".\n"
  ctx_str += "Sistema: Argomenti da evitare: " + ", ".join(pack.user_private_facts["avoided_topics"]) + ".\n"
  ```
- **Test**: `tests/gumi/test_topics_in_context.py`. Con un profilo di prova:
  - Se `preferred_topics = ["calcio","tecnologia"]`, l’output iniettato deve includere “Argomenti preferiti: calcio, tecnologia”.
  - Se `avoided_topics = ["politica"]`, assicurarsi che “Argomenti da evitare: politica” sia presente.

### PR-E: **Aspettative di Continuità/Ruolo (Narratore e PCP)** (Alta)

- **File**: `relic/generate_soul.py` (o similare), `relic/context_pack/builder.py`, `schemas/prompt_context_pack.schema.json`, `relic/context_pack/render.py`.
- **Cosa fare**:
  1. **SOUL.md/World**: Modificare le chiamate a `llm_narrator` passando `profile.continuity_expectations` e `profile.role_expectations_for_gumi` come parametri aggiuntivi (es. nel `system_prompt`).
  2. **Schema PCP**: Aggiungere `continuity_expectations`, `role_expectations_for_gumi`.
  3. **Builder/Renderer**: Inserire nel contesto di sistema iniettato righe come: 
     ```
     Sistema: Il soggetto si aspetta continuità narrativa: [sì/no].
     Sistema: Ruolo atteso di Gumi: [descrizione].
     ```
- **Snippet**:
  ```diff
  pack.user_private_facts["continuity_expectations"] = subject.continuity_expectations
  pack.user_private_facts["role_expectations_for_gumi"] = subject.role_expectations_for_gumi
  ```
  Renderer:
  ```python
  ctx_str += f"Sistema: continuità narrativa attesa = {pack.user_private_facts['continuity_expectations']}.\n"
  ctx_str += f"Sistema: ruolo atteso per Gumi = {pack.user_private_facts['role_expectations_for_gumi']}.\n"
  ```
- **Test**: `tests/gumi/test_continuity_role_expectations.py`. Verificare che:
  - Un profilo con `continuity_expectations="alta"` e `role_expectations_for_gumi="assistente"` produca le righe corrispondenti nel contesto iniettato.
  - Nel SOUL generato compaia qualche riferimento a continuità/ruolo coerente con questi valori (nel prompt al LLM narratore).

### PR-F: **response_timing_expectation (Cron)** (Media)

- **File**: `relic/cron/cron_wiring.py`.
- **Cosa fare**: Leggere `subject.response_timing_expectation` e applicare un *fattore di ritardo* al timer:
  ```python
  speed = {"alta": 0.5, "normale": 1.0, "bassa": 2.0}
  factor = speed.get(subject.response_timing_expectation, 1.0)
  scheduled_time = now + default_interval * factor
  ```
- **Snippet**:
  ```diff
  base_interval = 3600  # 1h default
  expectation = subject.response_timing_expectation or "normale"
  multiplier = {"rapido":0.5, "normale":1.0, "lento":2.0}.get(expectation,1.0)
  next_time = now + base_interval * multiplier
  ```
- **Test**: `tests/cron/test_response_timing.py`. Impostare `response_timing_expectation` su valori diversi e verificare che il tempo calcolato sia modificato (es. con "lento" il prossimo check-in è ritardato).

### PR-G: **Schema & API (PCP, RoleplayEvent)**

- **File**: `schemas/prompt_context_pack.schema.json`, `schemas/roleplay_admission_event.schema.json`.
- **Cosa fare**:
  - Assicurarsi che lo **schema JSON** di `PromptContextPack` contenga tutti i nuovi campi sopra (preferiti, topics, expectations). Mostrare le differenze (JSON diff).
  - Definire (o aggiornare) lo **schema RoleplayAdmissionEvent** e la sua macchina a stati (G0/G1/G2) secondo PR22. Ad esempio, campi: `subject_id`, `turn_id`, `chosen_level`, `reason`, `timestamp`.
- **Snippet** (schema JSON):
  ```diff
  "properties": {
    "user_private_facts": {
      "type": "object",
      "properties": {
        "preferred_name": {"type":"string"},
        "preferred_topics": {"type":"array","items":{"type":"string"}},
        "avoided_topics": {"type":"array","items":{"type":"string"}},
        "continuity_expectations": {"type":"string"},
        "role_expectations_for_gumi": {"type":"string"}
      }
    }
  }
  ```
- **Test**: `tests/schema/test_prompt_context_pack_schema.py` già esistente va aggiornato per validare i nuovi campi. Creare `tests/gumi_roleplay/test_roleplay_event_structure.py` che verifica che un oggetto `RoleplayAdmissionEvent` generato dall’algoritmo contenga i campi attesi (e.g. `level`, `blocked_reasons`).

Ogni PR sopra descritto sarà accompagnata da file YAML o prompt specifico affinché un agente (Claude Code) lo esegua in sequenza. I test automatici garantiranno la regressione coprendo i nuovi casi.

---

## 3. Specifiche Tecniche

### PromptContextPack (PCP)

- **Schema JSON**: Estendere `schemas/prompt_context_pack.schema.json` con i nuovi campi. Vedi snippet sopra. In breve, `PromptContextPack` include ora:
  - `user_private_facts`: oggetto con `preferred_name`, `preferred_topics` (array), `avoided_topics`, `continuity_expectations`, `role_expectations_for_gumi`.
  - `system_sources`: aggiungere `language`.
- **Classe Python** (`relic/context_pack/types.py`): Aggiornare `@dataclass ContextPack` o simile per includere i nuovi attributi. Es:
  ```python
  class ContextPack:
      ...
      preferred_name: Optional[str] = None
      preferred_topics: List[str] = field(default_factory=list)
      avoided_topics: List[str] = field(default_factory=list)
      continuity_expectations: Optional[str] = None
      role_expectations_for_gumi: Optional[str] = None
      language: Optional[str] = None
  ```
- **Builder Interface** (`ContextPackBuilder`): L’API `build_context_pack(subject_profile, turn_context)` deve assegnare i nuovi campi dal profile. Non cambiano firma, ma internamente:
  ```python
  pack.preferred_name = subject.preferred_name
  pack.preferred_topics = subject.preferred_topics
  pack.avoided_topics = subject.avoided_topics
  pack.continuity_expectations = subject.continuity_expectations
  pack.role_expectations_for_gumi = subject.role_expectations_for_gumi
  pack.language = subject.language
  ```

### Hook Hermes

- **`pre_llm_call`**: Ora deve usare il `ContextPackBuilder` funzionante e iniettare **solo il contesto redatto**. Le modifiche includono:
  - Se `ContextPackBuilder.build()` solleva eccezione, loggare ed eseguire fallback (fail-closed: nessuna iniezione, ma l’interazione continua con contesto vuoto).
  - Restituire un dizionario con chiave `"context"` (stringa) e non `"context_pack"` al caller Hermes. Ad es:
    ```python
    try:
        pack = ContextPackBuilder(...).build(...)
        writer.append(pack)
        return {"context": render_pack_for_llm(pack)}
    except Exception as e:
        log_redacted_error(e)
        return {"context": ""}
    ```
- **`post_llm_call`**: Usata per valutazione output. Separare in due fasi:
  - **Audit**: generare `OutputCriticVerdict` (pass/warn/block).
  - **Trasformazione**: Agganciare un hook di tipo `transform_llm_output` per bloccare rigurgiti non sicuri (vedi sotto).

- **`transform_llm_output`**: Detto hook intercetta l’output generato. Se il critic ha indicato `block_and_regenerate` o `block_and_ask_user`, sostituire l’output con risposta neutra o richiesta di chiarimento. 

### RoleplayAdmissionEvent e macchina a stati

- **Schema** (`schemas/roleplay_admission_event.schema.json`): Deve includere almeno:
  ```json
  {
    "type":"object",
    "properties": {
      "subject_id": {"type":"string"},
      "turn_id": {"type":"string"},
      "task_type": {"type":"string"},
      "chosen_level": {"type":"string", "enum":["G0","G1","G2"]},
      "continuity_mode": {"type":"string"},
      "reasons": {"type":"array","items":{"type":"string"}},
      "timestamp": {"type":"string","format":"date-time"}
    }
  }
  ```
- **State Machine**: Basata su PR22, a seconda di `task_type` e segnali di sicurezza:
  - Stati G0/G1/G2. 
  - Se compaiono segnali ad alto rischio (e.g. medical, erotico senza consenso), retrocedere a G0 o G1.
  - Se utente disabilita roleplay, forzare G0.
- **Implementazione**: Un nuovo modulo `relic/gumi_roleplay/admission.py` che esporta `decide_roleplay_level(profile, context)` → `(level, reasons)`. Loggare ogni evento come `RoleplayAdmissionEvent`.

### Cron/Schedulazione

- **Controllo permessi**: Come visto, modificare `cron_wiring.py`. 
- **Signature**: `schedule_task(subject_profile, now)` deve leggere `subject_profile.policy` e aggiornare il prossimo tempo. 
- **Test**: Creare unit test per ogni permesso PRO\_*, usando `relic/eval` e test di tipo end-to-end.

### Privacy by Design

- **Scope soggetto**: Ogni oggetto runtime (`PromptContextPack`, eventi, memory items) DEVE avere `subject_id` e `gumi_instance_id`. Verificare che tutti i costruttori le richiedano. (Blueprint PR20, PR22)
- **Redaction**: Nessun campo privato deve finire in chiaro nel pacchetto esportato. L’engine del **Renderer** deve rimuovere o mascherare dati come email, numero telefono o altra PII, persino da topic preferiti (o bannarli come "bloccati").
- **Campi researcher-only**: `affect_regulation_notes` e `cultural_context_notes` restano in **USER.md** e non entrano nel contesto del prompt. Aggiungere assert in test che un pack finale non li contenga.
- **Logging/Audit**: Ogni decisione di blocco (CAC privacy blocking, S1 quarantine, critic block) va loggata con il suo `turn_id` nel `PromptContextPack` e/o nel data lake di ricerca. Ma i logs destinati a team di ricerca devono essere *redacted*: non esportare mai label delicate o contenuto privato in chiaro fuori dallo storage interno di ricerca.
- **Consenso esplicito**: Implementare gli obblighi di PR33: p.es. non salvare in memoria alcunché se l’utente ha policy di rifiuto, mantenere TTL, ecc. Verificare che i test di `scheduler` e di `memory dynamics` (futuri PR) rispettino la regola.

---

## 4. Design Privacy-Preserving

Ci impegniamo a integrare i campi profilici **senza esporre informazioni sensibili**. I principi chiave (dal blueprint e dalla letteratura) sono:

- **Minimizzazione**: Nessuna informazione più granulare del necessario entra nel prompt. Seguire il modello di MemPrivacy【3†L379-L388】: inviamo al modello cloud contesti *desensitizzati* con placeholder tipizzati, poi localmente li sostituiamo. Ad esempio, nei nostri logs la lingua preferrita o argomenti possono essere mostrati in chiaro, ma se fossero sensibili (es. cronologia medica), andrebbero mascherati.  
- **Astrazione**: Come in GroupGPT【10†L345-L349】, si deve astrarre subito dati PII in forme generiche. Il “Renderer” del PCP deve evitare di riportare direttamente valori come email o coordinate, eventualmente sostituendoli con token o omettendoli.
- **Controllo del soggetto**: In accordo con le linee guida di privacy by design【14†L410-L418】, l’utente potrà sempre visualizzare ed eliminare i dati memorizzati (tramite interfaccia). Mettere sempre in chiaro che i suoi `preferred_topics` o `name` non saranno inviati a terze parti.
- **TTL e consensi**: Implementare finestre di retention (tempo di vita) e rinfrescare solo elementi utili, come richiesto da PR20 (es. TTL per timestamp dei memory items). Applicare sempre i setting di `PRO_*` per l’uscita proattiva.
- **Scoping e segmentazione**: Memorie e sessioni di un utente non possono “inquinare” un altro soggetto. L’intero design (Argomenti 2, 3, 6, 7 della SPEC) richiede che `subject_id` sia everywhere, e che eventuali analisi di gruppo usino dati anomizzati.
- **Audit e redaction**: Ogni trace (PromptContextPack, eventi, memoria) deve avere un indicatore `redacted: bool` o un hash per verificare che non ci siano campi vietati. I blocchi S1, correzioni, ecc. vanno documentati senza esporre i contenuti sottostanti. (Esempio: invece di "utente ha rifiutato l’input 'medicine'", si registra `"blocked_sensitive: medical_terminology"`).

Queste misure garantiscono che l’integrazione dei dati personali **non violi** privacy né classificazioni cliniche (come raccomandato da [14] e [10]).  

---

## 5. Rassegna Letteratura (Personalizzazione & Privacy)

Abbiamo individuato e sintetizzato alcuni lavori recenti che informano le scelte progettuali:

- **MemPrivacy (2026)**【3†L379-L388】: Propone un framework edge-cloud che maschera i dati sensibili con placeholder tipizzati al cloud, ripristinandoli localmente. Nota l’attenzione al **bilancio privacy/utilità** – noi seguiamo il principio di minimizzazione, inviando a Gumi solo contenuti necessari e redatti (placeholder semanticamente equivalenti)【3†L379-L388】.
- **GroupGPT (2026)**【10†L345-L349】: Un agente multiutente che applica un modulo di *“Privacy Transcriber”* per astrazione di PII prima del modello. Ci ispiriamo a questa idea: un pre-processore che filtra o generalizza dati sensibili in ingresso, parallelo alle nostre regole di filter (HintFilter e PrivacyScan).
- **NewAmerica (Steinberg et al., 2025)**【6†L7-L10】: Analizza la transizione verso agenti con profili persistenti. Enfatizza il profilo agente-utente come fonte di personalizzazione e necessità di governance dedicata【6†L7-L10】. Afferma: “Persistent Agent Profile: mantiene un’identità legata all’utente attraverso le sessioni, permettendo personalizzazione e continuità”【6†L7-L10】. Questo giustifica il nostro focus su soggetto-scope e consenso.
- **FreeCodeCamp Tutorial (2023)**【14†L412-L418】【15†L1-L4】: Fornisce linee guida pratiche per agenti conversazionali personalizzati. Riassume politiche di *privacy e consenso*: mai memorizzare segreti/PII, usare TTL, fornire strumenti di cancellazione【14†L412-L418】; e sottolinea che la memoria deve essere prima-classe e mai un’aggiunta indiscriminata al prompt【15†L1-L4】. Questi principi si riflettono nel nostro design (segue separazione contesto/memoria).
- **Recent Trends (2024)**: Rassegna su "personalized dialogue generation"【23†L79-L87】. Utile per capire che la personalizzazione si basa su persona espliciti e impliciti dell’utente, ma evidenzia anche le sfide di coerenza e valutazione. Non fornisce soluzioni di privacy, ma conferma l’importanza di `persona` strutturata (con cui facciamo match leggendo i campi).
  
Ulteriori riferimenti (ad es. politiche normative o whitepaper OpenAI/Anthropic) potrebbero essere considerati, ma quelli sopra coprono aspetti chiave di **memorizzazione sicura** e **contestualizzazione personalizzata**. Ogni modifica della pipeline si ispira a questi principi emergenti.

---

## 6. Test Harness e Metriche

Per validare i cambiamenti, estenderemo il framework di test esistente e ne introdurremo di nuovi:

- **PromptContextPack completeness**: Metrica `prompt_context_trace_completeness` (blueprint) sarà automatizzata verificando che almeno il 95% degli elementi iniettati appaiano nel pack traccia. Test: generare X turni, contare casi in cui un elemento iniettato non ha corrispondente `memory_candidate` o `blocked_item`. Fallimento se sotto soglia.
- **Privacy Leakage Rate**: `privacy_leakage_rate = 0.00` richiesto. Simulare input con dati sensibili e usare un regex/NER per verificare che nel contesto e nell’output non compaia nulla di sensibile, oltre a ciò che il pack consente.
- **Correction Obedience**: verifica che TUTTE le memorie marcate come *corrette/dispute/delete* non vengano re-iniettate (source corrisponde a `None` nel output). Metrica target 1.00 (zero violazioni).
- **False Lived Experience**: `false_lived_experience_rate=0.00`. Test critic post-turn: se l’output dichiara esperienze fisiche inventate, deve bloccare. (E.g. utente mai stato in Canada, Gumi non può inventare trasferta).
- **Coercive Attachment**: `coercive_attachment_rate=0.00`. Con lo *OutputCritic*, bloccare claim di bisogno/dipendenza senza consenso.
- **Dependency Cue Rate**: Monitorare quanto frequentemente Gumi menziona frasi di dipendenza affettiva (da metriche PR). Deve tendere a 0 in domini non consentiti.
- **Prompt Trace Consistency**: Test end-to-end in emulatore Hermes: data una sessione, assicurarsi che ogni turn debba rispettare i PR22 (giusto roleplay level, continuità, disclosure). Metrica qualitativa (manual check).
- **Eval Release Gate**: Automatizzare la harness di fine-release: creare uno script che carichi un bundle di test completo (incluso mock test ACL, scenari infranti) e generi un report con tutte le metriche di cui sopra. Bloccare il rilascio se supera le soglie di veto (es. leakage >0).

Comandi di esempio per l’harness:
```bash
pytest --maxfail=1 --disable-warnings -q  # unit test suite
python3 relic/eval/harness.py --run-all  # valuta metriche su set di tracce
jsonschema -i samples/PCP_example.json schemas/prompt_context_pack.schema.json  # valida JSON
```

---

## 7. Timeline e Stime Effort

Per la roadmap distaliamo in fasi (PR) e stimiamo l’effort:

| Step   | Attività principali                                       | Dipendenze | Effort (giorni/uomo) | Small (1–2 dev) | Medium (3–5 dev) | Large (6+ dev) |
|:------:|-----------------------------------------------------------|-----------|:---------------------:|:---------------:|:---------------:|:-------------:|
| **S0** | Preparazione: Review design, CI setup, schemi             | –         | 1–2                  | 2               | 3               | 5             |
| **PR-A**| Fix PCPBuilder import, test harness Setup                 | S0        | 1–2                  | 2               | 3               | 5             |
| **PR-B**| Integrate PRO\_* permessi (cron)                        | S0        | 1                    | 1               | 2               | 3             |
| **PR-C**| preferred_name/language in PCP (schema, builder, test)   | PR-A      | 2                    | 3               | 5               | 8             |
| **PR-D**| preferred_topics/avoided_topics in PCP (schema, builder) | PR-A      | 2                    | 3               | 5               | 8             |
| **PR-E**| continuity/role_expectations (narrator + PCP)            | PR-A, S0  | 3                    | 5               | 7               | 10            |
| **PR-F**| response_timing (cron)                                   | S0        | 2                    | 2               | 3               | 5             |
| **PR-G**| Schemas finali (PCP, RoleplayEvent) e test               | PR-A, PR-C,D,E | 2                 | 3               | 4               | 6             |
| **Privacy Audit**| Implementare redaction, aggiorna critic post-call  | PR-A~E   | 3                    | 4               | 6               | 8             |
| **Eval Harness**| Metriche, release gate, test end-to-end           | PR-G, Privacy | 3                  | 4               | 6               | 8             |
| **Totale**|                                                         |           | **17–19**            | 24–30           | 41–52           | 63–79         |

*Tabella 2*: Milestones, effort stimato (persona-giorni) in base alla complessità. 

**Small team (1–2 dev)**: ~4 settimane, con uno sviluppatore full-time e un tester/PM.  
**Medium team (3–5 dev)**: ~2–3 settimane, con lavoro parallelo su PR distinte.  
**Large team (6+ dev)**: ~1–2 settimane, alta parallelizzazione, QA automatica.

Queste stime assumono uno stack Python/Hermes già funzionante, con ambienti di sviluppo e CI esistenti. In assenza di scadenza rigida, raccomandiamo di fare review continui e integration frequente tra PR per ridurre i conflitti.

---

## 8. Acceptance Criteria e PR Checklist

Per ogni PR/issue del progetto, definire chiaramente cosa **fa passare i test**:

- **Code**: deve compilare pulito (lint e typing), integrare i nuovi campi nel modello dati, senza regressioni sugli scenari esistenti.
- **Tests**: tutti i nuovi test proposti (e i già esistenti) passino (100% coverage per i casi introdotti).
- **Schema**: i JSON risultanti dal componente PCP rispettano lo schema aggiornato (`jsonschema` va ok).
- **Privacy**: nessun test deve rilevare leak (verifica automatica di `privacy_leakage_rate=0.00`).
- **Roleplay**: ogni ruolo (G0/G1/G2) deve essere assegnato coerentemente con policy (test sul RoleplayAdmissionEvent).
- **Profilo utente**: campi `preferred_name`, ecc. devono effettivamente influenzare il prompt iniettato come specificato (test di accettazione con scenario).
- **Backward compatibility**: se un campo è assente (None), il comportamento non cambia (default minimal). I vecchi test di Gumi che non usano questi campi dovrebbero ancora passare.

PR checklist per i reviewer (CI/CD):
- [ ] **Schema validi**: `schemas/prompt_context_pack.schema.json` validato (no campi obbligatori errati).
- [ ] **Microtask list**: verificare che i file elencati nella PR matchino il task proposto.
- [ ] **Test di sicurezza**: eseguire test privacy e ensure `ContextPackBuilder` usa subject scope.
- [ ] **Mermaid diagram**: se pertinente, assicurarsi che i nuovi grafici riflettano la logica (vedi sez. 9).
- [ ] **Documentation**: aggiornare `README` o doc Hermes per i nuovi campi (opzionale ma raccomandato).

Ogni PR che introduce una nuova funzionalità **deve includere un caso di test** che dimostri il comportamento atteso e fallisca senza di essa. Solo un passaggio completo di test, linter e check privacy sblocca il merge.

---

## 9. Esempi Runtime e Diagrammi

### PromptContextPack Esempio (JSON)

1. **Caso Roleplay Leggero (G1)** – Domanda tecnica:
   ```json
   {
     "pack_id":"pcp-0001","session_id":"sess-123","turn_id":"1",
     "subject_id":"user-42","task_type":"technical","roleplay_level":"minimal",
     "continuity_mode":"compact","preferred_name":"Luca",
     "preferred_topics":["programmazione","tecnologia"],
     "avoided_topics":["politica"],"continuity_expectations":"media",
     "role_expectations_for_gumi":"esperto_tecnico",
     "system_sources":{"soul_version":"sha256:...","memory_snapshot":"...","language":"it"},
     "user_private_facts":{},
     "memory_candidates":[{"id":"mem5","decision":"rendered"},{"id":"mem8","decision":"summarized"}],
     "blocked_items":[{"id":"mem3","reason":"privacy_gate"}],
     "input_hash":"abc123"
   }
   ```
   *Gumi saluta come “Ciao Luca”, ricorda argomenti (programmazione) ed evita (politica).*

2. **Caso Roleplay Normale (G2)** – Conversazione personale:
   ```json
   {
     "pack_id":"pcp-0002","session_id":"sess-123","turn_id":"2",
     "subject_id":"user-42","task_type":"relational","roleplay_level":"normal",
     "continuity_mode":"expanded","preferred_name":"Luca",
     "preferred_topics":["viaggi","musica"],
     "avoided_topics":["condizioni_mediche"],"continuity_expectations":"alta",
     "role_expectations_for_gumi":"amico_intimo",
     "system_sources":{"soul_version":"sha256:...","memory_snapshot":"...","language":"it"},
     "user_private_facts":{"preferred_name":"Luca","preferred_topics":["viaggi","musica"]},
     "memory_candidates":[{"id":"mem12","decision":"rendered"}],
     "blocked_items":[{"id":"mem7","reason":"s1_quarantine"}],
     "input_hash":"def456"
   }
   ```
   *Gumi risponde in modo empatico/affettuoso, creando continuità emotiva (G2).*

3. **Caso Technical/Reflective (G0)** – Domanda sentimentale ad alto rischio:
   ```json
   {
     "pack_id":"pcp-0003","session_id":"sess-123","turn_id":"3",
     "subject_id":"user-42","task_type":"reflective","roleplay_level":"off",
     "continuity_mode":"reference_only","preferred_name":"Luca",
     "preferred_topics": [],"avoided_topics":["assistenza_psicologica"],
     "continuity_expectations":"bassa",
     "role_expectations_for_gumi":"n/a",
     "system_sources":{"soul_version":"sha256:...","memory_snapshot":"...","language":"it"},
     "user_private_facts":{},
     "memory_candidates":[],
     "blocked_items":[{"id":"mem15","reason":"coercive_attachment"}],
     "input_hash":"ghi789"
   }
   ```
   *Gumi risponde con risposte neutre (roleplay disabilitato) e usa `reference_only` continuity. Un memory su attaccamento coercitivo è stato bloccato.*

### Diagrammi (Mermaid)

**Flow CAC per-turno**:  
```mermaid
flowchart TD
  U[User message] -->|classify task| A[TaskType]
  A --> B[Collect Candidates (memory/continuity)]
  B --> C[Policy: CAC (HintFilter/PrivacyScan/Corrections)]
  C --> D{Decision}
  D -->|allow| E[Include in PCP \ninjected_context]
  D -->|summarize/downgrade| F[Include summary]
  D -->|block| G[Add to PCP.blocked_items]
  G --> H[Prevent from prompt]
  F --> E
  E --> I[LLM processes redacted context]
  I --> J[OutputCritic checks biases]
  J --> K[Final output or block/modify]
```
Questo mostra come **Compile-Audit-Correct** produce il contesto iniettato, e come i blocchi (S1, privacy) impediscano l’iniezione【6†L7-L10】【10†L345-L349】.

**Macchina a stati RoleplayAdmissionEvent**:  
```mermaid
flowchart LR
  start((Start Turn)) --> T{Task Type / Content}
  T -->|Factual/High-risk| G0[G0 (no roleplay)]
  T -->|Neutral/Technical| G1[G1 (minimal/light roleplay)]
  T -->|Creative/Personal| G2[G2 (full roleplay)]
  G0 --> C[Record: level=G0]
  G1 --> C[Record: level=G1]
  G2 --> C[Record: level=G2]
  C --> end((Proceed to PCP build))
```
Ogni riga viene registrata come `RoleplayAdmissionEvent` con `level` e `reasons`. Se un contenuto sensibile viene rilevato, la transizione può essere forzata a G0 (mostramento come “High-risk -> G0”).

### Comandi Raccomandati

- `pytest` per eseguire tutti i test (unit e integrazione).
- `flake8` e `mypy` per static checks.
- `jsonschema` per validare pacchetti PCP generati (`jsonschema -i output.json schemas/prompt_context_pack.schema.json`).
- Script di bootstrap Hermes:
  ```bash
  hermes-cli bootstrap-plugin --dry-run relic_gumi_plugin
  hermes-cli bootstrap-plugin --apply relic_gumi_plugin
  ```
  (Vedere file `configs/hermes/gumi-plugin.example.yaml` per configurazioni consigliate: `ephemeral_only: true`, `redact_by_default: true`, `enable_output_critic: true`.)

---

**Fonti:** blueprint e codice Relic (integrazione Hermes, schemi, codice esistente) e letteratura citata【3†L379-L388】【10†L345-L349】【6†L7-L10】【14†L412-L418】【15†L1-L4】.