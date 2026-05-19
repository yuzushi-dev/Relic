# Safety Warning Governance Verification Prompt

Use this prompt with Codex/GPT-5.5 `xhigh` after quota is available.

```
Verifica finale, non modificare file. Repo /home/cristina/Scrivania/relic-oss, branch safety-warning-governance.

Obiettivo: confermare che il piano docs/plans/2026-05-17-safety-warning-governance.md sia implementato senza blocker.

Contesto sintetico:
- Implementati warning tiers/categories non clinici in relic/patterns/signal_extractor.py.
- Implementata aggregazione non-crisis in relic/safety/signal_aggregator.py e audit redatto in relic/safety/signal_audit.py.
- hooks.py/hooks_adapter.py: crisis immediata con evidence_refs/tier/confidence; non-crisis aggregata; safety scan non inietta contesto; refs opaque turn-<hash>, no session id.
- escalation_notifier.py: audit anche senza contatti; email include evidence_refs/tier/confidence; no raw text.
- shared_continuity/service.py: recent_markers filtra source_type safety/researcher-only/sensitive_signal.
- Workbench/schema/docs aggiornati.
- Verifica locale finale: targeted continuity/safety/Hermes subset 38 passed; full rtk pytest -q 1426 passed.

Verifica specificamente:
1. Piano eseguito rispetto a docs/plans/2026-05-17-safety-warning-governance.md.
2. Conformità Hermes: no injection safety labels, no reliance on post_llm_call for crisis, transform not used for notification/storage, hooks best-effort, audit redatto.
3. Anti-clinicalization: no diagnosis/risk-score framing; food/body/habit as governance context only.
4. No leakage to Gumi/continuity/Hermes memory.
5. Notification metadata and evidence ref redaction.
6. UI/schema backward compatibility.

Restituisci findings con severità e riferimenti file/linee. Se non ci sono blocker, dillo chiaramente.
```
