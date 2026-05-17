# Artifact Lifecycle

A Relic artifact is a compiled, versioned, auditable piece of runtime guidance. Artifacts are not written by hand; they are produced by the compiler from the current state of the subject profile, evidence, and corrections.

## What artifacts are

Artifacts represent what the system believes about the subject at a specific point in time, expressed in a form that can be injected into Gumi's runtime context. Examples include trait summaries, behavioral hints, and contextual guidance notes.

Each artifact has:
- A content hash that changes when the content changes.
- A lineage reference to the evidence that produced it.
- A policy snapshot ID identifying the policy that was active at compilation time.
- A staleness flag that is set when corrections invalidate the artifact.
- A validity period (some artifacts expire if not updated by new evidence).

## Compilation pipeline

```
Subject profile + evidence + corrections + policy snapshot
  -> relic/compiler/pipeline.py
  -> passes (privacy gate, scope filter, lineage attach, confidence cap)
  -> versioned artifacts written to relic.db
  -> replication bundle written (optional)
```

The pipeline is deterministic: the same inputs produce the same artifacts. This is required for the replication bundle to work. Non-determinism in the pipeline is a bug.

The passes are defined in `relic/compiler/passes.py`. Each pass transforms the artifact candidates; none of them write to Hermes memory or modify the subject profile directly.

## Staleness

An artifact becomes stale when:
- A correction is applied that affects the evidence underlying it.
- The policy snapshot it was compiled against is superseded.
- The subject's consent state changes in a way that affects what can be compiled.

Stale artifacts are not used. The CAC checks artifact freshness before inclusion in the PromptContextPack. A turn where all relevant artifacts are stale will result in reduced context (Gumi operates with less personalization) until a recompile runs.

## Recompile triggers

A recompile is triggered by:
- A `researcher_feedback_event` that marks artifacts stale.
- A manual `relic subject reprovision <subject_id>` command.
- A policy update that invalidates the current snapshot.

The recompile runs through the full pipeline. It does not attempt partial updates; it produces a fresh set of artifacts from the current state.

## Replication bundles

The compiler can produce a replication bundle alongside a compilation run. A bundle contains:
- Input data snapshot (evidence, corrections, bootstrap data).
- Policy snapshot.
- Random seeds used in any stochastic steps.
- Compiler version.

A bundle allows an independent replication of the compilation result. This is important for research reproducibility: any claim about what Relic produced for a subject can be verified by running the compiler against the bundle.

See `relic/compiler/replication.py` and `relic/replication/bundle.py`.

## Registry

Compiled artifacts are tracked in the artifact registry (`relic/artifacts/registry.py`). The registry provides checksums for integrity verification (`relic/artifacts/checksums.py`) and type definitions for all supported artifact types (`relic/artifacts/types.py`).

## What artifacts are not

Artifacts are not stored in Hermes MEMORY.md or USER.md. They are not persistent system prompt content. They are injected as ephemeral per-turn context by the `pre_llm_call` hook and discarded after the turn. This means a stale artifact stops influencing Gumi as soon as it is marked stale — there is no residual in a persistent prompt.
