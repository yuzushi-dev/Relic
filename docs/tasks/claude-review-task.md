# Task per Claude (verifica spike + piano)

Sei chiamato come reviewer esterno. Devi verificare due documenti aggiornati:

- `docs/spikes/cron-checkin-naturalness-spike-claude.md`
- `docs/plans/2026-05-18-cron-checkin-naturalness-implementation.md`

Contesto:

- Il documento spike è il design di riferimento.
- Il documento plan è il piano TDD task-by-task derivato dallo spike.
- Entrambi sono già stati corretti più volte dopo review locali e una review Claude precedente sul `reach_score`.

## Cosa devi fare

Leggi entrambi i documenti e valuta solo questi aspetti:

1. **Coerenza spike ↔ piano**
   - Il piano implementa davvero le decisioni del documento spike?
   - Ci sono contraddizioni tra §9/§11/§12/§14 dello spike e i task del piano?

2. **Bloccanti per implementazione**
   - Ci sono passi del piano che un implementatore non potrebbe eseguire perché manca una definizione, un file reale, una test strategy concreta, o una dipendenza dal repo?
   - Ci sono test suggeriti che probabilmente non reggerebbero la struttura attuale del codice?

3. **Rischi tecnici residui**
   - Logging / Chronicle / `decision_events.jsonl`
   - `wakeAgent:false` vs no-agent path
   - `decision_type` plumbing
   - `checkin_cadence_state`
   - `followup_non_response_streak`
   - UI repointing

4. **Decisioni ancora troppo aperte**
   - Le “Conservative defaults for implementation” bastano davvero per partire?
   - C’è qualche open question che dovrebbe essere trasformata in default operativo o task esplicito?

5. **Modifiche puntuali consigliate**
   - Formato: sezione + problema + raccomandazione concreta.

## Vincoli

- Non modificare file.
- Non fare teoria generica.
- Cita sezioni specifiche (`§X.Y`) e, se utile, file/path del repo.
- Distingui tra:
  - `must_fix`: impedisce o rende rischiosa l’implementazione;
  - `nice_to_fix`: miglioramento utile ma non bloccante;
  - `do_not_change`: parti corrette che vanno preservate.

## Output

Restituisci JSON valido con questa forma:

```json
{
  "summary": "breve verdetto",
  "must_fix": [
    {"section": "§X", "issue": "...", "recommendation": "..."}
  ],
  "nice_to_fix": [
    {"section": "§X", "issue": "...", "recommendation": "..."}
  ],
  "do_not_change": [
    {"section": "§X", "reason": "..."}
  ]
}
```

Non fare preamboli fuori dal JSON.
