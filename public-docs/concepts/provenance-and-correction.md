# Provenance and Correction

Every compiled artifact in Relic can be traced back to the evidence that produced it. Every correction propagates through the pipeline and invalidates all downstream artifacts derived from the corrected data. These two properties, provenance and correction, are what make the model inspectable and contestable.

## Provenance

When the compiler produces a runtime artifact (a hint, a trait summary, a context fragment), it attaches source references identifying which observations and evidence items contributed to it. This lineage is stored alongside the artifact in `relic.db`.

The purpose is to make the artifact auditable. A researcher looking at a hint injected into Gumi's context can ask: what evidence produced this? Where did that evidence come from? When was it collected? Was it self-report or system inference?

Provenance is attached at the compilation step in `relic/compiler/lineage.py`. Artifacts without valid lineage are treated as stale.

## Why provenance matters in practice

Without provenance, a correction is difficult to apply correctly. If a hint reads "prefers direct communication" but the researcher cannot see what produced it, they cannot know whether it came from an explicitly corrected belief, a single ambiguous observation, or a high-confidence repeated signal. The appropriate response to each is different.

With provenance, corrections can be targeted. A researcher can correct a specific observation, propagate that correction through the lineage, and see exactly which artifacts are invalidated.

## Corrections

Corrections are the primary mechanism by which the model is updated in response to researcher judgment or subject input. A correction:

1. Targets a specific fact, trait, or inference in the model.
2. Is recorded as a `researcher_feedback_event` through the workbench or the API: it cannot be applied by directly mutating a compiled artifact.
3. Propagates to all artifacts derived from the corrected item, marking them stale.
4. Triggers a compiler rerun for the affected subject.
5. Produces updated artifacts after the rerun, which are then available for use at the next turn.

Corrections are authoritative. A corrected fact cannot be reactivated by graph neighbors, memory dynamics decay rehearsal, or any other automated mechanism. See `relic/correction/propagation.py`.

## The correction workflow in sequence

```
Researcher identifies an incorrect trait or inference
  -> Records correction via researcher_feedback_event
  -> relic/correction/propagation.py marks affected artifacts stale
  -> Compiler rerun scheduled
  -> relic/compiler/pipeline.py reruns with correction applied
  -> Updated artifacts written to relic.db
  -> CAC uses new artifacts at next turn
```

The sequence is enforced: there is no shortcut that lets a correction bypass the compiler and write directly to runtime artifacts. This is tested in `tests/ui/test_no_direct_artifact_write.py`.

## Replication bundles

For research reproducibility, the compiler can produce a replication bundle: a snapshot of the input data, correction state, policy snapshot, and random seeds that were used to produce a given set of artifacts. A bundle allows independent replication of the compilation result. See `relic/compiler/replication.py` and `relic/replication/bundle.py`.
