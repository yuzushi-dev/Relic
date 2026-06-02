# CAC: How Memory Decisions Are Scored

The Context-Aware Controller (CAC) decides, every turn, whether each candidate memory may influence Gumi. This page explains the inputs, the severity ladder, and the decision outcomes, at the level a researcher needs to read a CAC trace without surprise.

Source: `relic/cac/`.

## Pipeline

```
candidates from memory provider, continuity, profile
  ↓
score (per candidate): assigns a SeverityClass
  ↓
determine_decision: maps severity + context to CACDecision
  ↓
render: converts allowed decisions to PromptContextPack
  ↓
trace: writes CACTrace event (immutable)
```

The trace is the auditable artefact: every decision, with the inputs that produced it, ends up queryable via `chronicle decision --kind cac_decision`.

## Inputs to the scorer

Each candidate arrives as a `CACInput` (`relic/cac/types.py`):

| Field | What it carries |
|---|---|
| `memory_content` | The actual text. May be `None` for no-op evaluation. |
| `memory_hash` | SHA-256 hash for audit. Always present. |
| `memory_id` | Stable identifier. |
| `source` | One of `provider_memory`, `user_correction`, `inference`, `external`, `unknown`. |
| `disputed` | Boolean: has the subject or researcher disputed this memory? |
| `dispute_reason` | If `disputed`, why. |
| `metadata` | Extras: confidence, correction_type, verified, … |

The input never contains raw session text, only the memory content under evaluation, its hash, and structured metadata.

## Severity ladder

| Severity | Meaning |
|---|---|
| `NONE` | No issue. The candidate is admitted normally. |
| `S2` | Warning. Admitted but flagged in the trace; downstream renderer may attach a warning. |
| `S1` | Quarantine. Blocked from this turn pending reviewer disposition. |
| `S0` | Hard block. Must not be injected or influence runtime under any circumstance. |

S0 is reserved for disputed memories. Once a memory is marked disputed (subject correction, researcher feedback), the scorer will never re-elevate it.

## Scoring rules (in order)

The scorer walks rules top-to-bottom and stops at the first match:

1. **No content** → `NONE`. No evaluation needed.
2. **Disputed memory** → `S0`. Hard block. The dispute reason is recorded in the factors.
3. **Source = `unknown`** → `S1`. Quarantine until a reviewer dispositions.
4. **Source = `external` and unverified** → `S1`. Same.
5. **Source = `inference`**:
    - `metadata.confidence < 0.7` → `S1` (low-confidence inference).
    - else → `S2` (high-confidence inference, admitted with warning).
6. **Source = `user_correction`**:
    - `metadata.correction_type == "factual"` → `NONE` (trusted).
    - else → `S2` (admitted with warning).
7. **Source = `provider_memory`**:
    - `metadata.verified == True` → `S2` (admitted with warning).
    - else → `S1` (unverified provider memory, quarantine).

Every rule fires a `factor` string into the scoring result. Factors are what makes a CAC trace readable: `disputed_memory:dispute_reason`, `low_inference_confidence:0.42`, `verified_provider_memory_with_warning`, …

## Decision outcomes

After scoring, `determine_decision` maps severity to a `CACDecision`:

| Decision | When | What happens at render |
|---|---|---|
| `none` | No candidate / `NONE` severity with no content | Skipped silently |
| `compact` | Admitted memory, render it as a compact summary | Short hint injected into PromptContextPack |
| `expanded` | Admitted memory worth full inclusion | Full content injected |
| `local_only` | Memory restricted to this turn's local context | Not propagated to memory dynamics |
| `deferred` | Cannot decide now, kick to reviewer | Logged with `deferred_reason`, not injected |
| `quarantine` | `S1` candidate | Logged with `skip_reason`, not injected, queued for review |
| `blocked` | `S0` candidate | Logged with `skip_reason`, never injected |

`BLOCKED`, `QUARANTINED`, and `DEFERRED` always carry a `skip_reason` for audit. `EXPANDED` and `COMPACT` carry the trace of which factors permitted them.

## Reading a CAC trace

In the workbench, open the CAC traces panel for the last turn. Each row shows:

- Memory ID, source, severity, decision.
- Factor list (the why).
- Whether the candidate was rendered, and how.

From the CLI:

```bash
chronicle decision --subject <subject_id> --kind cac_decision --limit 1
# or from inside the Hermes session:
/relic why
```

`/relic why` prints the CAC trace for the most recent turn in a researcher-readable form.

## Properties to remember

- **No content = no decision.** A CAC trace with `NONE` severity and no content is normal; it means the candidate produced nothing to inject.
- **Disputed is irreversible at the scorer level.** S0 stays S0. To "rehabilitate" a disputed memory, a researcher must explicitly remove the dispute via the workbench correction surface.
- **Quarantine ≠ block.** S1 means "not now, ask a reviewer." S0 means "never."
- **Confidence is metadata.** The 0.7 threshold for `INFERENCE` sources is the only confidence used inside the scorer. The richer per-facet confidence lives elsewhere on the profile.
- **The scorer does not call the LLM.** It is deterministic rule application. Disagreements between scorer outputs are rule disagreements, not stochastic model output.

## When you disagree with a decision

Two paths:

1. **Correct the underlying data.** If the scorer marked something `S1` because the source is `external` and unverified, verify the source via the workbench correction surface. The scorer will re-score on the next turn.
2. **Promote / demote via correction.** Use a `researcher_feedback_event` to mark a specific memory `verified` or `disputed`. The next CAC pass uses the new state.

You cannot edit a CAC trace. Traces are immutable by design. Disagreement produces a new decision on the next turn; it does not rewrite history.
