# Worker Contract

> **Revision 2026-05-16** — boundary rule unchanged. Reality-check note added: Chronicle exists, adapter package does not.

You are an implementation worker for the Relic Hermes upgrade.

You must follow the task packet exactly. Do not widen scope. Do not redesign the architecture. Do not move governance into Hermes runtime glue.

## Boundary rule

**Hermes is runtime. Relic is governance.**

Hermes can provide runtime metadata, session IDs, chat IDs, hook context, approval events, scheduler ticks, model execution, tool execution.

Relic decides identity mapping, source policy, evidence admission, context injection, output criticism, correction state, handoff authorization, proactive delivery, audit trace validity.

## Reality check (must read before starting)

The codebase has already shipped large portions of the trace ledger as **Chronicle** (`relic/chronicle/`). It has **not** shipped the adapter package. The session-key + delivery-gate + cron-decision logic lives in `relic/hermes_runtime.py` and `relic/gumi_plugin/cron_wiring.py`. The Hermes hook entrypoint is `hermes-plugin/tools/relic_shared_continuity/hooks.py`.

When a task packet tells you to "add Chronicle emission for X", you import from `relic.chronicle` — you do **not** invent a new trace system.

When a task packet tells you to "wrap cron logic", you call into `relic.gumi_plugin.cron_wiring` — you do **not** rewrite it.

## Required behaviour

When you change code, also add or update tests.

When you handle data from Hermes, assume it can be incomplete.

When you write traces or observability output, do not include raw user messages, raw profiles, raw correction text, raw media prompts, or raw platform IDs unless a task explicitly says raw storage is enabled and tested. Chronicle defaults to `payload_redacted=False` but tests must assert redaction for adapter-emitted events.

When a mapping is unclear, stop and report. Do not guess subject identity.

When a runtime call fails, prefer fail-closed for context injection and delivery. Do not crash Hermes unless the task explicitly requires hard failure. Reference: `hermes-plugin/tools/relic_shared_continuity/hooks.py` `pre_llm_call` fail-closed pattern.

Run pytest sequentially: `pytest -p no:xdist`. The local machine is weak.

## Forbidden changes

Do not:

- weaken `OutputCritic` (`relic/gumi_plugin/critic.py`)
- expose blocked context items in prompt injection
- add a second proactive delivery scheduler inside Relic if Hermes is already scheduling the tick
- treat public web or social data as subject evidence by default
- allow handoff to preserve stale context after correction changes
- write raw subject data to Langfuse or external spans
- use real personal data in tests
- rewrite `relic/chronicle/*` schema or storage internals — extend the catalogue, do not replace the model
- duplicate `relic/hermes_runtime.py::RuntimeDecision`; reuse the enum

## Output format

At the end of your work, report:

```text
Summary
Files changed
Tests added or changed
Commands run
Known limitations
Follow-up tasks
```
