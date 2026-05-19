# Cron Check-in Naturalness Spike

## 1. Executive summary

Gumi's cron check-in system is inspectable and consent-aware in several important places, but the current behavior is still too mechanical because the decision layer mostly answers "may I send something now?" and "which media/question hint should I attach?" It does not yet model the conversational situation: whether there is a live thread to continue, whether silence is the least intrusive action, what posture fits the relationship state, how much initiative is appropriate, or how the last response/non-response should change future timing.

The most promising direction is a policy layer above the existing gates. Hermes should continue to own scheduling, profile isolation, delivery targets, cron job execution, skills, SOUL.md, and profile-local memory files. Relic/Gumi should own the subject-scoped policy evaluation, consent boundaries, longitudinal memory, risk scoring, logging, and post-run learning. The policy should emit a structured interaction decision, not a fixed mode rotation:

- `SILENT`
- `LIGHT_CHECKIN`
- `FOLLOWUP`
- `PROACTIVE_INTERVENTION`
- `REMINDER`
- `REFLECTION`
- `SMALL_SHARE`
- `REVIEW_REQUIRED`

That decision should include posture, grounding, timing rationale, suppression rationale, risk flags, and a future-adjustment recommendation. A Hermes cron job can then wake the LLM only when the policy says the interaction is worth spending attention and tokens on.

Key current gaps:

- `relic/gumi_plugin/cron_wiring.py` provisions separate `checkin`, `followup`, and `proactivity` scripts, but each rendered script calls the same `make_decision()` path. There is no separate verified proactivity policy.
- `_evaluate_decision()` gates quiet hours, active elicitation consent, pause state, delivery windows, deterministic jitter, due follow-ups, media type, and optional ask hints, but it does not distinguish scheduled check-in intent from opportunistic proactivity.
- `relic/checkin/question_engine.py` selects information gaps from a 60-facet profile model, but the selection is still a topic/question mechanism, not a conversational policy.
- `relic/checkin/context_builder.py` injects recent outbound check-ins, recent user messages, observations, topic hints, style hints, and avatar context, but it does not produce a compact decision record explaining why this tick should speak or stay silent.
- `ui/lib/workbench-data.ts` reads `$HERMES_HOME/workspace/gumi/cron/checkin_decision_log.jsonl`, but the inspected Python path writes `~/.relic/decision_events.jsonl` and Chronicle `cron_decision` events. This looks like an observability split that should be reconciled before relying on the UI metric.

## 2. Current implementation map

### Cron provisioning

`relic/gumi_plugin/cron_wiring.py` is the central cron wiring module. `provision_for_subject()` creates scripts under `~/.hermes/scripts/<subject_id>/` and defines:

```python
decision_types = ["checkin", "followup", "proactivity"]
```

For each type it writes `relic_<dtype>_decision.sh`, registers `hermes cron create --no-agent --script ...`, and names the job `relic_no_agent_<dtype>_<subject_id>`. The important verified detail is that all three scripts are produced by the same `render_no_agent_script()` function. The type-specific filename and job name do not currently imply type-specific decision semantics.

`render_no_agent_script()` executes Python inline, calls `make_decision(subject_id, gumi_instance_id, hermes_profile_id, force=...)`, emits an audit event, and:

- exits silently for `NO_REPLY`;
- prints candidate text for `CANDIDATE`;
- prints `DELIVER` metadata and `build_deliver_context()` output for `DELIVER`;
- suppresses stdout for `BLOCKED` or `ERROR`.

There is also a memory sync cron script from `render_memory_sync_script()`, intended to scan cron sessions and update `MEMORY.md`.

### Runtime decision path

`make_decision()` either force-delivers for manual testing or delegates to `_evaluate_decision()`.

`_evaluate_decision()` applies these gates:

- global `/relic pause` through `PauseController().is_any_session_paused()`;
- subject proactive check-in opt-out through `PRO_CHECKIN`;
- quiet hours from `delivery_policy.json`;
- active elicitation consent via `consent_for_active_elicitation`;
- subject active status;
- continuity-scope pause;
- due follow-ups from `ContinuityService.due_followups()`;
- delivery window and deterministic jitter through `_is_delivery_window_open()`;
- media type via `_select_media_type()`;
- optional open-question hint via `_select_ask_decision()`.

The final normal `DELIVER` payload is a terse control block:

```text
DELIVER
tipo: <text|voice|image|music>
ora: <local time>
ask: true
ask_topic: <hint>
```

This is useful as a gate, but too thin as a naturalness policy. It says the system may speak; it does not say what kind of social action speaking would be.

### Check-in timing

There are two timing implementations:

- `relic/gumi_plugin/cron_wiring.py` reads `delivery_policy.json` delivery windows, quiet hours, timezone, and `baseline_user_profile.json` `interaction_preferences.response_timing_expectation`. It then chooses a stable daily jitter point inside the active window and prevents more than one outbound per window.
- `relic/checkin/scheduler.py` reads `gumi_cron_manifest.json` `checkin_schedule` with windows, quiet hours, min spacing, max per day, min per day, and timezone. It exposes `check_gate()`, but the inspected `cron_wiring.py` path does not call this module directly.

This split should be resolved. The redesign should have one subject-level timing model with named fields and one canonical audit trail.

### Question and topic selection

`relic/checkin/question_engine.py` implements a topic gap score over a 60-facet longitudinal model. It combines unknownness, impact, timeliness, intrusion, and asked-recently penalties, then chooses from top candidates with seeded weighted randomness. It strips clinical scale references before rendering hints.

This is a reasonable input for "what could we learn next?", but it should not be the sole driver of "should Gumi check in?". A natural partner can choose not to ask even when a facet is underexplored.

`relic/checkin/anti_repeat.py` adds duplicate prevention over recent questions.

`relic/checkin/db_init.py` defines `checkin_exchanges` with `facet_id`, `question_text`, `reply_text`, `reply_captured_at`, `observations_extracted`, `asked_at`, `message_id`, and `followup_sent_at`.

`relic/checkin/reply_capture.py` captures a user reply into the most recent pending check-in exchange when allowed.

`relic/checkin/facet_updater.py` extracts observations from replies and updates traits.

### Context construction

`relic/checkin/context_builder.py` builds the prompt context for delivery:

- recent check-in messages from Hermes `MEMORY.md`;
- recent subject-authored Hermes `state.db` messages, excluding cron task prompts;
- recent observations from `relic.db`, consent-gated;
- a selected topic hint and `checkin_exchanges` insert, consent-gated;
- style hints from `subject_baseline.json`, consent-gated;
- avatar spec from `AVATAR_SPEC.md`.

The context is pragmatic but not yet policy-shaped. It gives the LLM material; it does not tell it the chosen posture, risk level, or reason for interrupting.

### Media delivery

`relic/gumi_plugin/checkin_media_dispatcher.py` parses `tipo:`, `caption:`, and `image_prompt:`. Text is sanitized by `sanitize_for_subject()` and printed to stdout; voice, image, and music can be sent directly via Telegram Bot API. Media cooldowns and opt-outs are handled in `cron_wiring.py`.

### Hermes adapter and delivery gate

`relic/hermes_adapter/cron_bridge.py` declares the intended boundary: "Hermes owns scheduling. Relic owns delivery decisions." Its current `evaluate_proactive_delivery()` is a simple wrapper: no candidate means `NO_REPLY`, candidate means `CANDIDATE`. Quiet-hours and platform checks are stubbed. This should become either a real facade over the new policy layer or be removed to avoid a false sense of implemented proactivity.

`relic/hermes_runtime.py` contains runtime decision enums, delivery gates, subject/profile scoping, and session-key scoping. It is the right place for shared decision result types, but the naturalness policy needs richer fields than the current `RuntimeDecision`.

### Memory, profile, and state access

`relic/hermes_plugin/memory_provider.py` registers a subject-scoped Hermes memory provider. It prefetches only confirmed continuity markers, blocks `sensitive_signal` origin markers, and captures check-in replies only as a consent-gated carve-out into the subject's own Relic DB. This is compatible with the redesign and should be kept.

`relic/gumi_plugin/memory_sync.py` scans Hermes cron sessions and appends assistant messages to `MEMORY.md` in a bounded rolling block.

`relic/profiles.py` defines profile names such as `companion`, `relic-maintainer`, and `gumi`, but the richer Hermes profile policy appears to live outside this file in actual Hermes homes.

### Logging and UI

`emit_decision_event()` writes to `~/.relic/decision_events.jsonl` and attempts to emit Chronicle `cron_decision` and `cron_evaluator` events.

`ui/lib/workbench-data.ts` reads `$HERMES_HOME/workspace/gumi/cron/checkin_decision_log.jsonl` to compute pending proactive count and last initiative time. I did not find a writer for that path in the inspected code. The spike should treat this as an unresolved integration gap, not as proof that proactive decisions are currently logged end-to-end.

## 3. Hermes integration map

Hermes documentation matters because cron behavior will be profile-managed, not just a Relic subprocess.

Relevant Hermes facts:

- Hermes cron can schedule recurring or one-shot jobs, attach skills, deliver results to platform targets, and run no-agent scripts whose stdout is delivered verbatim. Source: [Scheduled Tasks](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron/).
- Cron sessions are fresh sessions with no prior conversation history unless state is persisted to memory/files or passed through `context_from`. Source: [Cron Internals](https://hermes-agent.nousresearch.com/docs/developer-guide/cron-internals).
- `script=` can act as a pre-run gate. A script can emit `{"wakeAgent": false}` to skip the LLM or `{"wakeAgent": true, "context": {...}}` to wake it with structured context. Source: [Scheduled Tasks](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron/).
- Cron job outputs are saved under `~/.hermes/cron/output/{job_id}/`, and jobs live in `~/.hermes/cron/jobs.json`.
- Profiles are separate Hermes home directories with their own `config.yaml`, `.env`, `SOUL.md`, memories, sessions, skills, cron jobs, and state database. Source: [Profiles](https://hermes-agent.nousresearch.com/docs/user-guide/profiles).
- `SOUL.md` is loaded only from `HERMES_HOME`, occupies the primary identity slot, and should contain durable identity/style, not one-off workflow details. Source: [Personality & SOUL.md](https://hermes-agent.nousresearch.com/docs/user-guide/features/personality).
- Hermes memory providers inject relevant cross-session context before turns and sync turns after responses; built-in `MEMORY.md` / `USER.md` remain active. Source: [Memory Providers](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory-providers/).

### What should live in Hermes profile configuration

- Cron schedule definitions, names, delivery targets, no-agent vs agent-backed job choice.
- Profile-local `SOUL.md`: Gumi's durable voice, default warmth, directness, and interaction boundaries.
- Profile-local `config.yaml`: model/provider/toolset configuration, cron script timeout, fallback providers.
- Profile-local skills: reusable prompt procedures for "compose a bounded check-in", "evaluate if this is therapeutic overreach", "summarize a check-in outcome".
- Profile-local context files: stable user-approved relationship policy, delivery policy, and channel capabilities.
- Hermes `cron` platform toolset restrictions.

### What should stay in Relic/Gumi code

- Subject consent, pause state, delivery policy enforcement, and active elicitation permissions.
- Longitudinal memory model, continuity markers, check-in exchanges, reply capture, profile traits, and privacy gates.
- The naturalness policy evaluator and its audit log.
- Timing policy derived from subject state, response/non-response, availability, interruption cost, and interaction budget.
- Data minimization rules: what may be sent to Hermes prompt context and what must stay in Relic.
- UI/workbench observability over decisions, suppressions, and policy outcomes.

### Recommended Hermes shape

Use a two-stage cron:

1. Frequent no-agent policy gate:
   - runs every 15-30 minutes;
   - calls Relic `gumi_interaction_policy evaluate`;
   - emits `wakeAgent:false` when silent;
   - emits `wakeAgent:true` and compact context only when a message is warranted.
2. Agent-backed composer:
   - uses a Gumi check-in skill;
   - receives only the policy decision and approved context;
   - returns `[SILENT]` if the composer detects risk not caught by the policy;
   - delivers through Hermes or existing media dispatcher depending on target.

This fits Hermes' documented `script`/`wakeAgent` pattern and preserves Hermes profile ownership over cron while keeping Relic as the policy authority.

## 4. Failure analysis

### Prompt-level issues

- The current `DELIVER` control block does not give the LLM a conversational posture or reason for speaking.
- Context sections are useful but can encourage "use all context" behavior unless the prompt explicitly says what not to mention.
- Topic hints can produce questions even when the more natural move is to acknowledge, follow up, or stay quiet.
- The prompt likely over-indexes on generating an outbound message because the script has already decided `DELIVER`.

### Architecture-level issues

- `checkin`, `followup`, and `proactivity` are provisioned as separate jobs but share the same decision function. This makes the architecture look more differentiated than it is.
- The current decision enum is delivery-focused, not interaction-focused.
- `CronBridge.evaluate_proactive_delivery()` is too shallow to represent proactivity.
- Timing, question selection, context construction, and media selection are separate utilities without a single policy record that explains the chosen action.

### Timing issues

- Delivery windows and jitter prevent obviously bad timing, but they do not model user availability beyond static windows.
- Non-response does not appear to reduce future frequency in a first-class way.
- Recent user-initiated conversation can be read from Hermes `state.db`, but the policy does not treat it as an explicit "conversation already active" signal.
- Silence is a side effect of gates, not a deliberate social decision with a rationale.

### Memory/context issues

- Recent check-ins are read from `MEMORY.md`; recent messages are read from Hermes `state.db`; observations and traits come from Relic DB/baseline. These sources are not normalized into recency/salience/risk features before prompting.
- Check-in exchange memory tracks questions and replies, but not enough about the social outcome: ignored, answered warmly, answered tersely, boundary signaled, topic stale, too intrusive, good follow-up candidate.
- There is no separate "proactive decision memory" recording what Gumi wanted to say but suppressed.

### Hermes integration issues

- Cron fresh-session isolation means every job prompt must be self-contained or receive explicit context. The current context builder helps, but the policy should produce a compact, stable decision packet.
- Profile-local `SOUL.md` should hold stable identity, but dynamic check-in rules should not be buried there.
- The inspected UI expects `checkin_decision_log.jsonl`, while the code writes `decision_events.jsonl` and Chronicle events.

### Evaluation issues

- Existing gates can be unit-tested, but they do not test whether a message felt natural.
- There is no scenario corpus for "should stay silent", "avoid emotional overreach", "small share", or "reduce frequency after non-response".
- Repetition is checked mostly at question-text level, not at opening posture, topic family, or initiative pattern.

## 5. Literature and external source review

### Relational agents and rapport

Bickmore and Cassell's relational agent work argues that trust grows through incremental evidence and that small talk/task talk should be interleaved by a discourse planner balancing face threat, familiarity, relevance, and intrusion, not by static scripts. In their REA implementation, conversational moves are selected through an activation-network approach that can shift between planned and opportunistic behavior. Source: [Relational Agents, CHI 2001 PDF](https://www.ccs.neu.edu/home/bickmore/publications/CHI2001.pdf).

Application to Gumi: a natural check-in policy should score multiple conversational moves against relationship state and intrusion cost. "Ask a question" should be one possible move, not the default.

### Human-centered proactive conversational agents

Deng et al. frame proactive conversational agents around initiative-taking and warn that proactive systems can be perceived as intrusive without human-centered design. They propose focusing on intelligence, adaptivity, and civility rather than only anticipation capability. Source: [Towards Human-centered Proactive Conversational Agents](https://arxiv.org/abs/2404.12670).

Application to Gumi: proactivity should require civility checks: user control, contextual appropriateness, bounded initiative, and explicit suppression when risk or interruption cost is high.

### Proactive agents with inner thoughts

Liu et al. propose that proactive agents should not merely react to turn-taking cues; they should maintain an internal motivation stream and seek the right moment to contribute. Source: [Proactive Conversational Agents with Inner Thoughts](https://arxiv.org/abs/2501.00383).

Application to Gumi: do not copy hidden unbounded thoughts. Instead, implement an inspectable "candidate initiative ledger": possible contributions with salience, urgency, risk, expiry, and suppression history.

### Conversation analysis

Conversation analysis emphasizes turn-taking, adjacency pairs, repair, recipient design, and topic management. A practical healthcare education review summarizes recipient design as shaping talk to prior utterances and the anticipated next sequence. Source: [Using Applied Conversation Analysis in Patient Education](https://pmc.ncbi.nlm.nih.gov/articles/PMC8165833/).

Application to Gumi: a check-in should be treated as a conversational action that creates obligations. If Gumi asks, it creates an adjacency-pair expectation. If the user does not answer, retrying the same shape increases pressure. The policy needs repair and topic-bounding moves, not only new questions.

### Intelligent notification timing

Mehrotra and Musolesi survey notification systems and argue that notifications at inopportune moments can become disruptive; intelligent systems should infer the right time and context from user preferences and interruptibility. Source: [Intelligent Notification Systems](https://arxiv.org/abs/1711.10171).

A large-scale adaptive scheduling study found that breakpoint-based delivery improved response speed and engagement, while also noting production constraints and privacy-sensitive sensing choices. Source: [Real-world large-scale study on adaptive notification scheduling](https://www.sciencedirect.com/science/article/abs/pii/S1574119217304388).

Application to Gumi: static windows are only the first layer. The policy should estimate interruption cost from recent activity, last user message, day pattern, response history, channel, and explicit preferences, while avoiding invasive sensing unless consented.

## 6. GitHub/open-source review

### memU

[NevaMind-AI/memU](https://github.com/NevaMind-AI/memU) frames proactive memory as a background process that observes interactions, tracks conversation flow, extracts memories, organizes them into resource/item/category layers, and supports proactive context loading. The useful pattern is not the product claim; it is the separation between continuous memory processing and reactive generation.

Pattern for Gumi: keep a background memory/initiative extraction loop separate from cron message composition. Let it produce candidates and salience features; do not let it directly send messages.

### ProactiveAgent

[leomariga/ProactiveAgent](https://github.com/leomariga/ProactiveAgent) separates a proactive loop into: decision engine, message generation, and sleep-time calculator. It exposes callbacks for response, decision, and sleep-time reasoning, plus custom decision engines.

Pattern for Gumi: separate `should_speak`, `compose`, and `next_check_time`. Log all three decisions. Avoid the library's simpler "normal text chat pace" configuration as a final policy, but borrow the component boundary.

### Mercury Agent

[cosmicstack-labs/mercury-agent](https://github.com/cosmicstack-labs/mercury-agent) combines a soul/persona file model, scheduler, heartbeat, proactive notifications, and a local "Second Brain" that extracts structured memory types with confidence, importance, durability, consolidation, conflict resolution, decay, and user controls.

Pattern for Gumi: memory items need type, confidence, durability, and decay. User controls such as pause/resume/clear should be visible for proactive behavior.

### MicroClaw

[microclaw/microclaw](https://github.com/microclaw/microclaw) uses layered memory scopes (`global`, `bot`, `chat`), structured SQLite memory fallback, health/self-check output, and observability for memory pool health and injection coverage.

Pattern for Gumi: maintain scope boundaries between Gumi identity, subject relationship, and per-channel state. Add observability for why memories were injected into a check-in prompt.

### Memoh

[memohai/Memoh](https://github.com/memohai/Memoh) emphasizes isolated bot containers, local-first memory, multi-user privacy boundaries, schedule/heartbeat sessions, and visual configuration.

Pattern for Gumi: proactive behavior should be profile- and subject-isolated, with explicit config and inspection rather than hidden global state.

### TiMem

[TiMEM-AI/timem](https://github.com/TiMEM-AI/timem) organizes memory into temporal hierarchy from fine fragments to stable persona and uses complexity-aware recall.

Pattern for Gumi: check-ins need different memory granularity depending on posture. A lightweight "how did today go?" message should not load deep persona facts; a follow-up can load the specific prior episode and confirmed preference.

## 7. Design principles for Gumi check-ins and proactivity

1. Silence is a valid decision, not a failure to generate.
2. Scheduled check-ins and proactive interventions are distinct. A scheduled check-in is relationship maintenance within an agreed cadence; proactivity is opportunistic initiative triggered by salient context.
3. The policy chooses posture before wording.
4. Do not ask merely because a facet is underexplored.
5. Respect non-response as data, but never assume it means rejection.
6. Keep messages short by default.
7. Grounding must be recent, specific, and non-creepy. Prefer "you mentioned X earlier" over inferred psychological labels.
8. Emotional content needs stricter thresholds than practical reminders or light social check-ins.
9. Longitudinal variation should come from state and salience, not random mode rotation.
10. Every outbound and suppressed initiative must be inspectable.
11. User boundaries must be profile-configurable and subject-overridable.
12. The system should learn from outcomes: reply, no reply, terse reply, explicit boundary, positive continuation, correction.

## 8. Proposed architecture

### Components

`Hermes cron job`
: Owns schedule and delivery target. Runs a script gate first.

`Relic interaction policy evaluator`
: Computes the interaction decision from subject state, Hermes profile state, recent messages, memory, delivery policy, and candidate initiatives.

`Candidate initiative store`
: Stores possible follow-ups, reminders, reflections, small shares, and proactive observations with salience, expiry, risk, and status.

`Prompt packet builder`
: Converts the policy decision into a compact composer packet with approved context only.

`Gumi composer skill`
: Hermes skill that turns a policy packet into a short message or `[SILENT]`.

`Delivery dispatcher`
: Existing text/media dispatcher plus delivery gate.

`Outcome updater`
: Records user response/non-response and adjusts future policy features.

`Workbench log/view`
: Shows decisions, suppressions, candidate initiatives, context used, risk flags, and outcomes.

### Inputs

- Subject delivery policy: consent, quiet hours, windows, channel allowlist, proactive tolerance, media permissions.
- Hermes profile: `SOUL.md`, skills, model/toolset, cron config, memory files, state database.
- Recent conversation: user messages, assistant messages, active thread state.
- Relic memory: confirmed continuity markers, traits, observations, check-in exchanges.
- Candidate initiatives: due follow-ups, reminders, pending topics, recent external/context events.
- Interaction history: last check-ins, response latency, non-response streak, boundary feedback.

### Output data structure

```json
{
  "decision_id": "uuid",
  "subject_id": "daniele",
  "hermes_profile_id": "gumi",
  "event_type": "FOLLOWUP",
  "speak": true,
  "posture": "light_followup",
  "initiative_level": 0.35,
  "urgency": 0.2,
  "interruption_cost": 0.25,
  "emotional_risk": 0.1,
  "grounding_refs": ["checkin_exchange:123"],
  "allowed_context": {
    "recent_user_signal": "answered briefly yesterday",
    "topic": "project deadline",
    "avoid": ["diagnosis", "pressure", "long explanation"]
  },
  "rationale": "Due follow-up, user replied positively last time, within agreed window.",
  "suppressed_alternatives": [
    {"event_type": "QUESTION", "reason": "asked similar question <72h ago"}
  ],
  "future_adjustment": {
    "if_no_reply": "reduce_checkin_frequency",
    "cooldown_hours": 36
  }
}
```

## 9. Check-in and proactivity policy model

Use a scoring and constraint policy, not fixed behavior modes.

### Stage 1: hard gates

- paused or inactive subject;
- active elicitation consent missing;
- quiet hours;
- platform not allowlisted;
- daily/weekly initiative budget exhausted;
- emotional risk above configured threshold;
- sensitive signal origin not allowed for prompt use;
- duplicate recent message or topic.

### Stage 2: candidate generation

Generate candidates from:

- due follow-ups from shared continuity;
- scheduled check-in cadence;
- open `checkin_exchanges` needing reply capture or recovery;
- recent user messages that invite a later follow-up;
- reminders or external events explicitly configured by the user;
- small Gumi shares allowed by profile policy;
- proactive observations from approved context sources.

Each candidate gets:

- `candidate_type`;
- `source_ref`;
- `created_at`, `expires_at`;
- `salience`;
- `user_benefit`;
- `relationship_fit`;
- `interruption_cost`;
- `emotional_risk`;
- `privacy_risk`;
- `repetition_risk`;
- `required_posture`;
- `requires_review`.

### Stage 3: posture selection

Posture is the interaction stance, independent of surface text:

- `quiet`: no message;
- `light_presence`: brief "sono qui" without demand;
- `curious_question`: one low-pressure question;
- `specific_followup`: continue a prior user-raised topic;
- `practical_reminder`: task/reminder with minimal affect;
- `reflective_mirror`: summarize user-stated content without inference;
- `small_share`: Gumi shares a small non-demanding bit;
- `repair`: acknowledge possible overreach or missed response;
- `boundary_respect`: explicitly reduce contact or stay silent.

### Stage 4: decision

Choose the highest expected value candidate after constraints. If the top candidate does not clear a minimum value threshold, emit `SILENT` with a reason. If there is due follow-up but high interruption cost, emit `DEFER` with next evaluation time.

### Stage 5: future update

After outcome:

- answered warmly: maintain or slightly increase salience for that topic family;
- answered tersely: reduce initiative level and avoid follow-up unless necessary;
- no reply once: extend cooldown, do not infer emotion;
- no reply repeatedly: reduce frequency and switch to silence/light presence only;
- explicit boundary: store boundary and block matching future candidates;
- correction: update memory and mark prior assumption invalid.

## 10. Prompting strategy

The composer prompt should be short and structured:

1. System identity from Hermes `SOUL.md`.
2. Gumi check-in skill: rules for bounded, non-therapeutic, consent-aware composition.
3. Policy packet from Relic.
4. Recent context approved by the policy.
5. Output contract.

Output contract:

```text
Return exactly one of:
- [SILENT]
- tipo: text
  testo: <one short message>
- tipo: voice
  testo: <one short voice script>
- tipo: image
  caption: <short caption>
  image_prompt: <safe image prompt>
```

Prompt constraints:

- Do not mention internal policy scores.
- Do not reveal facet IDs, clinical scale names, or inferred traits.
- Do not ask more than one question.
- Do not combine a question, a reminder, and a self-share in one message.
- Do not escalate emotional intimacy beyond the user's last demonstrated level.
- Prefer silence if the policy packet and context conflict.
- If grounding would sound creepy, remove the grounding rather than over-explain it.

## 11. Data model and logging changes

### New table or JSONL event: `gumi_interaction_decisions`

Fields:

- `decision_id`
- `created_at`
- `subject_id`
- `gumi_instance_id`
- `hermes_profile_id`
- `cron_job_id`
- `decision_type`
- `speak`
- `posture`
- `initiative_level`
- `candidate_id`
- `rationale_summary`
- `reason_codes`
- `suppressed_alternatives`
- `context_refs`
- `memory_refs`
- `risk_flags`
- `privacy_level`
- `delivery_target`
- `composer_result_hash`
- `final_delivery_status`
- `outcome_status`

### New table or JSONL event: `gumi_initiative_candidates`

Fields:

- `candidate_id`
- `candidate_type`
- `source_ref`
- `topic_key`
- `created_at`
- `expires_at`
- `salience`
- `urgency`
- `user_benefit`
- `interruption_cost`
- `emotional_risk`
- `privacy_risk`
- `repetition_risk`
- `status`
- `last_evaluated_at`
- `suppression_count`

### Extend `checkin_exchanges`

Add or companion-log:

- `posture`
- `decision_id`
- `message_hash`
- `outcome_status`
- `reply_latency_seconds`
- `boundary_signal_detected`
- `future_cooldown_hours`

### Logging reconciliation

Unify or bridge:

- `~/.relic/decision_events.jsonl`;
- Chronicle `cron_decision`/`cron_evaluator`;
- Hermes `$HERMES_HOME/workspace/gumi/cron/checkin_decision_log.jsonl` expected by UI.

The workbench should read the canonical event store first and use JSONL only as a compatibility fallback.

## 12. Evaluation plan

### Qualitative review criteria

- Does the message have a clear reason to exist?
- Is it short enough for the situation?
- Does it preserve the user's freedom not to answer?
- Is the grounding recent and user-visible?
- Does the posture fit the last interaction?
- Would silence have been better?
- Does it avoid therapeutic framing?
- Does it avoid repetitive openings and topics?

### Automated checks

- No message when hard gates fail.
- No more than one question.
- No clinical labels, facet IDs, or scale names.
- No repeated opening/template within N recent check-ins.
- No proactive emotional message when emotional risk exceeds threshold.
- Non-response streak reduces future frequency.
- Explicit boundary blocks matching candidate types.
- `checkin`, `followup`, and `proactivity` jobs produce distinguishable decision records.
- UI pending proactive count is backed by the canonical decision log.

### Scenario corpus

Create fixtures with:

- recent message history;
- delivery policy;
- memory markers;
- candidate initiatives;
- expected decision/posture;
- expected suppression reasons.

Run each fixture through the policy evaluator and composer. For composer outputs, use deterministic mocked LLM responses for contract tests and human review for naturalness.

## 13. Risks and guardrails

- Privacy: do not inject sensitive or unconfirmed markers. Keep source refs and privacy levels in every context packet.
- Creepiness: avoid mentioning patterns the user did not explicitly surface unless the user opted into that level of reflection.
- Emotional overreach: do not diagnose, counsel, or intensify affect. Escalate to silence or low-pressure acknowledgement.
- Repetition: track posture, opening, topic family, and grounding source, not just question text.
- Excessive proactivity: enforce daily and weekly initiative budgets.
- Hallucinated intimacy: require grounding refs for personalized claims.
- User control: support pause, lower frequency, no questions, no media, no proactive contact, and channel-specific limits.
- Accidental therapy: ban therapeutic claims and require review for high emotional risk.
- Profile leakage: never mix Hermes profile memory across subjects.
- Observability drift: one canonical decision event must power audit and UI.

## 14. Example scenarios

### Normal lightweight check-in

Context: no conversation today, within delivery window, no non-response streak, user allows light check-ins.

Decision: `LIGHT_CHECKIN`, posture `light_presence`.

Example: "Passo solo un attimo: giornata gestibile fin qui?"

Why natural: short, no heavy grounding, one easy answer path.

### Follow-up based on previous conversation

Context: yesterday the user mentioned preparing a demo and replied positively to a brief question.

Decision: `FOLLOWUP`, posture `specific_followup`.

Example: "Com'è andata poi con la demo? Anche una risposta secca va bene."

Why natural: follows the user's topic, keeps pressure low.

### Proactive message grounded in recent context

Context: user explicitly asked Gumi to watch for a release note; new relevant item appears.

Decision: `PROACTIVE_INTERVENTION`, posture `practical_reminder`.

Example: "È uscito l'aggiornamento che volevi seguire. Ti lascio solo il punto utile: cambia la compatibilità del plugin."

Why natural: user-authorized, useful, not pretending emotional intimacy.

### Stay silent

Context: user has not replied to three recent check-ins, no urgent candidate, quiet period ended recently.

Decision: `SILENT`, posture `quiet`, future adjustment `reduce_checkin_frequency`.

Why natural: repeated outreach would create pressure. Silence respects ambiguity.

### Avoid emotional overreach

Context: user wrote "giornata pesante" but did not invite support; emotional risk medium; recent non-response to emotional prompts.

Decision: `LIGHT_CHECKIN` or `SILENT`, not reflective therapy.

Example if speaking: "Ricevuto. Non ti riempio di domande; sono qui se vuoi scaricare due righe."

Why natural: acknowledges without analysis or advice.

### Share something small without hijacking

Context: user likes small ambient updates from Gumi, no open user thread, proactive budget available.

Decision: `SMALL_SHARE`, posture `small_share`.

Example: "Mini cosa dal mio lato: oggi tengo il tono più leggero. Se vuoi, resto in modalità presenza discreta."

Why natural: self-share is small and leaves the floor to the user.

### Reduce future check-in frequency

Context: two consecutive unanswered check-ins and one terse reply.

Decision: `SILENT`, future adjustment `cooldown_hours=72`, lower initiative budget.

Why natural: the system treats weak engagement as a reason to back off without interpreting the user's feelings.

## 15. Implementation plan

1. Reconcile logs.
   - Add a canonical interaction decision event.
   - Update UI to read it.
   - Keep `decision_events.jsonl` compatibility during transition.

2. Make decision type real.
   - Pass `decision_type` from each generated script into Python.
   - Ensure `checkin`, `followup`, and `proactivity` have separate candidate sources and reason codes.

3. Extract a pure policy evaluator.
   - Inputs: policy, recent messages, check-in history, continuity candidates, memory refs, now.
   - Output: structured decision packet.
   - No LLM call.

4. Add candidate initiative store.
   - Start with due follow-ups, scheduled check-in, and explicit reminders.
   - Add proactive observations later.

5. Replace direct `DELIVER` context with policy packet.
   - `wakeAgent:false` for silence.
   - `wakeAgent:true` with compact approved context for delivery.

6. Create Hermes Gumi check-in skill.
   - Composer contract.
   - Guardrails.
   - `[SILENT]` fallback.

7. Add outcome updater.
   - Capture reply/no-reply and boundary signals.
   - Update future cooldown/frequency fields.

8. Add scenario tests.
   - Cover all example scenarios.
   - Verify no fixed behavior rotation.

9. Human review pass.
   - Review sampled outputs by posture and risk level.
   - Tune thresholds before enabling automatic delivery.

## 16. Open questions

- Should proactive observations ever be composed by the LLM before human review, or should only reminders/follow-ups auto-deliver at first?
- What is the default daily/weekly initiative budget for Gumi?
- Which signals are acceptable for availability inference without feeling invasive?
- Should media check-ins be governed by the same initiative budget as text?
- Should `relationship_policy.md` be treated as Hermes profile config, Relic subject policy, or both with a sync process?
- What is the canonical event store for the workbench: Chronicle only, JSONL mirror, or both?
- How should the user configure "small shares from Gumi" separately from questions and reminders?
- What are the escalation rules when emotional risk is high but the user has explicitly asked for follow-up?

## 17. Parts not to change during this spike

- Do not remove existing consent gates, pause handling, quiet-hours checks, or media opt-outs.
- Do not collapse Relic subject memory into Hermes profile memory.
- Do not rewrite SOUL.md as a substitute for policy.
- Do not implement a four-mode rotation.
- Do not make current `question_engine.py` responsible for the whole interaction decision.
- Do not expand context with sensitive or unconfirmed markers to improve "naturalness".

