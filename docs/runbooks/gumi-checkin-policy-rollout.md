# Gumi Check-in Naturalness Policy — Rollout Runbook

Owner: cron-checkin-naturalness work.
Related: [spike](../spikes/cron-checkin-naturalness-spike-claude.md),
[plan](../plans/2026-05-18-cron-checkin-naturalness-implementation.md).

Two env flags gate the new behaviour. Both default to OFF so the legacy
DELIVER path is preserved until an operator explicitly opts in:

| Flag | Purpose |
|------|---------|
| `RELIC_HERMES_WAKE_AGENT_JSON` | Switches the no-agent cron script to the Hermes `wakeAgent: { ... }` JSON contract (Plan §Task 2). |
| `RELIC_CHECKIN_POLICY_ENABLED` | Enables the naturalness policy (`select_decision`) inside `make_decision` (Plan §Task 7). |
| `RELIC_PROACTIVE_QUEUE_ENABLED` | Provisions the proactive consumer lane and skips the legacy `relic_proactivity_decision.sh` script (Plan §Task 9). |

## 1. Verify existing cron jobs

Confirm the three legacy decision scripts are present and current. Re-provision
in dry-run mode if any are stale:

```bash
rtk python - <<'PY'
from relic.gumi_plugin.cron_wiring import provision_for_subject
print(provision_for_subject(
    subject_id="demo",
    gumi_instance_id="demo",
    hermes_profile_id="gumi-demo",
    dry_run=True,
))
PY
```

## 2. Enable canonical logging with policy still disabled

This step lights up the new fields in `decision_events.jsonl` and Chronicle
without changing behaviour.

```bash
rtk pytest tests/gumi_plugin/test_decision_log_canonical.py -q
```

Run one cron tick and inspect the canonical log path:

```bash
rtk python - <<'PY'
from pathlib import Path
import os
path = Path(os.environ.get("RELIC_HOME", str(Path.home() / ".relic"))) / "decision_events.jsonl"
print(path)
PY
```

```bash
rtk python - <<'PY'
from pathlib import Path
import os
import json
path = Path(os.environ.get("RELIC_HOME", str(Path.home() / ".relic"))) / "decision_events.jsonl"
for line in path.read_text().splitlines()[-10:]:
    data = json.loads(line)
    print(data.get("created_at"), data.get("decision"), data.get("decision_type"), data.get("outcome_status"))
PY
```

After this repoint, the workbench `pending_proactive_count` may jump from a
broken historical `0` baseline because the previous file
(`$HERMES_HOME/workspace/gumi/cron/checkin_decision_log.jsonl`) had no in-repo
writer. This is expected.

## 3. Enable `RELIC_HERMES_WAKE_AGENT_JSON=1` on one test profile

```bash
RELIC_HERMES_WAKE_AGENT_JSON=1 \
RELIC_SUBJECT_ID=demo \
bash ~/.hermes/scripts/demo/relic_checkin_decision.sh
```

stdout must parse as exactly one JSON object — either `{"wakeAgent": false, ...}`
on a silent gate or `{"wakeAgent": true, "context": {...}}` on a DELIVER.
Any other stdout line means the gate is leaking — disable the flag and file
the bug.

## 4. Enable `RELIC_CHECKIN_POLICY_ENABLED=1` on the same test profile

```bash
RELIC_CHECKIN_POLICY_ENABLED=1 RELIC_HERMES_WAKE_AGENT_JSON=1 \
bash ~/.hermes/scripts/demo/relic_checkin_decision.sh
```

Watch the next 5–10 ticks. Each non-silent payload must contain the constraint
header at the top:

```
[EVENTO: <kind>]
[POSTURA: <posture>]
[VINCOLI: max <N> frasi; <con|senza> domanda]
[GROUNDING: ...]   (optional)
```

## 5. Inspect Chronicle events + canonical mirror

```bash
rtk chronicle-cli events --event-type cron_decision --limit 20
```

Spot-check that `decision_type`, `event_kind`, `posture`, `outcome_status`,
`non_response_streak`, `followup_non_response_streak`, and `reach_score` are
present on new rows.

## 6. Run the replay harness

```bash
rtk python tools/replay_decisions.py \
  --input $(rtk python -c 'from relic.paths import get_relic_home; print(get_relic_home() / "decision_events.jsonl")') \
  --output .agent-outs/replay.jsonl
```

Look at the `changed` column. A high `changed` ratio is the signal that
manual review (step 7) is needed before promoting beyond the test profile.

## 7. Manual review — 20 decisions

Pull 20 random rows from `decision_events.jsonl` and read the rendered
messages alongside the constraint header. Confirm:

- silent decisions are paired with `wake_agent_emitted == false`;
- non-silent decisions respect their declared `max <N> frasi` cap;
- `posture == 'ask'` lines actually contain a question; everything else does not.

## 8. Enable the proactive queue lane

```bash
RELIC_PROACTIVE_QUEUE_ENABLED=1 rtk python - <<'PY'
from relic.gumi_plugin.cron_wiring import provision_for_subject
print(provision_for_subject(
    subject_id="demo",
    gumi_instance_id="demo",
    hermes_profile_id="gumi-demo",
    dry_run=False,
))
PY
```

Confirm `relic_proactivity_decision.sh` is no longer scheduled and the new
`proactive_queue.jsonl` is being drained by the consumer.

## 9. Rollback

To revert quickly:

```bash
unset RELIC_CHECKIN_POLICY_ENABLED
unset RELIC_HERMES_WAKE_AGENT_JSON
unset RELIC_PROACTIVE_QUEUE_ENABLED
```

The legacy text-stdout DELIVER path is preserved by design — no code change
needed to roll back, only env flag removal.

## Optional full check command

```bash
rtk pytest \
  tests/checkin \
  tests/gumi_plugin \
  tests/hermes/test_no_agent_cron_wiring.py \
  tests/profile/test_checkin_prompt_contract.py \
  -q
```
