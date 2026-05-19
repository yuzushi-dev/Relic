# Cron Check-in Naturalness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the inspectable cron check-in naturalness policy described in `docs/spikes/cron-checkin-naturalness-spike-claude.md`.

**Architecture:** Hermes remains responsible for scheduling and profile execution. Relic/Gumi owns the policy: canonical decision logging, `decision_type` plumbing, feature assembly, `(EventType, Posture)` selection, cadence damping, posture-filtered context, proactive queue consumption, and replayable evaluation. The first delivery milestone preserves current behavior while making decisions observable; later milestones add behavior changes behind tests.

**Tech Stack:** Python 3.10+, pytest, SQLite, Chronicle event emitter, Hermes cron shell scripts, TypeScript workbench data reader.

---

## Ground Rules

- Keep `_evaluate_decision()` safety/consent gate ordering intact unless a test explicitly covers the change.
- Keep the current `tipo:` / `testo:` / `caption:` / `image_prompt:` dispatcher contract.
- Keep `[SILENT]` as a composer-side safety net even after adding `wakeAgent:false`.
- Do not store raw user or assistant text in cadence/features logs. Use IDs, hashes, counts, timestamps, and short approved refs.
- Use the conservative defaults in `docs/spikes/cron-checkin-naturalness-spike-claude.md` §15 if a human has not signed off on an open question yet.
- Treat the decision log path as a contract: writer and UI reader must resolve the same `RELIC_HOME`-aware location.
- Each task below should be committed separately when implemented.

## Verification Baseline

Before starting implementation, run:

```bash
rtk pytest tests/hermes/test_no_agent_cron_wiring.py tests/checkin/test_context_builder.py tests/profile/test_checkin_prompt_contract.py -q
```

Expected: all selected tests pass before changes. If they fail, record the failures and fix only if they are directly related to this work.

---

### Task 1: Canonical Decision Log Shape and `decision_type` Plumbing

**Files:**
- Modify: `relic/gumi_plugin/cron_wiring.py`
- Modify: `relic/hermes_runtime.py`
- Modify: `ui/lib/workbench-data.ts`
- Test: `tests/gumi_plugin/test_decision_log_canonical.py`
- Test: `tests/hermes/test_no_agent_cron_wiring.py`

**Step 1: Write failing tests for decision type plumbing**

Create `tests/gumi_plugin/test_decision_log_canonical.py`:

```python
from __future__ import annotations

from relic.gumi_plugin.cron_wiring import make_decision, render_no_agent_script


def test_make_decision_accepts_decision_type(monkeypatch):
    calls = {}

    def fake_eval(subject_id, gumi_instance_id, hermes_profile_id, decision_type="checkin"):
        calls["decision_type"] = decision_type
        from relic.hermes_runtime import RuntimeDecision
        return RuntimeDecision.NO_REPLY, [], None

    monkeypatch.setattr("relic.gumi_plugin.cron_wiring._evaluate_decision", fake_eval)

    make_decision("s1", "g1", "p1", decision_type="proactivity")

    assert calls["decision_type"] == "proactivity"


def test_rendered_script_passes_decision_type_from_filename(tmp_path):
    script = render_no_agent_script(tmp_path / "relic_followup_decision.sh")
    assert "DECISION_TYPE=" in script
    assert "make_decision(" in script
    assert "decision_type=decision_type" in script
```

**Step 2: Run tests to verify failure**

Run:

```bash
rtk pytest tests/gumi_plugin/test_decision_log_canonical.py -q
```

Expected: fail because `make_decision()` has no `decision_type` parameter and rendered scripts do not pass it.

**Step 3: Add `decision_type` parameter**

In `relic/gumi_plugin/cron_wiring.py`:

- Add `decision_type: str = "checkin"` to `_evaluate_decision()` and `make_decision()`.
- Pass `decision_type` through every call from rendered script.
- In `render_no_agent_script(script_path)`, derive the script default from `script_path.name` before the heredoc is rendered:

```python
_name = script_path.name
if "_followup_" in _name:
    default_decision_type = "followup"
elif "_proactivity_" in _name:
    default_decision_type = "proactivity"
else:
    default_decision_type = "checkin"
```

Inside the rendered shell, interpolate the derived default and expose:

```bash
DECISION_TYPE="${RELIC_DECISION_TYPE:-<default_decision_type>}"
```

Then:

1. pass it into the Python heredoc argv;
2. parse it in the heredoc as `decision_type`;
3. thread it into `make_decision(..., decision_type=decision_type)`;
4. thread it into `emit_decision_event(..., decision_type=decision_type)`.

Add a wiring test that renders `relic_checkin_decision.sh`, `relic_followup_decision.sh`, and `relic_proactivity_decision.sh` and asserts they embed three distinct defaults.
Do not rely on a post-render string replace for `DECISION_TYPE`; the rendered content itself must differ per dtype, or the shell must derive the default from `basename($0)` at runtime.

**Step 4: Extend decision event payload**

In `relic/hermes_runtime.py`, extend `DecisionEvent` with optional fields defaulting to `None`:

```python
decision_type: str | None = None
event_kind: str | None = None
posture: str | None = None
features_id: int | None = None
non_response_streak: int | None = None
followup_non_response_streak: int | None = None
reach_score: float | None = None
response_deadline_at: str | None = None
cadence_decay_applied: bool | None = None
outcome_status: str | None = None
wake_agent_emitted: bool | None = None
message_hash: str | None = None
delivered: bool | None = None
```

Include all fields in `to_dict()`.
Update `from_dict()` to round-trip the same optional fields, defaulting missing values to `None`.

In `cron_wiring.emit_decision_event()`, first switch the writer path to `relic.paths.get_relic_home() / "decision_events.jsonl"` so it follows the same `RELIC_HOME`-aware rule as the UI, then accept the same optional fields and write them into:

- `DecisionEvent(...)`;
- Chronicle `cron_decision` payload.

Initial behavior: pass `decision_type`, leave policy fields `None`.

Add round-trip and path tests:

```python
def test_decision_event_round_trip_preserves_optional_fields():
    ...

def test_emit_decision_event_uses_relic_home_path(...):
    ...
```

**Step 5: Repoint UI reader without breaking current counts**

This step happens only after Step 4 is complete and the Python writer already uses `relic.paths.get_relic_home()`. Do not repoint the UI first.

In `ui/lib/workbench-data.ts`, replace:

```ts
path.join(hermesHome, "workspace", "gumi", "cron", "checkin_decision_log.jsonl")
```

with a `RELIC_HOME`-aware decision event path that matches the writer contract. Use a new helper just for this log path:

```ts
path.join(relicHomeStrict(), "decision_events.jsonl")
```

Keep existing `relicHome()` unchanged for the rest of the UI so `.relic-live` dev behavior does not break. Add a separate `relicHomeStrict()` and align it to `relic/paths.py:get_relic_home()`:

- `process.env.RELIC_HOME` wins when set;
- otherwise default to `path.join(process.env.HOME || "", ".relic")`;
- do not use the current `.relic-live` fallback for this one path contract.

Add a contract test that sets `RELIC_HOME=tmp_path`, writes an event via `emit_decision_event()`, then asserts `relicHomeStrict()` points at the same file while `relicHome()` remains untouched for existing callers.

Extend `CheckinEntry` with:

```ts
event_kind?: string;
posture?: string;
outcome_status?: string;
wake_agent_emitted?: boolean;
```

Define the interim Task 1 `pending_proactive_count` semantics explicitly after the repoint:

- count entries where `decision == "DELIVER"` and `outcome_status != "silent"`;
- keep it decision-type agnostic until Task 9 makes the proactive queue path the sole producer;
- add a fixture test that documents the expected jump from the current broken baseline (`0`) to the repointed count.

Until Task 4b lands, `outcome_status` will usually be `None`, so this degrades intentionally to "count DELIVER entries".

Record that semantic switch as part of Task 9, not Task 1.

**Step 6: Run focused tests**

Run:

```bash
rtk pytest tests/gumi_plugin/test_decision_log_canonical.py tests/hermes/test_no_agent_cron_wiring.py -q
```

Expected: pass.

Also verify the reader/writer path contract explicitly:

```bash
rtk pytest tests/gumi_plugin/test_decision_log_canonical.py -q -k path
```

**Step 7: Commit**

```bash
rtk git add relic/gumi_plugin/cron_wiring.py relic/hermes_runtime.py ui/lib/workbench-data.ts tests/gumi_plugin/test_decision_log_canonical.py tests/hermes/test_no_agent_cron_wiring.py
rtk git commit -m "feat: canonicalize cron decision logging"
```

---

### Task 2: Hermes `wakeAgent:false` Gate Contract

**Files:**
- Modify: `relic/gumi_plugin/cron_wiring.py`
- Test: `tests/gumi_plugin/test_wake_agent_gate.py`

**Step 1: Write failing script-render tests**

Create `tests/gumi_plugin/test_wake_agent_gate.py`:

```python
from pathlib import Path

from relic.gumi_plugin.cron_wiring import render_no_agent_script


def test_rendered_script_can_emit_wake_agent_false(tmp_path: Path):
    script = render_no_agent_script(tmp_path / "relic_checkin_decision.sh")
    assert '"wakeAgent": false' in script
    assert '"wakeAgent": true' in script
    assert "RELIC_HERMES_WAKE_AGENT_JSON" in script
```

**Step 2: Run failure**

```bash
rtk pytest tests/gumi_plugin/test_wake_agent_gate.py -q
```

Expected: fail because the script still only uses empty stdout / text stdout.

**Step 3: Add opt-in JSON gate mode**

Do not break existing no-agent cron behavior. In rendered script, add env flag:

```bash
RELIC_HERMES_WAKE_AGENT_JSON="${RELIC_HERMES_WAKE_AGENT_JSON:-0}"
```

In Python heredoc, when `decision != RuntimeDecision.DELIVER` and env flag is true:

```python
print(json.dumps({"wakeAgent": False, "reason": decision.value}))
sys.exit(0)
```

When deliverable and env flag is true:

```python
print(json.dumps({
    "wakeAgent": True,
    "context": {
        "gate_output": candidate_data["message"],
        "deliver_context": build_deliver_context(...),
        "decision_type": decision_type,
    },
}))
sys.exit(0)
```

Keep legacy behavior when env flag is false.

Contract for this task:

- JSON mode emits only JSON, never mixed text stdout;
- legacy mode emits only the current text stdout contract;
- `wake_agent_emitted` is sourced from the rendered script branch taken, then passed into `emit_decision_event()`.
- In JSON mode, every debug `print()` in the Python heredoc and every shell `echo` in the rendered script must go to stderr, not stdout.

Add a test that executes the rendered script in JSON mode and asserts stdout parses as one JSON object with no extra lines.

**Step 4: Run focused tests**

```bash
rtk pytest tests/gumi_plugin/test_wake_agent_gate.py tests/hermes/test_no_agent_cron_wiring.py -q
```

Expected: pass.

**Step 5: Commit**

```bash
rtk git add relic/gumi_plugin/cron_wiring.py tests/gumi_plugin/test_wake_agent_gate.py
rtk git commit -m "feat: add wakeAgent cron gate contract"
```

---

### Task 3: Policy Types and Deterministic Stub

**Files:**
- Create: `relic/checkin/policy.py`
- Test: `tests/checkin/test_policy.py`

**Step 1: Write tests**

Create `tests/checkin/test_policy.py`:

```python
from relic.checkin.policy import CheckinFeatures, EventType, Posture, select_decision


def test_risk_flag_short_circuits_to_silent():
    f = CheckinFeatures(risk_flag_active=True)
    d = select_decision(f, decision_type="checkin")
    assert d.event_type is EventType.SILENT
    assert d.posture is Posture.QUIET


def test_stub_defaults_to_silent_until_policy_enabled():
    f = CheckinFeatures()
    d = select_decision(f, decision_type="checkin", policy_enabled=False)
    assert d.event_type is EventType.SILENT
    assert d.posture is Posture.QUIET
```

**Step 2: Run failure**

```bash
rtk pytest tests/checkin/test_policy.py -q
```

Expected: fail because module does not exist.

**Step 3: Implement minimal module**

Create `relic/checkin/policy.py` with:

- `EventType(str, Enum)`;
- `Posture(str, Enum)`;
- `CheckinFeatures(dataclass)`;
- `Decision(dataclass)`;
- `select_decision(...)`.

Defaults must be conservative:

```python
def select_decision(f, *, decision_type: str, policy_enabled: bool = False) -> Decision:
    if f.risk_flag_active or not policy_enabled:
        return Decision(EventType.SILENT, Posture.QUIET, "risk_or_disabled")
```

**Step 4: Run tests**

```bash
rtk pytest tests/checkin/test_policy.py -q
```

Expected: pass.

**Step 5: Commit**

```bash
rtk git add relic/checkin/policy.py tests/checkin/test_policy.py
rtk git commit -m "feat: add checkin policy types"
```

---

### Task 4: Feature Assembly and Cadence State

**Files:**
- Create: `relic/checkin/features.py`
- Modify: `relic/checkin/db_init.py`
- Modify: `relic/checkin/reply_capture.py`
- Modify: `relic/db/migrations/<next>_checkin_naturalness.sql`
- Test: `tests/checkin/test_features.py`
- Test: `tests/checkin/test_cadence_damping.py`
- Test: `tests/checkin/test_reply_capture_latency.py`

**Step 1: Write feature shape tests**

Create `tests/checkin/test_features.py`:

```python
from pathlib import Path

from relic.checkin.features import build_checkin_features


def test_build_features_returns_defaults_without_state(tmp_path: Path):
    features = build_checkin_features(
        subject_id="s1",
        decision_type="checkin",
        relic_home=tmp_path / "relic",
        hermes_home=tmp_path / "hermes",
    )
    assert features.non_response_streak == 0
    assert features.followup_non_response_streak == 0
    assert features.reach_score == 1.0
```

**Step 2: Write cadence tests**

Create `tests/checkin/test_cadence_damping.py`:

```python
from datetime import datetime, timedelta, timezone

from relic.checkin.features import CadenceState, reconcile_cadence_outcome


def test_unanswered_transition_increments_once():
    state = CadenceState(subject_id="s1")
    event = {"outcome_status_before": "delivered", "outcome_status": "unanswered_24h", "decision_type": "checkin"}
    new_state = reconcile_cadence_outcome(state, event)
    assert new_state.non_response_streak == 1


def test_silent_tick_does_not_increment():
    state = CadenceState(subject_id="s1", non_response_streak=2)
    event = {"outcome_status": "silent", "decision_type": "checkin"}
    new_state = reconcile_cadence_outcome(state, event)
    assert new_state.non_response_streak == 2


def test_boundary_sets_cap_without_reset():
    state = CadenceState(subject_id="s1", non_response_streak=3)
    new_state = reconcile_cadence_outcome(state, {"boundary_frequency_cap_per_day": 1})
    assert new_state.non_response_streak == 3
    assert new_state.frequency_cap_per_day == 1


def test_decay_requires_recent_subject_message():
    old = datetime.now(timezone.utc) - timedelta(days=8)
    state = CadenceState(
        subject_id="s1",
        non_response_streak=3,
        last_delivered_initiative_at=old,
        last_subject_msg_at=datetime.now(timezone.utc) - timedelta(days=2),
    )
    assert reconcile_cadence_outcome(state, {"now": datetime.now(timezone.utc)}).non_response_streak == 2


def test_followup_multiplier_reduces_reach_score_more_aggressively():
    assert compute_reach_score(1, 2) < 0.7
```

**Step 3: Run failure**

```bash
rtk pytest tests/checkin/test_features.py tests/checkin/test_cadence_damping.py -q
```

Expected: fail because `features.py` does not exist.

**Step 4: Add schema**

In `relic/checkin/db_init.py` and the next SQL migration, add:

```sql
CREATE TABLE IF NOT EXISTS checkin_cadence_state (...);
CREATE TABLE IF NOT EXISTS checkin_features (...);
ALTER TABLE checkin_exchanges ADD COLUMN posture TEXT;
ALTER TABLE checkin_exchanges ADD COLUMN response_latency_seconds INTEGER;
```

Use the schema from `docs/spikes/cron-checkin-naturalness-spike-claude.md` §11.1.

**Step 5: Implement features module**

Create:

- `CadenceState(dataclass)`;
- `PersistedFeatures(dataclass)` or equivalent row/result type;
- `load_cadence_state(conn, subject_id)`;
- `save_cadence_state(conn, state)`;
- `persist_features(conn, subject_id, tick_id, features, posture) -> int`;
- `reconcile_cadence_outcome(state, event)`;
- `compute_reach_score(non_response_streak, followup_non_response_streak)`;
- `build_checkin_features(...)`;
- `backfill_from_decision_log(path, conn)` for database state only, not for rewriting the append-only JSONL log;
- `normalize_decision_event_dict(event)` to supply missing optional keys in memory for replay/reader compatibility.

Document the `reconcile_cadence_outcome()` event dict contract in the module docstring and reuse it everywhere:

```python
{
    "outcome_status": str | None,
    "outcome_status_before": str | None,
    "decision_type": str | None,
    "now": datetime | None,
    "boundary_frequency_cap_per_day": int | None,
}
```

Do not read raw message content except counts/timestamps from Hermes `state.db`.
Do not rewrite historical `decision_events.jsonl` entries. Older records remain append-only and sparse; replay/read paths must tolerate missing keys via `normalize_decision_event_dict(...)`.

Explicitly wire the high-signal fields that later policy tasks depend on:

- `salience_top` from `relic/memory_dynamics/decay.py` or its current salience helper;
- `topic_freshness` from `relic/checkin/anti_repeat.py` / anti-repeat state;
- `subject_avg_tokens_14d` from Hermes `state.db`;
- `importance_accumulator` as a real source if available, else pin it to `0.0` until reflection work lands.
- `facet_status` from the current facet/question selection path or `None` if no facet is active;
- `asked_recently_12h` from `checkin_exchanges.asked_at`;
- `last_reflect_age_days` from the most recent persisted reflective posture in `checkin_features`.

Add focused tests for each populated source rather than only the all-defaults shape test.

Persistence requirement for this task:

- `persist_features(...)` inserts a row into `checkin_features`;
- returns the inserted `id`;
- later tasks use that `features_id` in canonical decision events;
- `posture_history_last_5` is derived from persisted rows, not from in-memory state.

**Step 6: Add reply-capture latency write**

In `relic/checkin/reply_capture.py`, when a reply is captured:

- extend the pending-exchange SELECT to load both `id` and `asked_at`;
- parse both timestamps with `datetime.fromisoformat(...)`;
- if either timestamp is malformed or naive, leave `response_latency_seconds = NULL`;
- otherwise normalize to UTC with `.astimezone(timezone.utc)` and write `response_latency_seconds = int((reply_captured_at - asked_at).total_seconds())`.
- after a successful capture, reset cadence state by calling `reconcile_cadence_outcome(...)` with an `answered` event and persisting the result, so `non_response_streak` and `followup_non_response_streak` recover on first reply.

Add a focused test:

```python
def test_capture_reply_sets_response_latency_seconds(...):
    ...

def test_capture_reply_leaves_latency_null_for_malformed_asked_at(...):
    ...

def test_reply_capture_resets_cadence_streak(...):
    ...
```

**Step 7: Run tests**

```bash
rtk pytest tests/checkin/test_features.py tests/checkin/test_cadence_damping.py tests/checkin/test_reply_capture_latency.py tests/checkin/test_context_builder.py -q
```

Expected: pass.

**Step 8: Commit**

```bash
rtk git add relic/checkin/features.py relic/checkin/db_init.py relic/checkin/reply_capture.py relic/db/migrations tests/checkin/test_features.py tests/checkin/test_cadence_damping.py tests/checkin/test_reply_capture_latency.py
rtk git commit -m "feat: add checkin feature and cadence state"
```

---

### Task 4b: Outcome Reconciler for `delivered -> unanswered_24h`

**Files:**
- Create: `relic/checkin/outcome_reconciler.py`
- Modify: `relic/gumi_plugin/cron_wiring.py`
- Test: `tests/checkin/test_outcome_reconciler.py`

**Step 1: Write failing end-to-end reconciliation tests**

Create `tests/checkin/test_outcome_reconciler.py` covering:

- delivered event older than 24h with no subject reply becomes `unanswered_24h`;
- a reply before the deadline prevents the transition;
- reconciling the same event twice is idempotent;
- after reconciliation, `checkin_cadence_state.non_response_streak` increments once.

**Step 2: Run failure**

```bash
rtk pytest tests/checkin/test_outcome_reconciler.py -q
```

Expected: fail because no reconciler exists.

**Step 3: Implement the reconciler**

Create `relic/checkin/outcome_reconciler.py` with:

- scan functions over Chronicle via `relic/chronicle/reader.py` when available, with JSONL mirror fallback only if the Chronicle read path is unavailable in the execution context;
- `reconcile_due_outcomes(subject_id, relic_home, now)` that finds canonical decision events with:
  - `outcome_status == "delivered"`,
  - `response_deadline_at <= now`,
  - no subject reply recorded for the delivery window, where reply is defined as any subject-authored message in Hermes `state.db` with timestamp in `[delivered_at, response_deadline_at]`, not only `checkin_exchanges` rows;
- emission of a follow-up canonical event with:

```python
{
    "outcome_status_before": "delivered",
    "outcome_status": "unanswered_24h",
    ...
}
```

- a call into `reconcile_cadence_outcome()` plus persistence via `save_cadence_state()`.

State explicitly in the implementation notes which source won for the milestone:

- preferred: Chronicle reader;
- fallback: `decision_events.jsonl` mirror.

Add an end-to-end test for a non-ask delivery:

- emit `(checkin, observe)` with `outcome_status="delivered"`;
- insert a subject message in Hermes `state.db` at `+23h`;
- run the reconciler;
- assert no `unanswered_24h` transition is emitted and streak does not increment.

**Step 4: Wire the reconciler into runtime**

Before policy evaluation on each tick, run a cheap reconciliation pass for the subject so stale delivered events are materialized before `build_checkin_features()` reads cadence state.

**Step 5: Run tests**

```bash
rtk pytest tests/checkin/test_outcome_reconciler.py tests/checkin/test_cadence_damping.py -q
```

Expected: pass.

**Step 6: Commit**

```bash
rtk git add relic/checkin/outcome_reconciler.py relic/gumi_plugin/cron_wiring.py tests/checkin/test_outcome_reconciler.py
rtk git commit -m "feat: reconcile unanswered checkin outcomes"
```

---

### Task 5: Minimal Policy Behavior

**Files:**
- Modify: `relic/checkin/policy.py`
- Test: `tests/checkin/test_policy.py`
- Test: `tests/checkin/test_policy_scenarios.py`

**Step 1: Add scenario tests**

Append threshold tests to `tests/checkin/test_policy.py` and create `tests/checkin/test_policy_scenarios.py` for the spike scenarios:

```python
def test_reach_below_threshold_goes_silent():
    f = CheckinFeatures(non_response_streak=3, reach_score=0.343)
    d = select_decision(f, decision_type="checkin", policy_enabled=True)
    assert d.event_type is EventType.SILENT


def test_checkin_observe_default_when_enabled():
    f = CheckinFeatures(reach_score=1.0, time_since_last_subject_msg_sec=3600)
    d = select_decision(f, decision_type="checkin", policy_enabled=True)
    assert d.event_type is EventType.CHECKIN
    assert d.posture is Posture.OBSERVE


def test_proactivity_requires_salience():
    f = CheckinFeatures(reach_score=1.0, salience_top=0.7, time_since_last_subject_msg_sec=7200)
    d = select_decision(f, decision_type="proactivity", policy_enabled=True)
    assert d.event_type is EventType.PROACTIVE
    assert d.posture is Posture.BRIEF_SHARE
```

`tests/checkin/test_policy_scenarios.py` should pin the named scenarios from spike §12.3 / §15 and assert:

- expected `(EventType, Posture)`;
- expected constraint header fragments;
- reflection remains disabled by default unless explicitly enabled.

**Step 2: Run failure**

```bash
rtk pytest tests/checkin/test_policy.py -q
```

Expected: fail until policy thresholds are implemented.

**Step 3: Implement thresholds**

Use:

```python
REACH_THRESHOLD = 0.35
PROACTIVE_SALIENCE_THRESHOLD = 0.6
REFLECT_THRESHOLD = 0.8
BRIEF_SHARE_THRESHOLD = 0.4
```

Implement the §9.2 decision tree from the spike. Keep `policy_enabled=False` default until wiring is explicitly enabled.
Also apply the conservative default from spike §15:

```python
if decision.event_type is EventType.REFLECTION and not reflection_enabled:
    return Decision(EventType.SILENT, Posture.QUIET, "reflection_disabled")
```

Before implementing helper-style branches from the spike pseudocode, either:

- add corresponding fields to `CheckinFeatures` and populate them in Task 4:
  - `facet_status: str | None`
  - `asked_recently_12h: bool`
  - `last_reflect_age_days: int | None`
- or rewrite those branches to use already-populated fields and document that substitution in code comments/tests.

**Step 4: Run tests**

```bash
rtk pytest tests/checkin/test_policy.py tests/checkin/test_policy_scenarios.py tests/checkin/test_cadence_damping.py -q
```

Expected: pass.

**Step 5: Commit**

```bash
rtk git add relic/checkin/policy.py tests/checkin/test_policy.py tests/checkin/test_policy_scenarios.py
rtk git commit -m "feat: implement minimal checkin policy"
```

---

### Task 6: Posture-Filtered Context Builder

**Files:**
- Modify: `relic/checkin/context_builder.py`
- Test: `tests/checkin/test_context_builder.py`

**Step 1: Add tests**

Append tests:

```python
from relic.checkin.topic_hint import HEADER as TOPIC_HINT_HEADER


def test_silent_posture_returns_empty_context(hermes_home, relic_dir):
    _write_consent(relic_dir, active=True)
    result = build_deliver_context("test_subj", hermes_home, relic_dir, event_type="silent", posture="quiet")
    assert result == ""


def test_checkin_observe_omits_topic_hint(hermes_home, relic_dir):
    _write_consent(relic_dir, active=True)
    result = build_deliver_context("test_subj", hermes_home, relic_dir, event_type="checkin", posture="observe")
    assert TOPIC_HINT_HEADER not in result
```

**Step 2: Run failure**

```bash
rtk pytest tests/checkin/test_context_builder.py -q
```

Expected: fail because `build_deliver_context()` does not accept event/posture args.

**Step 3: Add optional parameters**

Change signature:

```python
def build_deliver_context(subject_id, hermes_home, relic_home=None, *, event_type=None, posture=None, policy_packet=None) -> str:
```

Preserve existing behavior when `event_type is None and posture is None`.

Add a section selection map based on §10.2 of the spike.

**Step 4: Run tests**

```bash
rtk pytest tests/checkin/test_context_builder.py tests/profile/test_checkin_prompt_contract.py -q
```

Expected: pass.

**Step 5: Commit**

```bash
rtk git add relic/checkin/context_builder.py tests/checkin/test_context_builder.py
rtk git commit -m "feat: filter checkin context by posture"
```

---

### Task 6b: Constraint Header Injection

**Files:**
- Modify: `relic/checkin/policy.py`
- Modify: `relic/profile/registry.py`
- Test: `tests/profile/test_checkin_prompt_contract.py`
- Test: `tests/checkin/test_policy_scenarios.py`

**Step 1: Add failing prompt-contract tests**

Add tests asserting that for non-silent policy outcomes the rendered prompt handed to the composer contains a deterministic header such as:

```text
[EVENTO: checkin] [POSTURA: observe] [VINCOLI: max 2 frasi; senza domanda]
```

and, when required:

```text
[GROUNDING: ...]
```

**Step 2: Run failure**

```bash
rtk pytest tests/profile/test_checkin_prompt_contract.py tests/checkin/test_policy_scenarios.py -q
```

Expected: fail because no header is injected yet.

**Step 3: Implement rendering and injection**

Create a deterministic helper such as:

```python
render_constraint_header(event_type, posture, *, max_sentences, with_question, grounding) -> str
```

Then prepend it at the actual prompt insertion point used by `registry.gumi_checkin_message` or the equivalent composer entry point. This task is where posture becomes behaviorally observable to the LLM, not just logged metadata.

**Step 4: Run tests**

```bash
rtk pytest tests/profile/test_checkin_prompt_contract.py tests/checkin/test_policy_scenarios.py tests/checkin/test_context_builder.py -q
```

Expected: pass.

**Step 5: Commit**

```bash
rtk git add relic/checkin/policy.py relic/profile/registry.py tests/profile/test_checkin_prompt_contract.py tests/checkin/test_policy_scenarios.py
rtk git commit -m "feat: inject checkin constraint headers"
```

---

### Task 7: Wire Policy Behind an Opt-In Flag

**Files:**
- Modify: `relic/gumi_plugin/cron_wiring.py`
- Test: `tests/gumi_plugin/test_policy_wiring.py`
- Test: `tests/hermes/test_no_agent_cron_wiring.py`

**Step 1: Write tests**

Create `tests/gumi_plugin/test_policy_wiring.py`:

```python
from unittest.mock import patch

from relic.gumi_plugin.cron_wiring import make_decision
from relic.hermes_runtime import RuntimeDecision


def test_policy_disabled_preserves_current_deliver_shape(monkeypatch):
    monkeypatch.delenv("RELIC_CHECKIN_POLICY_ENABLED", raising=False)
    with patch("relic.gumi_plugin.cron_wiring._evaluate_decision") as eval_mock:
        eval_mock.return_value = (RuntimeDecision.DELIVER, [], {"message": "DELIVER\ntipo: text"})
        decision, _, data = make_decision("s1", "g1", "p1", decision_type="checkin")
    assert decision == RuntimeDecision.DELIVER
    assert data["message"].startswith("DELIVER")


def test_policy_enabled_silent_returns_no_reply(monkeypatch):
    monkeypatch.setenv("RELIC_CHECKIN_POLICY_ENABLED", "1")
    with patch("relic.gumi_plugin.cron_wiring._evaluate_decision") as eval_mock:
        eval_mock.return_value = (RuntimeDecision.DELIVER, [], {"message": "DELIVER\ntipo: text"})
        with patch("relic.gumi_plugin.cron_wiring.select_decision") as select_mock:
            from relic.checkin.policy import Decision, EventType, Posture
            select_mock.return_value = Decision(EventType.SILENT, Posture.QUIET, "test")
            decision, _, data = make_decision("s1", "g1", "p1", decision_type="checkin")
    assert decision == RuntimeDecision.NO_REPLY
    assert data is None
```

**Step 2: Run failure**

```bash
rtk pytest tests/gumi_plugin/test_policy_wiring.py -q
```

Expected: fail until wiring exists.

**Step 3: Implement opt-in wiring**

In `cron_wiring.make_decision()`:

- after `_evaluate_decision()` returns `DELIVER`;
- if `RELIC_CHECKIN_POLICY_ENABLED` is true:
  - build features;
  - call `select_decision(..., policy_enabled=True)`;
  - if silent, emit `NO_REPLY`;
  - otherwise append `event_type`, `posture`, and `features_id` to candidate data and to the audit event;
  - call `persist_features(...)` and pass the returned `features_id` downstream.

Constraint header rendering is implemented in Task 6b, not in this task. Here the requirement is only to carry enough metadata for Task 6b to inject it deterministically.

Do not enable by default.
Use the existing path resolution helpers / env contract already present in runtime code for `RELIC_HOME` and Hermes profile home; do not introduce a second ad hoc resolver in this task.

**Step 4: Run tests**

```bash
rtk pytest tests/gumi_plugin/test_policy_wiring.py tests/hermes/test_no_agent_cron_wiring.py tests/checkin/test_policy.py -q
```

Expected: pass.

**Step 5: Commit**

```bash
rtk git add relic/gumi_plugin/cron_wiring.py tests/gumi_plugin/test_policy_wiring.py
rtk git commit -m "feat: wire checkin policy behind flag"
```

---

### Task 8: Follow-up Postures

**Files:**
- Modify: `relic/checkin/policy.py`
- Modify: `relic/checkin/context_builder.py`
- Test: `tests/checkin/test_followup_posture.py`

**Step 1: Write tests**

Create tests asserting:

- `decision_type="followup"` with `non_response_streak=0` returns `(followup, follow_up_warm)`;
- with `non_response_streak>0` returns `(followup, follow_up_terse)`;
- follow-up context includes last answered exchange and excludes observations unless required.

**Step 2: Run failure**

```bash
rtk pytest tests/checkin/test_followup_posture.py -q
```

Expected: fail until context section exists.

**Step 3: Implement last-exchange section**

In `context_builder.py`, add:

```python
def build_last_exchange_section(db_path: Path) -> str:
    ...
```

Query latest `checkin_exchanges` row with `reply_text IS NOT NULL`, but return only bounded, non-raw summary fields or short excerpts already allowed by consent.
Pin the returned shape in the tests, for example:

```python
{
    "question_text": "...",
    "reply_excerpt": "...",
    "asked_at": "...",
    "reply_captured_at": "...",
    "response_latency_seconds": 1800,
    "posture": "follow_up_warm",
}
```

Hard limits:

- no full transcript block;
- excerpt length cap;
- no observations/facets unless the posture explicitly needs them.

**Step 4: Run tests**

```bash
rtk pytest tests/checkin/test_followup_posture.py tests/checkin/test_context_builder.py -q
```

Expected: pass.

**Step 5: Commit**

```bash
rtk git add relic/checkin/policy.py relic/checkin/context_builder.py tests/checkin/test_followup_posture.py
rtk git commit -m "feat: add followup postures"
```

---

### Task 9: Proactive Queue Consumer

**Files:**
- Modify: `relic/shared_continuity/service.py`
- Create: `relic/gumi_plugin/proactive_consumer.py`
- Modify: `relic/gumi_plugin/cron_wiring.py`
- Test: `tests/gumi_plugin/test_proactive_consumer.py`

**Step 1: Write tests**

Create tests for:

- expired candidate is skipped;
- low salience candidate returns no delivery;
- high salience candidate calls policy with `decision_type="proactivity"`;
- queue file is rewritten without consumed/expired entries.
- when `RELIC_PROACTIVE_QUEUE_ENABLED=1`, only one proactivity producer is active.

**Step 2: Run failure**

```bash
rtk pytest tests/gumi_plugin/test_proactive_consumer.py -q
```

Expected: fail.

**Step 3: Implement queue model**

Use `RELIC_HOME/subjects/<id>/proactive_queue.jsonl` if `RELIC_HOME` is set, else `~/.relic/subjects/<id>/proactive_queue.jsonl`.

Functions:

- `load_candidates(path)`;
- `save_candidates(path, candidates)`;
- `consume_one(subject_id, hermes_home, relic_home) -> tuple[RuntimeDecision, list[RuntimeDecisionReason], Optional[dict]]`.

Do not send directly. Return the same tuple shape as `make_decision()` so it can slot into the same downstream dispatch path.

**Step 4: Add the producer side in continuity**

In `relic/shared_continuity/service.py`, expose an explicit `enqueue_proactive_candidate(...)` producer that writes `ProactiveCandidate` entries into `subjects/<id>/proactive_queue.jsonl`. Do not add broad polling or implicit candidate detection in this task. Cover:

- signal shape;
- salience/priority floor;
- expiry;
- dedupe key.

Add at least one concrete caller or integration fixture for this task so the queue is not only unit-tested in isolation. A documented test path `enqueue -> consume_one -> emit decision` is sufficient for the first milestone.

**Step 5: Switch to a single active proactivity lane**

In `cron_wiring.provision_for_subject()`:

- when `RELIC_PROACTIVE_QUEUE_ENABLED=0`, keep the legacy `relic_proactivity_decision.sh` lane;
- when `RELIC_PROACTIVE_QUEUE_ENABLED=1`, install the consumer lane and skip or stub the legacy proactivity script.

Add a wiring test that asserts exactly one proactivity producer is active for each flag value.

**Step 6: Run tests**

```bash
rtk pytest tests/gumi_plugin/test_proactive_consumer.py tests/hermes/test_no_agent_cron_wiring.py -q
```

Expected: pass.

**Step 7: Commit**

```bash
rtk git add relic/shared_continuity/service.py relic/gumi_plugin/proactive_consumer.py relic/gumi_plugin/cron_wiring.py tests/gumi_plugin/test_proactive_consumer.py
rtk git commit -m "feat: add proactive queue consumer"
```

---

### Task 10: Replay Harness

**Files:**
- Create: `tools/replay_decisions.py`
- Test: `tests/checkin/test_replay_decisions.py`

**Step 1: Write tests**

Create a temp JSONL with two feature records and assert replay produces byte-stable decisions.

**Step 2: Run failure**

```bash
rtk pytest tests/checkin/test_replay_decisions.py -q
```

Expected: fail.

**Step 3: Implement CLI**

`tools/replay_decisions.py` should:

- read JSONL decision events;
- extract `features_json` or dereference `features_id` if DB path provided;
- call `select_decision`;
- write JSONL output with `event_id`, old/new event kind, old/new posture, and changed flag.

Support:

```bash
python tools/replay_decisions.py --input .agent-outs/sample_decisions.jsonl --output .agent-outs/replay.jsonl
```

**Step 4: Run tests**

```bash
rtk pytest tests/checkin/test_replay_decisions.py -q
```

Expected: pass.

**Step 5: Commit**

```bash
rtk git add tools/replay_decisions.py tests/checkin/test_replay_decisions.py
rtk git commit -m "feat: add checkin decision replay"
```

---

### Task 11: Metrics and CI Checks

**Files:**
- Create: `relic/checkin/metrics.py`
- Modify: `.github/workflows/ci.yml`
- Test: `tests/checkin/test_metrics.py`

**Step 1: Write tests**

Cover:

- Jaccard repetition under/over threshold;
- posture entropy;
- silent rate band;
- wakeAgent emission rate vs silent posture count.

**Step 2: Run failure**

```bash
rtk pytest tests/checkin/test_metrics.py -q
```

Expected: fail.

**Step 3: Implement metrics**

Create pure functions:

- `message_jaccard(a, b)`;
- `rolling_repetition_rate(messages)`;
- `posture_entropy(postures)`;
- `silent_rate(events)`;
- `wake_agent_consistency(events)`.

**Step 4: Run tests**

```bash
rtk pytest tests/checkin/test_metrics.py -q
```

Expected: pass.

**Step 5: Add optional full check command to docs**

Append this verification command to the spike or README section for this work:

```bash
rtk pytest tests/checkin tests/gumi_plugin tests/hermes/test_no_agent_cron_wiring.py tests/profile/test_checkin_prompt_contract.py -q
```

**Step 6: Wire metrics into CI**

In `.github/workflows/ci.yml`, extend the existing GitHub Actions job `jobs.ci.steps[name=Test]` or add a clearly named dedicated job `checkin-naturalness` that runs:

```bash
rtk pytest tests/checkin/test_metrics.py tests/checkin/test_policy_scenarios.py tests/gumi_plugin/test_decision_log_canonical.py -q
```

**Step 7: Commit**

```bash
rtk git add relic/checkin/metrics.py tests/checkin/test_metrics.py .github/workflows/ci.yml docs/spikes/cron-checkin-naturalness-spike-claude.md
rtk git commit -m "test: add checkin naturalness metrics"
```

---

### Task 12: Manual Rollout Checklist

**Files:**
- Modify: `docs/spikes/cron-checkin-naturalness-spike-claude.md`
- Create: `docs/runbooks/gumi-checkin-policy-rollout.md`

**Step 1: Write runbook**

Create a runbook with:

1. Verify existing cron jobs.
2. Enable logging fields with policy disabled.
3. Enable `RELIC_HERMES_WAKE_AGENT_JSON=1` on one test profile.
4. Enable `RELIC_CHECKIN_POLICY_ENABLED=1` on one test profile.
5. Inspect Chronicle events and `decision_events.jsonl`.
6. Run replay harness.
7. Review 20 decisions manually.
8. Roll back by disabling env flags.

**Step 2: Verify docs references**

Run:

```bash
rtk rg -n "RELIC_CHECKIN_POLICY_ENABLED|RELIC_HERMES_WAKE_AGENT_JSON|replay_decisions|checkin_cadence_state" docs
```

Expected: references appear in spike, plan, and runbook.

Runbook should include concrete operator commands, for example:

```bash
rtk python - <<'PY'
from pathlib import Path
import os
path = Path(os.environ.get("RELIC_HOME", str(Path.home() / ".relic"))) / "decision_events.jsonl"
print(path)
PY
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

Also document that `pending_proactive_count` may jump from a broken historical `0` baseline after the UI repoint because the previous file had no in-repo writer.

**Step 3: Commit**

```bash
rtk git add docs/runbooks/gumi-checkin-policy-rollout.md docs/spikes/cron-checkin-naturalness-spike-claude.md docs/plans/2026-05-18-cron-checkin-naturalness-implementation.md
rtk git commit -m "docs: add checkin policy rollout plan"
```

---

## Final Verification

After all tasks:

```bash
rtk pytest tests/checkin tests/gumi_plugin tests/hermes/test_no_agent_cron_wiring.py tests/profile/test_checkin_prompt_contract.py -q
rtk ruff check relic/checkin relic/gumi_plugin tests/checkin tests/gumi_plugin
if rtk rg -n 'checkin_decision_log\.jsonl' ui; then exit 1; fi
```

Expected:

- pytest exits 0;
- ruff exits 0;
- no UI reader references `$HERMES_HOME/workspace/gumi/cron/checkin_decision_log.jsonl`;
- `decision_events.jsonl` and Chronicle events include `decision_type`, `event_kind`, `posture`, `outcome_status`, `non_response_streak`, `followup_non_response_streak`, and `reach_score`;
- policy remains disabled by default unless explicitly enabled by env flag.
