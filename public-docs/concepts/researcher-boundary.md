# Researcher Boundary

The researcher UI can read a great deal of information about the system's internal state. It cannot directly change that state. This boundary is not a UI convention; it is a hard architectural constraint enforced in code and tests.

## What the researcher can read

- Review queues: pending items that need researcher attention
- Redacted evidence projections: what evidence is available, with PII removed
- Hypotheses and trait estimates with confidence scores
- Runtime hints (what is currently being injected into Gumi's context)
- CAC traces: how hints were scored and filtered for a given turn
- Privacy traces: what redactions and checks were applied
- Correction traces: history of corrections and their propagation
- Artifact diffs: what changed between compiler runs
- Eval summaries: aggregate metrics across subjects and sessions
- Replication bundle status

## What the researcher can write

Two things only:

1. `researcher_feedback_event`: a structured correction, annotation, or evaluation judgment.
2. Replay request: a request to replay a session with different parameters for evaluation.

That is the complete write surface. There is no direct write path to compiled artifacts, runtime packs, CAC traces, privacy traces, or lab outputs.

## Why this constraint exists

Allowing direct mutation of compiled artifacts would break the provenance chain. An artifact that has been manually edited without going through the compiler cannot be verified against the evidence that produced it. It also makes the compilation pipeline non-deterministic: the same inputs might produce different results depending on what a researcher has edited directly.

The feedback-event-first approach keeps the pipeline auditable and replayable. Every change to the model is traceable to a specific feedback event with a timestamp and a rationale.

## The full path from UI action to runtime change

```
Researcher submits a correction via the workbench
  -> researcher_feedback_event written to relic.db
  -> feedback processor applies the correction
  -> propagation marks affected artifacts stale
  -> compiler rerun scheduled
  -> compiler reruns, producing updated artifacts
  -> updated artifacts written to relic.db
  -> CAC uses updated artifacts at next turn
```

A UI action that claims to change runtime behavior without this sequence is a bug, not a feature. The test `tests/ui/test_no_direct_artifact_write.py` verifies that direct writes are blocked.

## Scope adjustments

Researchers can adjust the scope of what the system models for a specific subject (for example, disabling a facet cluster or reducing the confidence cap on a category of inference). Scope changes go through `relic/profile/cli.py` and trigger a recompile. See `tests/ui/test_scope_adjustment_recompile.py`.

## Permissions

The workbench permission model is defined in `relic/ui/permissions.py`. Researcher permissions are scoped to specific studies and subjects; a researcher working on one study cannot access data from another.
