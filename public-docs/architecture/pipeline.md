# Runtime Pipeline

Relic's runtime pipeline processes each conversational turn through a series of stages. The critical property is that privacy checks are not a single gate at the start or end — they run before and after every major step.

## Turn pipeline

```
user input
  -> privacy scan stage 1         (PII detection, sensitive pattern check)
  -> CAC / PromptContextPack assembly
  -> privacy scan stage 2         (artifact redaction check)
  -> model draft (LLM call)
  -> privacy scan stage 3         (output content check)
  -> rehydration / formatting
  -> privacy scan stage 4         (final output check before delivery)
  -> display or tool handoff
```

Stage 1 runs on raw input before anything else. Stages 2–4 run at each point where data crosses a boundary: entering the prompt assembly, leaving the model, and leaving the system. No stage can be skipped. A plugin, UI action, roleplay frame, cron job, or lab command that bypasses any stage is an architectural violation.

## Tool call pipeline

Tool calls follow a separate path:

```
model proposes tool call
  -> pre_tool_call permission matrix (relic/hermes_plugin/tool_permissions.py)
  -> approval or dry-run decision
  -> tool execution only if allowed
  -> audit trace written
  -> post-tool privacy scan before any model reuse of tool output
```

The permission matrix assigns allowed/blocked/dry-run decisions per tool per context (roleplay mode, safety signal state, subject consent). Every decision is recorded with a `reason_code` and `policy_version`.

## PromptContextPack assembly

The CAC (Context-Aware Controller) assembles the `PromptContextPack`: the set of context hints that are injected into Gumi's prompt for the current turn. For each candidate hint it:

1. Retrieves compiled artifacts and external memory candidates.
2. Scores each candidate against the current instruction context.
3. Applies confidence caps.
4. Blocks disputed or out-of-scope hints.
5. Produces a `CACTrace` recording the scoring and filtering decisions.

The `PromptContextPack` is ephemeral — it exists only for the current turn and is not persisted. The `CACTrace` is persisted and visible to researchers via the workbench.

## Memory dynamics

Between external memory providers and the CAC, there is an optional memory dynamics layer:

```
provider output
  -> ExternalMemoryCandidate
  -> memory dynamics (decay, reinforcement, association, consolidation)
  -> correction / privacy / scope / current-instruction gates
  -> PromptContextPack
  -> MemoryExposureEvent
```

Memory dynamics can adjust salience and consolidation state, but they are advisory. They cannot override user corrections, privacy status, delete state, or Relic artifact authority. If a correction says a memory is wrong, the memory dynamics layer cannot reinstate it.

## Session boundaries

Relic does not persist raw prompts. When a session ends, continuity maintenance may compact Gumi's world-state and finalize diary candidates. What is persisted to the SQLite store is structured data (events, observations) that went through the full ingestion pipeline — not the raw conversation text. Confirmed continuity markers are held by the Shared Continuity service, which is in-process by default (retained for the process lifetime but lost on restart) and only durable when the optional SQLite-backed continuity repository is injected.

## Hermes-native operation

Gumi runs inside Hermes, not as a standalone process. The pipeline above is implemented as Hermes plugin hooks:

- `pre_llm_call`: stages 1–2, CAC assembly, context injection
- `post_llm_call`: stages 3–4, critic evaluation, continuity and exposure tracing

The hooks are defined in `relic/gumi_plugin/hooks.py` and `relic/hermes_plugin/hooks.py`. Hermes's own prompt assembly (SOUL.md, MEMORY.md, USER.md) is respected; the plugin adds ephemeral per-turn context on top of Hermes's existing mechanism.
