# Spike — Cron Check-in Naturalness Redesign

**Author:** Claude Opus 4.7 (research+technical spike, no implementation)
**Date:** 2026-05-18
**Branch:** `safety-warning-governance`
**Source prompt:** `cron-checkin-naturalness-spike-claude_prompt.md` (repo root)
**Status:** Spike complete for human review. Detailed implementation plan: `docs/plans/2026-05-18-cron-checkin-naturalness-implementation.md`. Do not implement before sign-off on Open Questions (§15).

---

## 1. Executive Summary

### What is wrong today

Gumi's cron-driven outreach is gate-gated by safety and consent (good) but, once the gate decides `DELIVER`, the rest of the pipeline collapses into a single behavior: build a context blob, hand it to an LLM with a long Italian prompt, and let the LLM choose surface form. Three things follow:

1. **Three decision types, one evaluator.** `relic/gumi_plugin/cron_wiring.py:1000` declares `decision_types = ["checkin", "followup", "proactivity"]` and provisions three separate cron scripts, but all three call `make_decision()` → `_evaluate_decision()` (`cron_wiring.py:568–638`), which applies the same gate logic regardless of decision type. The "proactivity" lane is a name, not a behavior. There is no distinct surface for *opportunistic* outreach.
2. **"Ask" is a probability roll, not a posture.** `_select_ask_decision()` (`cron_wiring.py:70–141`) gates ask-mode behind three gates: `select_facet()=='ask_now'`, a 12 h cooldown, and a 35 % deterministic daily roll. When the roll says yes, the prompt switches into "ask" mode; otherwise it does not. There is no concept of *observing*, *briefly sharing*, *reflecting*, *reminding*, or *deliberately remaining silent because the human is busy*. There is `ask` or `not ask`.
3. **Non-response is invisible.** When the subject does not reply, nothing in the loop updates: `checkin_exchanges.reply_captured_at` stays `NULL`, but no feature feeds back into the next tick's decision. Salience decay exists (`relic/memory_dynamics/decay.py`) but is disconnected from cron scheduling. The system can ring the bell at the same cadence for days regardless of whether anyone is on the other end.

### Most promising direction

Insert a **policy layer** between the gate and the prompt:

```
cron tick
  → _evaluate_decision()  [safety/consent gate, UNCHANGED]
  → assemble CheckinFeatures vector  [NEW, from already-available state]
  → select_decision(features, decision_type) → (EventType, Posture)  [NEW, pure function, replayable]
  → build_deliver_context(event_type, posture)  [PARAMETERIZED, was unconditional]
  → LLM/composer skill with event/posture-shaped constraint header  [PROMPT CHANGE, not new prompt]
  → checkin_media_dispatcher  [UNCHANGED]
```

The policy returns two orthogonal labels: **EventType** (`silent | checkin | followup | proactive | reminder | reflection`) and **Posture** (`quiet | observe | brief_share | ask | follow_up_warm | follow_up_terse | reflective_mirror | small_share | repair`). Both are chosen from an inspectable feature vector by a *deterministic* policy. Silence is a valid event/posture pair, not a fallback. Proactivity becomes a *separate trigger surface* (event-driven, sourced from `relic/shared_continuity/service.py`), not a sibling cron script with identical logic.

This is not a four-mode rotation. It is a decision tree over signals that already exist in the database, with a few new fields (response latency, posture history, non-response streak) and one new log shape so decisions are offline-replayable.

### What this spike is not

- Not an implementation. §14 lists 11 small steps; none have been written.
- Not a UX redesign. Surface format (text/voice/image/music) stays on `checkin_media_dispatcher`.
- Not a new persona. SOUL.md gains *invariants* (silence is OK, no clinical advice), not new rules.
- Not a model swap. Same Gemini call path, same prompt scaffolding language.

---

## 2. Current Implementation Map

### 2.1 Cron entry → gate → dispatch

```
hermes cron tick (every 30 min, jitter)
  └── ~/.hermes/scripts/<subject_id>/relic_{checkin|followup|proactivity}_decision.sh
       └── python -m relic.gumi_plugin.cron_wiring make-decision --type <T>
            ├── _evaluate_decision()              # cron_wiring.py:568–638
            │     global_pause? PRO_CHECKIN? quiet_hours?
            │     platform_allowlist? subject_pause? continuity_scope?
            │     due_followup? → RuntimeDecision {NO_REPLY|CANDIDATE|DELIVER|BLOCKED}
            ├── if DELIVER: _select_ask_decision()  # cron_wiring.py:70–141
            │     select_facet()=='ask_now' AND 12h cooldown AND 35% daily roll
            │     → (ask: bool, ask_topic: str|None)
            ├── emit DELIVER payload: "DELIVER\ntipo: text\nora: 15:42\n[ask: true\nask_topic: …]"
            └── pipe → hermes cron job that calls LLM with prompt = registry.gumi_checkin_message
                       └── LLM output (could be "[SILENT]")
                            └── checkin_media_dispatcher.py  # parses tipo, dispatches via Telegram
```

### 2.2 Context assembly

`relic/checkin/context_builder.py:302–346` `build_deliver_context()`:

| Section function | Source | Consent-gated |
|---|---|---|
| `build_recent_checkins_section` (`:30–89`) | `MEMORY.md` sync block, last 5 per job | no |
| `build_recent_subject_messages_section` (`:230–285`) | Hermes `state.db` role='user', last 24 h, limit 5, filters `[IMPORTANT:` cron injections | no |
| `build_observations_section` (`:92–125`) | `relic.db` observations, last 30 d, limit 3 | yes |
| `build_topic_hint_section` (`:128–212`) | `question_engine.select_facet()` + `AntiRepeatGate` Jaccard 0.60 | yes |
| `build_style_hints_section` (`:215–227`) | `subject_baseline.json` interaction block | yes |
| `build_avatar_section` (`:288–299`) | `AVATAR_SPEC.md` (≤600 chars) | no |

### 2.3 Facet scoring (the only "what to talk about" model)

`relic/checkin/question_engine.py:257–305` `select_facet()` returns top scorer by:

```
TGS = 0.35 * unknownness
    + 0.25 * impact
    + 0.20 * timeliness
    - 0.20 * intrusion
    - 0.15 * asked_recently
```

If top ≥ 0.30 → `status='ask_now'`. `build_question_hint()` strips clinical scale refs (ECR-R, DERS…) before injection.

### 2.4 [SILENT] short-circuit

Dual-layer:

- **LLM contract** (`relic/profile/registry.py:1394`): prompt instructs the model to reply literally `[SILENT]` if the gate did not emit `DELIVER`.
- **Dispatch grep** (`relic/gumi_plugin/cron_wiring.py:1155, 1180`): `grep -q '^\[SILENT\]'` exits before any Telegram call. Python dispatcher exits on `if llm_output == "[SILENT]"`.

This is robust — but it is *binary*. Either we speak (whatever the LLM produces) or we are entirely absent.

### 2.5 Observability split (writer/reader divergence — verified bug)

Three decision-related stores exist; **the writer the UI thinks it reads from has no producer in this repository**. Confirmed by a Codex second-pass review and re-verified here against current code.

| Store | Path | Written by | Read by |
|---|---|---|---|
| Decision-event JSONL | `~/.relic/decision_events.jsonl` today; Task 1 aligns it to `RELIC_HOME/decision_events.jsonl` if `RELIC_HOME` is set, else `~/.relic/decision_events.jsonl` | `relic/gumi_plugin/cron_wiring.py:660` (inside `emit_decision_event()` at `:640`) | none in repo |
| Chronicle events | Chronicle bus, `event_type="cron_decision"` and `decision_kind="cron_evaluator"` | `cron_wiring.py:670, 683` (via `relic.chronicle.emit_event` / `emit_decision`) | Chronicle consumers |
| UI-expected JSONL | `$HERMES_HOME/workspace/gumi/cron/checkin_decision_log.jsonl` | **no writer found** (`grep -rn checkin_decision_log.jsonl` returns only the UI reader) | `ui/lib/workbench-data.ts:128, 132` |

UI consumer schema (`ui/lib/workbench-data.ts:131–144`):

```ts
type CheckinEntry = {
  status?: 'pending_review' | 'warranted';
  decision?: string;            // text or "[SILENT]"
  timestamp?: string;           // ISO
  created_at?: string;          // ISO
};
```

UI counts `decision !== "[SILENT]"` as `pending_proactive_count` and uses max(timestamp, created_at) as `last_initiative_at`. **Today the UI counts entries from a file nothing writes** — it silently shows zero unless something out-of-tree populates the path. Reconciling the three stores is a prerequisite for any policy redesign (otherwise replay and naturalness metrics measure the wrong surface). This is the first implementation step (§14).

Additional gap: `make_decision()` (`cron_wiring.py:694–741`) takes `(subject_id, gumi_instance_id, hermes_profile_id, force=False)` — **no `decision_type` parameter**. The three shell scripts (`relic_{checkin|followup|proactivity}_decision.sh`) all call the same entry point with no type plumbing, so even the canonical writer cannot distinguish event types in its log.

### 2.6 State Gumi can already read

| Source | Tables / files | Notes |
|---|---|---|
| `relic.db` | `facets` (60 canonical), `traits`, `observations`, `checkin_exchanges`, `hypotheses`, `inbox`, `model_snapshots` | SQLite WAL, FK on |
| Hermes home | `MEMORY.md`, `workspace/gumi/world.md`, `workspace/gumi/relationship_policy.md`, `SOUL.md`, `cron/jobs.json`, `cron/checkin_decision_log.jsonl` | per-profile dir |
| Subject baseline | `baseline_user_profile.json`, `boundary_policy.json`, `subject_baseline.json`, `gumi_sweet_spot_config.json`, `delivery_policy.json`, `consent_record.json` | JSON |
| Hermes state | `state.db` `messages` table (role/content/timestamp) | read-only from cron |

Note: `relic/memory_dynamics/decay.py` defines a `SalienceResult` dataclass with decay calculations. It is **not currently called from the checkin path**. This is a free win.

### 2.7 What must not be touched in this spike

- `_evaluate_decision()` gate ordering (safety-critical: pause, consent, quiet hours).
- `[SILENT]` LLM contract + dispatch grep (retained as composer-side safety net even after `wakeAgent` adoption).
- `checkin_media_dispatcher.parse_gate_output()` schema (`tipo:`, `testo:`, `caption:`, `image_prompt:`).
- Hermes profile layout, `jobs.json` schema, `no_agent` upstream parameter.
- `relic.db` schema for `facets`, `traits`, `observations`, `checkin_exchanges` (additive only).
- Chronicle event-emission contract (additive fields only on `cron_decision`).

---

## 3. Hermes Integration Map

### 3.1 What Hermes provides (verified against installed Hermes v0.11.0 + docs)

> **Correction from initial draft.** This section originally said `--no-agent` was a Relic extension and that Hermes had no upstream policy layer. Both claims were wrong. Re-verified by reading `~/.hermes/hermes-agent/` source.

- **Profile = isolated `HERMES_HOME` dir** containing `config.yaml`, `.env`, `SOUL.md`, `sessions/`, `memory/`, `skills/`, `cron/`, and `state.db`. Per-profile persona via SOUL.md.
- **Cron** schedules recurring agent invocations. Upstream cron *inherits profile context* and runs the full conversation loop when in agent mode.
- **`no_agent` cron mode is upstream-native** (`~/.hermes/hermes-agent/tools/cronjob_tools.py:279, 319–372, 506–519`). Parameter `no_agent: bool`; when `True` the cron job runs the `script` and skips the LLM entirely. Relic's `render_no_agent_script` (`cron_wiring.py:865–963`) is the *content* of that script, not a replacement for an absent mode.
- **`wakeAgent: false` script gate is upstream-native** (Hermes v0.11.0, `RELEASE_v0.11.0.md:261`; impl `~/.hermes/hermes-agent/cron/scheduler.py:828, 846, 1049, 1101, 1112, 1155, 1165`). The pre-run `script` can emit JSON `{"wakeAgent": false}` to short-circuit before the agent loop runs. From `scheduler.py:828`: *"JSON like `{\"wakeAgent\": false}`, the agent is skipped entirely — no agent run is started."* This **is** an autonomous policy hook — Relic should use it instead of relying on the LLM to emit `[SILENT]` after a wasted call.
- **Memory providers** (`hindsight`, `honcho`) are configurable; runtime read/write API is not documented in the fetched llms-full.txt. Gumi today reads `state.db` and MEMORY.md directly rather than going through a Hermes memory API.
- **Skills** live in `~/.hermes/skills/` and autoload via `-s` flag or slash commands. Cron-from-skill: a Hermes skill can be the composer step in a two-stage cron (script gate + agent-backed composer skill).

### 3.2 Ownership split (proposed)

| Concern | Owner | Rationale |
|---|---|---|
| Persona, tone, voice, invariants | Hermes (`SOUL.md`) | Per-profile; survives Relic refactors |
| Conversation history | Hermes (`state.db`) | Hermes is the gateway; subject messages arrive there first |
| Skill registry, tool exposure | Hermes (`skills/`, `config.yaml`) | Platform concern |
| Cron scheduling + delivery channel | Hermes (`cron/jobs.json`) | Hermes-managed cron |
| **Should-I-speak gate** | Relic (`_evaluate_decision`) → emits Hermes `{"wakeAgent": false}` when silent | Consent, boundaries, pause state — Relic owns subject model; Hermes-canonical short-circuit |
| **Event-type + posture selection** (NEW) | Relic (`relic/checkin/policy.py`) | Two orthogonal dimensions; replayable |
| **Feature assembly** (NEW) | Relic (`relic/checkin/features.py`) | Mixes Hermes state.db reads with relic.db reads |
| Context construction | Relic (`relic/checkin/context_builder.py`) | Already there; parameterize by posture |
| Surface dispatch | Relic (`checkin_media_dispatcher.py`) | Already there; unchanged |
| **Proactive event surface** (NEW) | Relic (`relic/shared_continuity/service.py`) | Triggered by world events, not by clock |

### 3.3 What SOUL.md should declare (invariants, not behavior)

Today `SOUL.md` is generated by `relic/profile/registry.py:2182–2230` `_generate_agent_identity()` and is mostly descriptive. The redesign asks it to declare a small list of invariants that the LLM cannot override regardless of posture:

- "Silence is acceptable. If I have nothing to add, I say nothing."
- "I am not a clinician, therapist, or crisis line."
- "I do not narrate the user's life back to them."
- "I do not invent shared memories. I reference only what is in our history."
- "I match the user's disclosure depth. I do not lead it."

Posture vocabulary itself does **not** live in SOUL.md — it lives in `policy.py`. SOUL.md is the *unchanging* layer; postures are the *tunable* layer.

---

## 4. Failure Analysis

### 4.1 Prompt-level

- `registry.py:1388–1430` `gumi_checkin_message` is one big Italian prompt that tries to be everything at once: explain `DELIVER`, explain `[SILENT]`, list four media modalities (text/voice/image/music), inject base rules, switch on `ask: true`. The model has too many conditional branches to track per turn; quality drifts toward the most prominent instruction.
- "Ispirate alla tua giornata" was removed in the most recent commit, but the prompt still leans Gumi-centric because the *only* context section that contains the subject is `build_recent_subject_messages_section`, a quoted list. There is no extracted "topic the user cares about right now."
- `topic_hint` is sourced from facet scoring (a research instrument), so even when the model follows the rules, the *topic* it picks is whatever maximizes TGS — which is correlated with intrusion penalty but not with conversational momentum.

### 4.2 Architecture-level

- `decision_types = ["checkin", "followup", "proactivity"]` is a triplet without a behavior split. Three cron jobs run, each invokes the same evaluator, each emits the same payload shape. The naming suggests intent that the code does not realize.
- `ask` is binary and probabilistic. The 35 % daily roll is deterministic-per-day but uniform — it does not respond to whether the subject is mid-conversation, just woke up, or has not replied in three days.
- No failed-checkin recovery. `checkin_exchanges.reply_captured_at = NULL` after 24 h could trivially feed back into a `non_response_streak`. It does not.
- No distinction between "scheduled outreach because the cron fired" (low-information event) and "outreach because something in the subject's world changed" (high-information event). Proactive outreach should be event-triggered; today it is clock-triggered with a different filename.

### 4.3 Timing

- Fixed 30-min cron with jitter. Interruption cost (Mark, Iqbal, Horvitz — see §5) is not modeled at all. Quiet hours are a blunt on/off.
- No exponential back-off after silence. Subject ignores Gumi for two days → cron keeps firing → workbench shows growing `pending_proactive_count`.
- No coupling to time-since-last-subject-message. A subject who messaged 30 s ago should not get a cron check-in 90 s later.

### 4.4 Memory / context

- `build_recent_subject_messages_section` returns the last 5 messages by recency only, no relevance scoring. The Generative Agents pattern (recency × importance × relevance, §5/§6) is exactly what is missing here.
- Salience decay (`relic/memory_dynamics/decay.py`) is unused in the checkin path.
- No relational distance proxy (e.g., disclosure depth trend over the last 14 days).
- Observations are capped at 3, last 30 d — same flatness as messages.

### 4.5 Hermes integration

- The shell-wrapper `--no-agent` mode means cron skips the agent loop entirely. This is the correct decision for safety and determinism, but it means Hermes-side memory providers (`hindsight`, `honcho`) are not consulted. Relic re-reads state from disk each tick.
- No state carries between cron ticks beyond what is in `relic.db` and `checkin_exchanges`. The previous tick's posture is unknown to the next. (Trivial to add: `checkin_exchanges.posture`.)
- `SOUL.md` is regenerated whenever the subject is updated. Hard-pinned invariants risk being LLM-rewritten away.

### 4.6 Evaluation

- `checkin_decision_log.jsonl` is outcome-only (`status`, `decision`, timestamps). No way to ask "for this feature vector, what would the new policy have decided?" — i.e., no replay.
- No naturalness metric. No repetition metric. No coverage metric. Workbench shows counts only.
- Test coverage is contract-shaped (`tests/profile/test_checkin_prompt_contract.py` asserts that specific Italian phrases appear in the prompt). This is brittle and orthogonal to naturalness.

---

## 5. Literature Review

Citations are precise where the source is paywall-open; behind-paywall items are flagged. Each entry ends with **→ application to Gumi**.

### 5.1 Generative Agents (Park et al., 2023)

https://arxiv.org/abs/2304.03442

Memory retrieval combines three components with persona-tunable weights, confirmed in source code (https://github.com/joonspk-research/generative_agents/blob/main/reverie/backend_server/persona/cognitive_modules/retrieve.py):

```python
gw = [0.5, 3, 2]
master_out[key] = (persona.scratch.recency_w  * recency_out[key]   * gw[0]
                 + persona.scratch.relevance_w * relevance_out[key] * gw[1]
                 + persona.scratch.importance_w * importance_out[key] * gw[2])
```

Reflection is triggered when an importance counter crosses a threshold (`reflect.py`: *"if persona.scratch.importance_trigger_curr <= 0 and seq_event+seq_thought != []"*). Reflections re-enter memory as nodes with their own poignancy.

**→ application to Gumi:** the same weighted sum is the natural choice for `topic_freshness` and `salience` features. The importance-trigger pattern is a clean way to schedule *reflective* postures (which should be rare, not periodic).

### 5.2 MemGPT / Letta (Packer et al., 2023)

https://arxiv.org/abs/2310.08560 · https://github.com/letta-ai/letta/blob/main/letta/agent.py

Two key patterns:

- **Tiered memory with explicit read/write tool calls.** The agent decides when to invoke `core_memory_replace`, `archival_memory_insert`, `archival_memory_search` — memory writes are conscious actions, not implicit.
- **Heartbeat-driven self-invocation.** *"if heartbeat_request: continue # always chain"* — the agent can ask for another turn. This is the upstream analog of cron, but driven by the agent's own assessment of unfinished business.

**→ application to Gumi:** the heartbeat pattern is exactly the right metaphor for *proactive* outreach. Instead of three cron lanes, run one cron lane plus a *heartbeat queue* fed by events in `shared_continuity/service.py`. The cron lane handles scheduled check-ins (low information). The heartbeat queue handles proactivity (high information). Distinct decision policies for each.

### 5.3 Bickmore — Relational Agents

https://relationalagents.com/publications/

The relational-vs-task distinction: relational agents improve outcomes *because of* the relationship. Bickmore validates accommodation theory (users reciprocate agent communication style), self-disclosure reciprocity (agents disclosing appropriately raise user disclosure depth), and warns against "therapeutic creep" (positioning as a clinical substitute creates dependency risk).

**→ application to Gumi:** posture must mirror disclosure depth, not lead it. `brief_share` should fire when the subject has just disclosed something; never standalone. The `reflect` posture must be rate-limited and forbidden when `risk_flags` are present.

### 5.4 Conversation analysis canon

Sacks, Schegloff, Jefferson "A Simplest Systematics for the Organization of Turn-Taking" (Language, 1974, https://doi.org/10.2307/412243). Adjacency pairs (question→answer, greeting→greeting) impose preference structures: a question without an answer creates a noticeable absence; an absence is not neutral.

**→ application to Gumi:** if the previous tick asked a question and the subject did not reply, the next tick should *not* ask another question — that compounds the noticeable absence. Posture transition matrix should forbid `ask → ask` over a non-response.

### 5.5 Mark et al. — attention rhythms

"Bored Mondays and focused afternoons: the rhythm of attention and online activity in the workplace" (CHI 2014, https://dl.acm.org/doi/10.1145/2556288.2557204). Found bimodal attention rhythms across the workday; interruptibility correlates with task boundaries, not clock time.

Iqbal & Bailey on PC interruption cost (CHI 2008) measure that interruption at task boundaries costs 3–5× less than mid-task interruption.

**→ application to Gumi:** without sensor data Gumi cannot measure task boundaries, but it has a usable proxy: *time since last subject message*. Very recent message (≤2 min) → subject is actively present (good for posture `observe`, bad for posture `ask`); long silence (≥4 h) → subject availability unknown (bias toward `silent`).

### 5.6 Altman & Taylor — Social Penetration Theory

Foundational work on disclosure depth as the spine of relationship development. Depth proceeds in stages; jumping stages feels invasive.

**→ application to Gumi:** disclosure depth of the *agent* must not exceed disclosure depth of the *subject*. A simple metric: track average tokens-per-subject-message over 14 days; cap `brief_share` length at that.

### 5.7 Companion-app empirical work

Skjuve et al. on Replika user attachment (https://doi.org/10.1016/j.ijhcs.2022.102903) found that perceived intimacy is *not* driven by message frequency; it is driven by perceived listening. Higher message frequency was associated with disengagement when not paired with continuity (reference to previous content).

**→ application to Gumi:** more cron ticks ≠ more connection. The right axis is *grounded reference*: every message that references something specific the subject said is worth more than ten generic check-ins.

---

## 6. GitHub / Open-Source Review

Each entry: repo · specific file · pattern · borrow/reject for Gumi.

### 6.1 `joonspk-research/generative_agents`

- `reverie/backend_server/persona/cognitive_modules/retrieve.py` — weighted-sum scoring (see §5.1). **Borrow** as the basis for `features.py` salience/freshness scoring.
- `.../reflect.py` — importance-triggered reflection. **Borrow** as the trigger for the `reflect` posture (importance accumulator on `observations.signal_strength`).
- `.../plan.py` — daily plan generation. **Reject** for Gumi — Gumi does not need a daily plan; cron schedule is its plan.

### 6.2 `letta-ai/letta` (formerly MemGPT)

- `letta/agent.py` — heartbeat-driven self-invocation. **Borrow** the *queue* pattern (not the in-loop continuation) for proactive triggers.
- `letta/functions/function_sets/base.py` — explicit memory tool calls. **Reject** for Gumi cron path (we use `--no-agent` for determinism); could be useful if a separate "memory curation" cron is added later.

### 6.3 `SillyTavern/SillyTavern` (idle extension)

- The "idle" extension implements timeout-based proactive messaging with a per-character cooldown. **Reject the timeout-only model** — exactly the failure mode Gumi already has. **Borrow** the per-character cooldown structure (Gumi has 12 h ask cooldown already; this generalizes to posture cooldowns).

### 6.4 `microsoft/autogen` and `crewai`

Multi-agent orchestration. Scheduling is task-driven, not relational. **Reject** for Gumi's relational use case — patterns do not transfer.

### 6.5 `cogentapps/chat-with-gpt` and similar persona scaffolds

Persona definitions, conversation memory, no proactive logic. **No useful patterns** for this spike.

### 6.6 Journaling / mood check-in apps

`nomie-app/nomie6-oss` and similar use *user-initiated* check-ins. The pattern that translates: *no-question prompts*. Many of these apps prompt with "anything to track?" rather than "how do you feel about X?". **Borrow** the no-question default — Gumi's `observe` posture should make the no-question case the most common.

### 6.7 Hermes itself

`hermes/cron/` and `hermes/skills/` (per https://hermes-agent.nousresearch.com/docs/llms-full.txt) provide scheduling and capability registration but no policy layer. **Confirms** the design choice to keep policy in Relic.

---

## 7. Design Principles

Each: principle · justification · anti-pattern.

1. **Silence is a first-class output.**
   Justification: §5.7, §4.3 — message volume is not a proxy for connection.
   Anti-pattern: treating `[SILENT]` as failure or hiding it from telemetry. Today's UI counts non-silent decisions only.

2. **Posture is the decision; the message is its rendering.**
   Justification: §4.1 — letting the LLM choose posture from prose is unstable. A small enum is inspectable, testable, and replayable.
   Anti-pattern: prompts that contain conditional logic the model has to execute.

3. **Recency × salience × novelty over fixed rotation.**
   Justification: §5.1, §6.1.
   Anti-pattern: round-robin over four "modes".

4. **Reciprocity over interrogation.**
   Justification: §5.3, §5.6.
   Anti-pattern: probing a facet because TGS scored it high while the subject is talking about something else.

5. **Failed reach reduces future reach.**
   Justification: §5.5 — silence may mean unavailability; persisting at the same cadence amplifies the offense.
   Anti-pattern: `pending_proactive_count` growing unboundedly.

6. **Proactive ≠ scheduled.**
   Justification: §5.2 — proactivity should be triggered by world events, not clocks.
   Anti-pattern: today's three cron lanes, one of which is named "proactivity".

7. **Every decision is replayable.**
   Justification: §4.6.
   Anti-pattern: outcome-only logs.

8. **Consent / boundary pre-empts policy.**
   Justification: existing `_evaluate_decision` design, not changed.
   Anti-pattern: any code path where posture selection sidesteps a gate result.

---

## 8. Proposed Architecture

### 8.1 Components

```
┌────────────────────────────────────────────────────────────────────────┐
│                          hermes cron tick                              │
└────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│  _evaluate_decision()         [UNCHANGED — safety/consent gate]        │
│  returns RuntimeDecision: NO_REPLY | CANDIDATE | DELIVER | BLOCKED     │
└────────────────────────────────────────────────────────────────────────┘
                                  │
                  DELIVER         │       (others → wakeAgent:false / [SILENT] safety net)
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│  relic/checkin/features.py    [NEW]                                    │
│    CheckinFeatures = {                                                 │
│      time_since_last_subject_msg_sec: int                              │
│      subject_msg_count_24h: int                                        │
│      subject_avg_tokens_14d: float                                     │
│      non_response_streak: int                                          │
│      time_since_last_checkin_min: int                                  │
│      last_posture: Posture | None                                      │
│      posture_history_last_5: list[Posture]                             │
│      due_followup: bool                                                │
│      topic_freshness: float          [0..1, 1 = unseen]                │
│      salience_top: float             [from memory_dynamics.decay]      │
│      importance_accumulator: float   [Park et al. reflection trigger]  │
│      risk_flag_active: bool                                            │
│      quiet_hours_proximity_min: int  [neg = inside, pos = outside]     │
│      reach_score: float              [base * decay(non_response_streak)]│
│    }                                                                   │
└────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│  relic/checkin/policy.py      [NEW]                                    │
│    def select_decision(f: CheckinFeatures, *, decision_type: str,      │
│                        proactive_trigger: bool=False) -> Decision      │
│    Decision = (EventType, Posture); ConstraintHeader is rendered next  │
│                                                                        │
│    EventType (WHAT kind of social event):                              │
│       silent | checkin | followup | proactive | reminder | reflection  │
│    Posture (HOW to occupy the conversational stance):                  │
│       quiet | observe | brief_share | ask | follow_up_warm |           │
│       follow_up_terse | reflective_mirror | small_share | repair       │
│                                                                        │
│    Two orthogonal axes: e.g. (followup, follow_up_warm),               │
│    (proactive, brief_share), (checkin, observe), (silent, quiet),      │
│    (reminder, small_share).                                            │
└────────────────────────────────────────────────────────────────────────┘
                                  │
        EventType=silent → emit  {"wakeAgent": false}  (Hermes canonical)
        else             → emit  {"wakeAgent": true, "context": packet}
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│  build_deliver_context(event_type, posture, …)   [PARAMETERIZED]       │
│    section selection table per (event_type, posture) pair              │
└────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│  LLM (Hermes agent-backed leg) with prompt = composer skill            │
│  + CONSTRAINT HEADER (≤3 lines: event_type, posture, grounding)        │
└────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│  checkin_media_dispatcher                            [UNCHANGED]       │
└────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Canonical decision event store (see §11.2 reconciliation)             │
│    fields: event_type, posture, features_id, gate_result,              │
│            message_hash, was_delivered, wake_agent_emitted, ...        │
│    UI repointed from checkin_decision_log.jsonl to this store          │
└────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Proactive trigger surface (parallel path)

```
relic/shared_continuity/service.py
  └── event detector: new world signal in MEMORY.md / state.db
       └── emits ProactiveCandidate { subject_id, signal_ref,
                                       suggested_posture, expiry, priority }
            └── queue: RELIC_HOME/subjects/<id>/proactive_queue.jsonl
                 └── consumed by a low-frequency cron job
                      (default every 2 h) that:
                         - reads queue head
                         - runs _evaluate_decision()
                         - runs select_decision(..., decision_type="proactivity")
                         - decides DELIVER or DEFER (re-queue with expiry)
```

This replaces the `relic_proactivity_decision.sh` cron lane. Scheduled-checkin and proactive-trigger become orthogonal sources, not parallel cron names with identical logic.

### 8.3 Inputs / outputs at boundaries

| Boundary | Today | Proposed |
|---|---|---|
| Cron tick → Python | `make_decision(subject_id, gumi_instance_id, hermes_profile_id, force)` — **no `decision_type`** | `make_decision(..., decision_type: str)` — type plumbed end-to-end |
| Script → Hermes scheduler | stdout text + LLM "[SILENT]" sentinel | JSON `{"wakeAgent": false}` for silent; `{"wakeAgent": true, "context": packet}` otherwise (Hermes-canonical, no wasted agent run) |
| Gate → composer skill packet | `DELIVER\ntipo: text\nora: 15:42\n[ask: true\nask_topic: …]` | `{event_type, posture, features_id, grounding_refs, allowed_context, constraint_header}` |
| Composer prompt → LLM | full prompt + context blob | Hermes skill prompt + packet + constraint header + posture-filtered context |
| LLM → dispatcher | `tipo: …\ntesto: …` or `[SILENT]` | same (`[SILENT]` retained as composer-side safety net) |
| Decision log entry | `{status, decision, timestamp}` | canonical event store (§11.2) with `event_type`, `posture`, `features_id`, `non_response_streak`, `reach_score`, `wake_agent_emitted` |

---

## 9. Check-in and Proactivity Policy Model

### 9.1 EventType × Posture (two orthogonal dimensions)

**EventType** answers *what kind of social action this is*; it maps 1:1 to the existing `decision_types` triplet plus a few additions, so the cron-script split keeps observability value.

| EventType | Meaning | Trigger source |
|---|---|---|
| `silent` | Deliberate non-action | policy decided to skip |
| `checkin` | Scheduled relationship maintenance | cron tick |
| `followup` | Continuation of an open thread | `checkin_exchanges.followup_sent_at IS NULL` AND prior reply present |
| `proactive` | Event-grounded initiative | `ProactiveCandidate` from `shared_continuity` |
| `reminder` | Practical, low-affect nudge | external reminder source (user-configured) |
| `reflection` | Importance-accumulator-driven retrospective | Park et al. trigger; rate-limited |

**Posture** answers *how to occupy the conversational stance*; independent of EventType. The same EventType can produce different postures depending on features.

| Posture | Demand on subject | Asks question | Max output |
|---|---|---|---|
| `quiet` | none (no message) | no | 0 |
| `observe` | minimal: 1-line presence | no | 1 sentence |
| `brief_share` | low: agent shares 1 line to reciprocate disclosure | no | 1 sentence |
| `ask` | medium: open question on fresh topic | yes (one only) | 2 sentences |
| `follow_up_warm` | medium: explicit continuation, low pressure | optional | up to 3 sentences |
| `follow_up_terse` | low: brief acknowledgement of a stale or non-responsive thread | no | 1 sentence |
| `reflective_mirror` | low: paraphrase user-stated content without inference | no | 2 sentences |
| `small_share` | low: ambient self-share without demand for response | no | 1 sentence |
| `repair` | medium: acknowledge possible overreach or missed reply | optional | 2 sentences |

**Valid (EventType, Posture) pairs** (not all combinations make sense):

| EventType ↓ \ Posture → | quiet | observe | brief_share | ask | follow_up_warm | follow_up_terse | reflective_mirror | small_share | repair |
|---|---|---|---|---|---|---|---|---|---|
| silent | ✓ | – | – | – | – | – | – | – | – |
| checkin | – | ✓ | ✓ | ✓ | – | – | – | ✓ | – |
| followup | – | – | – | – | ✓ | ✓ | ✓ | – | ✓ |
| proactive | – | – | ✓ | – | – | – | – | – | – |
| reminder | – | – | – | – | – | – | – | ✓ | – |
| reflection | – | – | – | – | – | – | ✓ | – | – |

### 9.2 `select_decision` decision tree (deterministic, replayable)

Returns the (EventType, Posture) pair. `decision_type` is the cron-script-declared intent (`"checkin" | "followup" | "proactivity"`), now actually plumbed through. The policy is free to *downgrade* an event (e.g. `proactivity` → `silent`) but never upgrade across kinds.

Pseudocode:

```python
def select_decision(
    f: CheckinFeatures,
    *,
    decision_type: str,                       # plumbed from cron script
) -> tuple[EventType, Posture]:

    # Safety pre-empts everything
    if f.risk_flag_active:
        return EventType.silent, Posture.quiet  # escalation_notifier handles

    # Cadence damping (Hermes-canonical short-circuit at script gate)
    if f.reach_score < REACH_THRESHOLD:
        return EventType.silent, Posture.quiet

    if f.time_since_last_subject_msg_sec < 120:   # mid-conversation
        return EventType.silent, Posture.quiet

    # Followup lane (driven by checkin_exchanges or due_followup)
    if decision_type == "followup" or f.due_followup:
        if f.non_response_streak == 0:
            return EventType.followup, Posture.follow_up_warm
        return EventType.followup, Posture.follow_up_terse

    # Proactive lane (event-grounded; only fire when salient)
    if decision_type == "proactivity":
        if f.non_response_streak >= 3:
            return EventType.silent, Posture.quiet
        if f.salience_top > PROACTIVE_SALIENCE_THRESHOLD:
            return EventType.proactive, Posture.brief_share
        return EventType.silent, Posture.quiet

    # decision_type == "checkin" (scheduled relationship maintenance)
    if f.non_response_streak >= 3:                # noticeable absence: don't push
        return EventType.silent, Posture.quiet

    if (f.importance_accumulator > REFLECT_THRESHOLD
        and last_reflect_age_days(f) >= 7):
        return EventType.reflection, Posture.reflective_mirror

    if (f.topic_freshness > 0.6
        and select_facet_status() == 'ask_now'
        and not asked_recently(f, hours=12)
        and f.last_posture != Posture.ask):       # no two asks in a row
        return EventType.checkin, Posture.ask

    if f.subject_msg_count_24h > 0 and f.salience_top > BRIEF_SHARE_THRESHOLD:
        # forbidden-transition gate (§9.5)
        if f.subject_avg_tokens_14d >= 10:
            return EventType.checkin, Posture.brief_share

    return EventType.checkin, Posture.observe
```

Thresholds (initial guesses, tune in eval phase):

```
REACH_THRESHOLD              = 0.35
PROACTIVE_SALIENCE_THRESHOLD = 0.6
REFLECT_THRESHOLD            = 0.8
BRIEF_SHARE_THRESHOLD        = 0.4
```

### 9.3 Cadence damping

```
non_response_streak = consecutive delivered initiatives that received no reply within 24h
followup_non_response_streak = consecutive delivered followups that received no reply within 24h
reach_score         = min(
    1.0 * (0.7 ** non_response_streak),
    1.0 * (0.7 ** (followup_non_response_streak * 1.3)),
)   # follow-up silence weighs more than generic outreach silence
```

Streak 0 → 1.0; streak 1 → 0.7; streak 2 → 0.49; streak 3 → 0.343. With `REACH_THRESHOLD = 0.35`, the policy goes silent at 3 unanswered delivered initiatives and recovers when a subject message arrives.

This does **not** reset at midnight. A daily reset would erase the signal that the subject has repeatedly ignored outreach and would make Gumi re-approach at full strength every morning. Recovery rules are explicit:

```python
if subject_replied_after_delivery:
    non_response_streak = 0
    followup_non_response_streak = 0
elif explicit_boundary_or_lower_frequency_request:
    persist_boundary_preference()  # hard cap in select_decision, evaluated before reach_score
    # Do not erase streak history. The explicit preference now governs future outreach.
elif decision_event.outcome_status_transitions("delivered", "unanswered_24h"):
    non_response_streak += 1
    if decision_event.decision_type == "followup":
        followup_non_response_streak += 1
elif days_since_last_delivered_initiative >= 7 and days_since_last_subject_msg <= 14:
    non_response_streak = max(0, non_response_streak - 1)
    followup_non_response_streak = max(0, followup_non_response_streak - 1)
```

The canonical event store is the source of truth: the increment happens exactly when a decision event with `outcome_status="delivered"` is reconciled to `outcome_status="unanswered_24h"`, never when `DELIVER` is first emitted. Silent ticks, blocked gates, quiet-hours skips, and `wakeAgent:false` decisions do not increment the streak. Only actual delivered initiatives can become unanswered. The 7-day decay is a recovery valve only when the subject has shown recent conversational life outside this outreach loop; if both sides have been silent, the streak remains stable and Gumi keeps backing off.

### 9.4 Topic freshness

```
topic_freshness = 1 - max_jaccard(candidate_topic_tokens, last_K_topic_token_sets)
```

K = 5; tokens lower-cased, stop-worded; uses `AntiRepeatGate` (already in `relic/checkin/anti_repeat.py`) for the Jaccard computation.

### 9.5 Forbidden transitions

| From | To | When forbidden |
|---|---|---|
| `ask` | `ask` | over a single non-response |
| `reflect` | `reflect` | within 7 d |
| any | `brief_share` | when `subject_avg_tokens_14d < 10` (subject is laconic; agent must not flood) |

---

## 10. Prompting Strategy

### 10.1 One base prompt; (event_type, posture) form a constraint header

The existing `registry.gumi_checkin_message` stays (or migrates to a Hermes composer skill — see §15). Inject a short *constraint header* at the top, derived deterministically from `(EventType, Posture)`:

```
[EVENTO: <event_type>]
[POSTURA: <posture_name>]
[VINCOLI: max <N> frasi; <"con domanda" | "senza domanda">]
[GROUNDING: <riferimento concreto a stato osservato> | <"nessuno">]
```

Examples:

- `[EVENTO: checkin] [POSTURA: observe] [VINCOLI: max 1 frase; senza domanda] [GROUNDING: nessuno]`
- `[EVENTO: checkin] [POSTURA: ask] [VINCOLI: max 2 frasi; con domanda] [GROUNDING: il soggetto ha menzionato "esame venerdì" 14h fa]`
- `[EVENTO: proactive] [POSTURA: brief_share] [VINCOLI: max 1 frase; senza domanda] [GROUNDING: il soggetto ha condiviso "non ho dormito" 35min fa]`
- `[EVENTO: followup] [POSTURA: follow_up_terse] [VINCOLI: max 1 frase; senza domanda] [GROUNDING: la mia domanda "come va il progetto?" 36h fa, nessuna risposta]`

### 10.2 (EventType, Posture)-filtered context sections

| (EventType, Posture) | Sections in `build_deliver_context` |
|---|---|
| `(silent, quiet)` | none — short-circuits at Hermes script gate via `wakeAgent: false` |
| `(checkin, observe)` | recent_subject_messages only |
| `(checkin, brief_share)` | recent_subject_messages + world.md fragment matching salience_top |
| `(checkin, ask)` | recent_subject_messages + topic_hint + style_hints (current behavior) |
| `(checkin, small_share)` | world.md fragment only (no subject context — agent volunteers) |
| `(followup, follow_up_warm)` | recent_subject_messages + last_exchange (new section) |
| `(followup, follow_up_terse)` | last_exchange only |
| `(followup, repair)` | last_exchange + last_failed_delivery (new section) |
| `(followup, reflective_mirror)` | last_exchange paraphrased; no observations injected |
| `(proactive, brief_share)` | proactive_candidate.signal_ref + recent_subject_messages (≤2) |
| `(reminder, small_share)` | reminder_payload only |
| `(reflection, reflective_mirror)` | observations_section + style_hints |

### 10.3 Hard constraints encoded in prompt

- Each constraint header is a contract: the model is told that violating max sentence count produces an unusable message that will be discarded by `checkin_media_dispatcher`. (Soft enforcement initially; can be hard-enforced by a post-LLM filter.)
- "Anti-creepiness" invariants stay in `SOUL.md`, not in the checkin prompt, so they survive prompt refactors.
- `(silent, quiet)` is enforced at the Hermes script gate (`wakeAgent: false`) — the LLM is never invoked, eliminating the "LLM ignores `[SILENT]`" failure mode entirely.

### 10.4 What does *not* change in the prompt

- The `DELIVER` parsing contract.
- The `tipo:` / `testo:` / `caption:` / `image_prompt:` output schema.
- The media modality rules (text/voice/image/music dispatch).

---

## 11. Data Model and Logging Changes

### 11.1 SQLite (additive only — no destructive migrations)

```sql
ALTER TABLE checkin_exchanges ADD COLUMN posture TEXT;
ALTER TABLE checkin_exchanges ADD COLUMN response_latency_seconds INTEGER;
-- response_latency_seconds set at reply_capture time = (reply_captured_at - asked_at)

CREATE TABLE IF NOT EXISTS checkin_features (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id      TEXT NOT NULL,
    tick_id         TEXT NOT NULL,
    features_json   TEXT NOT NULL,
    posture         TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cf_subject_tick ON checkin_features(subject_id, tick_id);
-- one row persisted per evaluated policy tick; id is emitted as features_id in the canonical event

CREATE TABLE IF NOT EXISTS checkin_cadence_state (
    subject_id                   TEXT PRIMARY KEY,
    non_response_streak           INTEGER NOT NULL DEFAULT 0,
    followup_non_response_streak  INTEGER NOT NULL DEFAULT 0,
    last_delivered_initiative_at  TEXT,
    last_unanswered_delivery_at   TEXT,
    last_reply_at                 TEXT,
    last_subject_msg_at           TEXT,
    last_boundary_at              TEXT,
    last_decay_at                 TEXT,
    frequency_cap_per_day         INTEGER,
    updated_at                    TEXT NOT NULL
);
```

### 11.2 Canonical event store + log reconciliation

Today three stores exist (§2.5) and the UI reads one that no producer writes to. The redesign needs a single canonical event store, with the UI repointed and a compatibility mirror during the transition.

**Canonical store: Chronicle.** Already in use (`relic/chronicle/emit_event`, called from `cron_wiring.py:670, 683`). Add the new fields to the `cron_decision` event payload:

```json
{
  "event_type": "cron_decision",
  "subject_id": "daniele",
  "decision_type": "checkin",            // NEW — plumbed from cron script
  "event_kind": "checkin",               // NEW — EventType enum
  "posture": "follow_up_warm",           // NEW — Posture enum
  "features_id": 4711,                   // NEW — FK into checkin_features
  "non_response_streak": 0,              // NEW
  "followup_non_response_streak": 0,     // NEW
  "reach_score": 1.0,                    // NEW
  "response_deadline_at": "2026-05-19T15:42:00+02:00",
  "cadence_decay_applied": false,
  "outcome_status": "delivered|answered|unanswered_24h|silent|blocked",
  "wake_agent_emitted": true,            // NEW — Hermes-canonical gate result
  "constraint_header": "[EVENTO: followup] [POSTURA: follow_up_warm] [VINCOLI: max 3 frasi] [GROUNDING: esame venerdì 14h fa]",
  "message_hash": "sha256:…",            // NEW — for repetition detection
  "delivered": true,                     // NEW
  "timestamp": "2026-05-18T15:42:00+02:00"
}
```

**JSONL mirror for UI continuity.** Today the writer is hard-coded to `~/.relic/decision_events.jsonl` (`cron_wiring.py:660`). In Task 1 it is aligned to the runtime contract `RELIC_HOME/decision_events.jsonl` if `RELIC_HOME` is set, else `~/.relic/decision_events.jsonl`, and the UI is repointed to read that exact rule instead of `$HERMES_HOME/workspace/gumi/cron/checkin_decision_log.jsonl`. The orphan path can be removed once the UI ships.

**Migration order** (matches §14 step 1):

1. Add new fields to `cron_decision` Chronicle event + `decision_events.jsonl` writer.
2. Do not rewrite historical `decision_events.jsonl`; normalize missing nullable fields in readers/replay paths and backfill only downstream DB state if needed.
3. Repoint UI (`ui/lib/workbench-data.ts:128, 132`) from `checkin_decision_log.jsonl` → `RELIC_HOME/decision_events.jsonl` (same resolution rule as the writer).
4. Drop the orphan path reference from the UI.

### 11.3 Proactive queue

`RELIC_HOME/subjects/<id>/proactive_queue.jsonl` if `RELIC_HOME` is set, else `~/.relic/subjects/<id>/proactive_queue.jsonl`:

```json
{"id": "pc-…", "signal_ref": "memory.md#L42", "suggested_posture": "brief_share",
 "expires_at": "2026-05-19T00:00:00+02:00", "priority": 0.6, "enqueued_at": "…"}
```

### 11.4 Posture history and cadence state

For the `last_posture` / `posture_history_last_5` features: query `checkin_features` ordered by `created_at DESC LIMIT 5`.

For `non_response_streak` / `followup_non_response_streak` / `reach_score`: read `checkin_cadence_state` before policy evaluation, update it only from delivery outcome reconciliation plus explicit reply capture. The global streak captures overall ignored initiative. The follow-up streak is separate because ignoring an explicit continuation is a stronger signal than ignoring generic proactive outreach.

Reply matching for reconciliation is not limited to `checkin_exchanges`: for any delivered initiative, a reply is any subject-authored message recorded in Hermes `state.db` whose timestamp falls within `[delivered_at, response_deadline_at]`. This prevents non-ask deliveries from being misclassified as `unanswered_24h`.

Explicit frequency or boundary requests do not erase cadence history. They populate `last_boundary_at` and `frequency_cap_per_day`, and `select_decision()` applies those fields as hard caps before computing reach. This keeps user preference separate from inferred non-response signals.

---

## 12. Evaluation Plan

### 12.1 Qualitative (gating)

Blind rater rubric over 50 ticks (25 baseline, 25 new policy):

| Criterion | Scale | Pass band |
|---|---|---|
| Naturalness | 1 (scripted) – 5 (natural) | mean ≥ 3.5 |
| Relevance | 1 (generic) – 5 (specific) | mean ≥ 3.5 |
| Boundary respect | pass/fail | 100 % pass |
| Repetitiveness | 1 (very) – 5 (none) | mean ≥ 3.5 |

### 12.2 Automated (replayable)

- **Jaccard repetition** over rolling 7-day window of issued messages: `< 0.4`.
- **Posture entropy** over 14 days: `H(posture distribution) ≥ 1.5 bits` (no monoculture).
- **Silent rate**: within configured band (initial `[0.3, 0.6]` — tune from subject baseline).
- **Damping verification**: synthetic delivered-initiative stream with non_response_streak=3 → posture=silent in ≥ 80 % of cases.
- **No daily reset**: streak remains unchanged across a midnight boundary unless a subject reply or the gated 7-day no-delivery decay rule applies. Boundary updates set caps; they do not reset streaks.
- **No phantom penalty**: silent ticks, blocked gates, and quiet-hours skips do not increment `non_response_streak`.
- **Outcome transition only**: `non_response_streak` increments only when a canonical decision event transitions from `delivered` to `unanswered_24h`.
- **Decay gating**: replay two 7-day cases: subject active outside check-ins → streak decays by 1; subject silent and no delivery because of damping → streak remains unchanged.
- **Boundary respect without erasure**: explicit lower-frequency request sets a frequency cap but does not reset streak history.
- **Replay determinism**: same features → same posture (byte-equal).

### 12.3 Scenario tests (one per §15 scenario)

Pinned in `tests/checkin/test_policy_scenarios.py`. Each test constructs a `CheckinFeatures` instance, calls `select_decision`, asserts the expected `(EventType, Posture)` pair, asserts the constraint header rendered correctly.

### 12.4 Long-running observation

After deployment, the workbench should expose:

- Posture distribution over time (per subject).
- Non-response streak over time.
- Reach-score trajectory.

These are read-only views into `checkin_features` + decision log v2.

---

## 13. Risks and Guardrails

| Risk | Guardrail |
|---|---|
| Privacy: posture features may inadvertently leak observations into a logged context | Store feature vector hashed for facet IDs; never include raw `observation.content` in `features_json` |
| Creepiness from too-recent reference | Hard cap: `recent_subject_messages` lookback ≤ 72 h unless `follow_up` posture explicitly extends |
| Emotional overreach | `reflect` posture: 7 d cooldown; disabled when any `risk_flag_active` |
| Hallucinated intimacy | `brief_share` constraint header must include `[GROUNDING: …]` with a verifiable reference; no grounding → posture demoted to `observe` |
| Excessive proactivity | Proactive queue cap: `boundary_policy.maximum_daily_initiatives`; enqueue-side check |
| User loss of control | New `pause:posture:<name>` syntax in subject pause file; mirrors existing global pause |
| Therapeutic creep | SOUL.md hard invariant ("not a clinician"); `reflect` posture forbidden to use advisory imperative verbs (post-filter regex) |
| `[SILENT]` over-emission seen by user as Gumi "going dark" | Workbench surfaces silent rate per subject; alert if > 80 % over 7 d |
| Regression in safety gate | `_evaluate_decision` is unchanged in this redesign; contract tests in `tests/gumi_plugin/test_cron_pause_controller_gate.py` etc. must continue to pass |

---

## 14. Implementation Plan (small testable steps)

Detailed task-by-task TDD execution plan: `docs/plans/2026-05-18-cron-checkin-naturalness-implementation.md`.

Each step is shippable and testable in isolation. Steps 1–2 are observability prerequisites; steps 3–5 are mechanical wiring; steps 6+ change behavior.

1. **Reconcile observability + plumb `decision_type` end-to-end.** Pre-policy prerequisite — otherwise nothing the new policy emits is replayable or visible to the UI.
   - Add `decision_type: str` parameter to `make_decision()` (`cron_wiring.py:694`). Each per-subject cron script (`relic_{checkin|followup|proactivity}_decision.sh`) passes its own type.
   - Add `event_kind`, `posture`, `features_id`, `non_response_streak`, `reach_score`, `response_deadline_at`, `cadence_decay_applied`, `outcome_status`, `wake_agent_emitted`, `message_hash`, `delivered` fields to `decision_events.jsonl` + Chronicle `cron_decision` payload (initially all `null` — no behavior change).
   - Repoint `ui/lib/workbench-data.ts:128, 132` from `$HERMES_HOME/workspace/gumi/cron/checkin_decision_log.jsonl` to a strict `RELIC_HOME/decision_events.jsonl` resolver used only for this log path, and add a contract test that the writer and UI resolve the same path without breaking the existing `.relic-live` dev fallback elsewhere in the UI.
   - **Files:** `relic/gumi_plugin/cron_wiring.py`; `ui/lib/workbench-data.ts`; new contract test `tests/gumi_plugin/test_decision_log_canonical.py`.

2. **Adopt Hermes `wakeAgent: false` script gate for the agent-backed composer leg.** Replace the LLM `[SILENT]` round-trip where Hermes is about to wake an agent; keep pure no-agent decision probes as no-agent jobs.
   - Render the Relic gate script (`cron_wiring.py:865–963`, or its successor when split into gate/composer jobs) so the agent-backed cron leg receives `{"wakeAgent": false}` JSON when `_evaluate_decision()` or `select_decision()` returns a silent/non-deliverable result.
   - `[SILENT]` LLM contract stays as a composer-side safety net (still saves dispatch).
   - **Files:** `cron_wiring.py:render_no_agent_script`; new test `tests/gumi_plugin/test_wake_agent_gate.py`.

3. **Add `EventType` + `Posture` enums + `select_decision` stub returning `(silent, quiet)`.** Wire the gate → policy call → JSON gate emission. Verify all existing `[SILENT]` tests still pass. **Files:** new `relic/checkin/policy.py`; modify `cron_wiring.py` payload emission only.

4. **Add `features.py` reading existing tables and logging to `decision_events.jsonl` via the canonical writer.** No new schema yet; no behavior change. **Files:** new `relic/checkin/features.py`; new `tests/checkin/test_features_shape.py`.

5. **Add `checkin_features` table + migration.** Persist one feature row per evaluated tick and use its id as `features_id` in the canonical event. Also add `checkin_exchanges.posture` and `checkin_exchanges.response_latency_seconds` so follow-up shaping and latency analysis are first-class. **Files:** migration in `relic/db/migrations/`; `db_init.py` update; `reply_capture.py` write-side update.

6. **Implement minimal policy: `(silent, quiet)` / `(checkin, observe)` / `(checkin, ask)`.** Route existing ask path through `(checkin, ask)` (preserves behavior). **Files:** `policy.py`; `context_builder.py` posture parameter (default preserves current behavior).

7. **Parameterize `build_deliver_context()` by `(event_type, posture)` pair.** Section selection table from §10.2. **Files:** `context_builder.py`; update `tests/checkin/test_context_builder.py`.

8. **Inject the constraint header into the actual composer prompt.** The posture becomes behaviorally real only when `[EVENTO: ...] [POSTURA: ...] [VINCOLI: ...] [GROUNDING: ...]` is prepended at the composer insertion point. **Files:** `relic/profile/registry.py` or successor composer entry point; `policy.py`; prompt contract tests.

9. **Add cadence damping** (`non_response_streak` feature + `reach_score`) plus the runtime reconciler that materializes `delivered -> unanswered_24h`. **Files:** `features.py`; new `outcome_reconciler.py`; `policy.py`; new tests `tests/checkin/test_cadence_damping.py`, `tests/checkin/test_outcome_reconciler.py`.
   - Count only delivered initiatives that remain unanswered after 24h.
   - Increment only on canonical event transition `delivered → unanswered_24h`.
   - Do not reset daily; reset on subject reply only, including replies detected through Hermes `state.db` even when no `checkin_exchanges` row exists.
   - Treat explicit boundary/frequency preference as a hard policy cap, not as a streak reset.
   - Apply partial recovery after 7 days without delivered initiatives only if the subject has messaged within the last 14 days.

10. **Add `brief_share` posture sourcing from `workspace/gumi/world.md`.** New section function in `context_builder.py`. Hard-cap length per §13. **Files:** `context_builder.py`; `policy.py`.

11. **Add `followup` event type with `follow_up_warm` / `follow_up_terse` postures** sourcing from last `checkin_exchanges` reply. **Files:** `context_builder.py`; `policy.py`; `tests/checkin/test_followup_posture.py`.

12. **Separate proactive trigger surface in `shared_continuity/service.py`.** Add the queue producer in continuity and make the low-frequency queue consumer the sole proactivity lane when enabled, so the legacy `relic_proactivity_decision.sh` path cannot double-fire. **Files:** `shared_continuity/service.py`; new `relic/gumi_plugin/proactive_consumer.py`; `cron_wiring.py`.

13. **Replay harness.** `tools/replay_decisions.py` to re-run `select_decision` over historical features. **Files:** new `tools/replay_decisions.py`.

14. **Add automated metrics in CI:** posture entropy, Jaccard repetition, damping verification, wakeAgent emission rate matches posture distribution. **Files:** `tests/checkin/test_metrics.py`; CI job.

Each step ≤ 1 day of work. Steps 1–5 are reversible by reverting the posture parameter to a constant default.

---

## 15. Open Questions (require human review)

1. **`wakeAgent: false` adoption timing.** Hermes v0.11.0 supports it (`scheduler.py:828`). Adopt it in step 2 of the implementation plan, or keep the LLM `[SILENT]` round-trip as a transitional safety net?
2. **Hermes composer skill vs in-tree prompt.** Should `registry.gumi_checkin_message` migrate to a Hermes skill (`hermes/skills/relic-checkin-compose`) so the composer is profile-managed, or stay in Relic?
3. **`workspace/gumi/world.md` ownership.** Today it lives in the Hermes profile dir. The proposed `brief_share` posture reads it. Stay Hermes-owned (Relic reads) or move to `~/.relic/subjects/<id>/`?
4. **Posture vocabulary size.** Nine postures may be too many. Candidate collapses: `follow_up_warm`/`follow_up_terse` merged with a `warmth: float` parameter; `small_share` folded into `brief_share` with `solicited: bool`.
5. **Proactive trigger source.** Hermes documents no agent event bus. Options:
   (a) Relic cron polling MEMORY.md and state.db diffs,
   (b) write-side hooks in `shared_continuity/service.py`,
   (c) a Hermes skill that emits events via stdout.
6. **`select_facet` retirement timeline.** Long term, facet-driven question scoring (a clinical research instrument) is a poor fit for naturalistic conversation. Should `ask` posture stop using `select_facet` once `topic_freshness` is reliable?
7. **Cadence damping curve.** Exponential `0.7^streak` is a guess. Linear? Step function? Subject-tunable from `boundary_policy.json`?
8. **UI exposure of posture/event_type.** Privacy concern: showing the subject what internal label was selected may be intrusive. Show in researcher workbench only?
9. **Cron frequency.** With cadence damping + Hermes `wakeAgent: false` (cheap silent ticks), can the cron tick go from 30 min to 15 min without raising volume?
10. **SOUL.md invariant injection mechanism.** SOUL.md is regenerated on subject update; how to pin the invariants so the LLM does not rewrite them away?
11. **`reflection` event type safety.** Is reflection ever appropriate without a clinician in the loop? Default to disabled per-subject?
12. **UI repointing strategy.** Step 1.3 repoints UI from `checkin_decision_log.jsonl` to `RELIC_HOME/decision_events.jsonl`. Should we instead surface the canonical Chronicle event store directly through a Chronicle reader API (cleaner long term, more work now)?

### Conservative defaults for implementation

These defaults let the implementation plan proceed without inventing architecture while still leaving final product choices open for human review:

| Question | Default for first implementation |
|---|---|
| `wakeAgent:false` timing | Add opt-in support in step 2 via env flag; keep `[SILENT]` fallback and legacy stdout behavior until one profile is verified. |
| Composer location | Keep `registry.gumi_checkin_message` in Relic for the first pass; create a Hermes skill only after policy/logging stabilizes. |
| `world.md` ownership | Keep Hermes-owned; Relic reads it read-only. Do not move state between profile homes yet. |
| Posture vocabulary | Keep the explicit nine-posture enum for auditability; collapse only if evaluation shows sparse/confusing categories. |
| Proactive trigger source | Start with Relic queue consumer and explicit candidate writes; do not infer from broad polling until privacy review. |
| `select_facet` retirement | Keep `select_facet` for `(checkin, ask)` only; never let it drive whether Gumi speaks. |
| Damping curve | Keep `0.7^streak`, `REACH_THRESHOLD=0.35`, follow-up multiplier `1.3`; tune only through replay metrics. |
| UI posture exposure | Researcher workbench only; do not expose internal labels to the subject. |
| Cron frequency | Keep 30 min tick initially; consider 15 min only after silent-rate and wakeAgent metrics are stable. |
| SOUL.md invariants | Add invariant text through the existing generator, with regression tests that assert the lines remain present. |
| Reflection event | Disabled by default unless explicitly enabled per subject/profile. |
| UI source | Repoint to `RELIC_HOME/decision_events.jsonl` first, using the same resolution rule as the writer; Chronicle reader API is a later cleanup. |

---

## Scenarios

Seven scenarios required by prompt §"Also create a small set of example scenarios". Each shows: feature snapshot → posture → constraint header → message sketch.

### Scenario 1 — normal lightweight check-in

```
features = {
  time_since_last_subject_msg_sec: 18000,   # 5h
  subject_msg_count_24h: 3,
  non_response_streak: 0,
  topic_freshness: 0.3,
  salience_top: 0.2,
  last_posture: observe,
  ...
}
```

`select_decision(decision_type="checkin")` → `(checkin, observe)`.
Constraint: `[EVENTO: checkin] [POSTURA: observe] [VINCOLI: max 1 frase; senza domanda] [GROUNDING: nessuno]`
Message sketch: *"Pomeriggio tranquillo da queste parti."*

### Scenario 2 — follow-up on a previous conversation

```
features = {
  due_followup: true,
  non_response_streak: 0,
  last_exchange: {question: "come è andata?", answer: "boh, vediamo",
                  topic: "esame venerdì", asked_at: -14h},
  ...
}
```

`select_decision(decision_type="followup")` → `(followup, follow_up_warm)` (non_response_streak == 0).
Constraint: `[EVENTO: followup] [POSTURA: follow_up_warm] [VINCOLI: max 3 frasi; senza domanda] [GROUNDING: "esame venerdì" 14h fa]`
Message sketch: *"Ehi, niente fretta — solo per dire che il pensiero di venerdì mi è rimasto."*

### Scenario 3 — proactive grounded in recent context

(Triggered by `ProactiveCandidate` consumed by the proactive cron lane with `decision_type="proactivity"`.)

```
trigger = ProactiveCandidate{signal_ref: "subject mentioned 'mal di testa da 3 giorni'", priority: 0.7}
features = {
  salience_top: 0.7,
  time_since_last_subject_msg_sec: 7200,    # 2h
  non_response_streak: 0,
  ...
}
```

`select_decision(decision_type="proactivity")` → `(proactive, brief_share)` (salience_top > 0.6).
Constraint: `[EVENTO: proactive] [POSTURA: brief_share] [VINCOLI: max 1 frase; senza domanda] [GROUNDING: "mal di testa da 3 giorni" 2h fa]`
Message sketch: *"Se il mal di testa è ancora lì, magari oggi vai piano."*

### Scenario 4 — should stay silent

```
features = {
  non_response_streak: 3,
  reach_score: 0.34,
  time_since_last_subject_msg_sec: 86400,   # 24h
  quiet_hours_proximity_min: -30,            # 30 min inside quiet hours
  ...
}
```

`select_decision(decision_type="checkin")` → `(silent, quiet)`.
Hermes script gate emits `{"wakeAgent": false}`. **No LLM call. No message.**
Canonical event store records: `{event_kind: silent, posture: quiet, non_response_streak: 3, reach_score: 0.34, wake_agent_emitted: false}`.

### Scenario 5 — should avoid emotional overreach

```
features = {
  risk_flag_active: True,
  ...
}
```

`select_decision(...)` → `(silent, quiet)` (risk_flag short-circuit, first branch of decision tree).
Hermes `wakeAgent: false`. `escalation_notifier` (`relic/safety/escalation_notifier.py`) handles separately; Gumi does not attempt a "caring" message.

### Scenario 6 — share something small without hijacking

```
features = {
  subject_msg_count_24h: 12,                 # subject is talkative
  subject_avg_tokens_14d: 8,                 # but laconic per message
  time_since_last_subject_msg_sec: 600,      # 10 min
  salience_top: 0.5,
  ...
}
```

Forbidden-transition gate: `subject_avg_tokens_14d < 10` blocks `brief_share`.
`select_decision(decision_type="checkin")` → `(checkin, observe)`.
Constraint: `[EVENTO: checkin] [POSTURA: observe] [VINCOLI: max 1 frase; senza domanda] [GROUNDING: nessuno]`
Message sketch: *"Tutto bene da qui."*

### Scenario 7 — reduce future check-in frequency

```
delivered initiatives t..t+5 transition to unanswered_24h, so non_response_streak grows 0 → 5
reach_score   trajectory: 1.0, 0.7, 0.49, 0.343, 0.24, 0.17
```

From `streak=3` onward `select_decision` → `(silent, quiet)`. Hermes `wakeAgent: false` fires at the script gate — silent ticks are essentially free (no agent loop, no LLM call). Volume drops automatically without a config change. Recovery on first subject reply: streak resets to 0, reach_score back to 1.0.

No daily reset occurs. If Gumi sends nothing for 7 days after backing off, the decay rule can reduce the streak by 1 only if the subject has otherwise messaged recently. If the subject has been fully silent, the streak remains unchanged and Gumi keeps backing off.

### Scenario 8 — lower-frequency boundary without erasing history

```
state = {
  non_response_streak: 3,
  followup_non_response_streak: 1,
  explicit_boundary: "scrivimi meno spesso",
}
```

`select_decision` persists `frequency_cap_per_day` / `last_boundary_at` and applies that cap before `reach_score`. The streaks are not reset to 0. If the user later re-engages, reply handling resets the streaks; until then, explicit preference and non-response history both keep initiative low.

---

## Acceptance Criteria Self-Check

Mapping against the 10 acceptance criteria in the source prompt:

1. **Grounded in current codebase** — §2, §4 cite specific file:line. §2.5 verifies an actual writer/reader divergence bug.
2. **Verifies checkin/followup/proactivity paths** — §2.1, §2.5, §4.2 expose that the three are name-only and that `make_decision()` takes no `decision_type` parameter today.
3. **Studies Hermes documentation** — §3.1 cites both upstream docs and installed Hermes v0.11.0 source (`cronjob_tools.py`, `scheduler.py`); §3.2 explicit ownership split.
4. **Cites external sources** — §5 (7 sources) + §6 (7 repos), with links and verified code quotes (Park et al. retrieve.py / reflect.py).
5. **Avoids rigid mode splitting** — `(EventType, Posture)` selected by feature vector via deterministic decision tree, never rotated.
6. **Silence/timing/context/posture/availability as first-class** — silent is an EventType (§9.1); `(silent, quiet)` enforced at Hermes script gate via `wakeAgent: false` (§3.1, §10); cadence damping (§9.3); posture-filtered context (§10.2); availability via `time_since_last_subject_msg_sec`, `quiet_hours_proximity_min`, `subject_avg_tokens_14d`.
7. **Distinguishes scheduled vs proactive** — §8.2 separate paths; `decision_type` plumbed end-to-end (§14 step 1); §9.2 branches on `decision_type`.
8. **Specific enough to implement without inventing architecture** — §8 component-by-component, §9.2 pseudocode with thresholds, §11.1 SQL DDL, §11.2 log reconciliation migration order, §14 ordered steps with files listed.
9. **Consent-compatible** — `_evaluate_decision` (consent gate) unchanged; §13 risk_flag short-circuit; §9.2 `risk_flag_active` is the first decision-tree branch.
10. **Practical, not generic chatbot theory** — every section references files in this repo; second-pass Codex review surfaced concrete bugs that have been incorporated.

### Revision history

- v1: initial draft.
- v2: incorporated Codex second-pass review findings. Changes:
  - §2.5 rewritten as "observability split" with the verified writer/reader divergence bug.
  - §3.1 corrected: `no_agent` IS upstream Hermes; `wakeAgent: false` script gate IS upstream (v0.11.0+).
  - §8 / §9.1 / §9.2 split single `Posture` into orthogonal `(EventType, Posture)` axes.
  - §11.2 rewritten as canonical event store reconciliation (Chronicle + decision_events.jsonl mirror).
  - §14 step 1 prepended: log reconciliation + `decision_type` plumbing as observability prerequisite. Step 2 prepended: Hermes `wakeAgent: false` adoption.
  - §15 added open questions on `wakeAgent` adoption, Hermes composer skill, UI repointing strategy.

---

## Verification snippet

```bash
rtk pytest tests/checkin tests/gumi_plugin tests/hermes/test_no_agent_cron_wiring.py tests/profile/test_checkin_prompt_contract.py -q
```

See `docs/runbooks/gumi-checkin-policy-rollout.md` for the operator-side
rollout sequence with the canonical RELIC_HOME path inspection commands.
