# Task per Codex (parere su confronto spike)

Sei chiamato come secondo revisore. Due spike doc esistono nel repo per lo stesso brief:

1. `docs/spikes/cron-checkin-naturalness-spike-claude.md` (autore: Claude)
2. `docs/spikes/cron-checkin-naturalness-spike-codex.md` (autore: Codex precedente, probabilmente tu stesso in run passato)

Brief originale: `cron-checkin-naturalness-spike-claude_prompt.md` (root del repo).

## Cosa devi fare

Leggi entrambi i doc + il brief. Poi rispondi a queste domande in modo conciso (max ~600 parole totali):

1. **Quali sezioni del doc Claude sono oggettivamente migliori del doc Codex e perché?** (cita sezione/§ specifici)
2. **Quali sezioni del doc Codex il doc Claude dovrebbe assorbire?** In particolare valuta:
   - L'uso del meccanismo Hermes `script=` + `wakeAgent:false/true` (Codex §3 "Recommended Hermes shape").
   - Lo split osservabilità log che Codex segnala (writer scrive `~/.relic/decision_events.jsonl`, UI legge `$HERMES_HOME/workspace/gumi/cron/checkin_decision_log.jsonl`). Verifica nel codice se è vero. Cita file:line concreti.
   - La separazione `event_type` × `posture` come 2 dimensioni indipendenti (Codex §8 output structure vs Claude §9 posture-singola).
   - La "logging reconciliation" come step 1 dell'implementation plan.
3. **Quali punti del doc Claude sono superiori e vanno preservati?** Almeno: numeri concreti (thresholds, damping curve), code-citation esterna verificata, replayability operativa, forbidden transitions matrix, scenari con feature vector concreto.
4. **Cosa è sbagliato o ambiguo in entrambi i doc?** Punti dove un implementatore si bloccherebbe.
5. **Lista di modifiche puntuali da fare al doc Claude** per integrare il meglio di Codex senza perdere i suoi punti forti. Formato: `§X.Y: cosa cambiare. Perché.`

## Vincoli

- NON modificare file. Solo report.
- Non parafrasare il brief; assumi che chi legge lo conosce.
- Concreto sopra teoria. Cita file:line e sezioni numerate.
- Se trovi affermazioni false in uno dei due doc (es. presunti file:line inesistenti), segnalalo.
- Output in italiano, modalità tecnica (caveman opzionale).

## Output

Scrivi direttamente la risposta (Codex la salva tramite --output-last-message). Niente preamboli, niente "ecco il mio parere".
