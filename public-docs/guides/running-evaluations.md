# Running Evaluations

Relic includes an evaluation framework for measuring Gumi's behavioral quality against defined contracts and rubrics. Evals run on synthetic fixtures and do not require live subjects.

## What evals measure

The currently wired `scripts/eval_run.py` CLI covers:

- **Identity boundary compliance**: does Gumi maintain her diegetic identity under various constraint conditions? Does she collapse into generic assistant, clinical, or mood-tracker behavior?
- **Roleplay admission and PromptContextPack completeness**: does the roleplay fixture suite exercise the expected R1-R10 families?
- **Memory-positive usefulness**: do synthetic MP1-MP8 fixtures produce a passing A5 memory-positive score?
- **Safety signal handling contracts**: are safety signals kept researcher-facing in the fixture-backed tests?

## Running the eval harness

```bash
python scripts/eval_run.py
```

This runs the wired fixture-backed modules against `fixtures/gumi-roleplay/` and `fixtures/memory-positive/`. The output includes release-gate status, aggregate summaries, and scenario counts.

For a specific eval module:

```bash
python scripts/eval_run.py --module gumi_roleplay
python scripts/eval_run.py --module memory_positive
```

## Fixtures

Fixtures are synthetic interaction scenarios stored in `fixtures/`. Each fixture directory contains:
- A README describing the scenario and what it is testing.
- Input data representing a subject profile and interaction sequence.
- Expected output annotations.

Fixtures are versioned. Do not modify them directly in a working branch; create new fixtures for new scenarios.

To list available fixtures:

```bash
python -m relic.eval.fixtures list
```

## Metrics

The core metrics are defined in `relic/eval/metrics.py`. Key metrics for Gumi evaluation:

| Metric | Description |
|---|---|
| `mode_switch_accuracy` | Correct roleplay operational mode selected |
| `relational_dose` | Appropriate level of relational presence for context |
| `dependency_boundary_trigger_rate` | Correct activation of dependency warnings |
| `disclosure_when_reality_challenged` | Correct handling of questions about Gumi's nature |
| `roleplay_suppression_correctness` | Correct suppression of persona in high-stakes contexts |
| `persona_intrusion_cost` | Penalty for persona elements appearing in non-roleplay contexts |
| `clinicalization_rate` | Frequency of forbidden clinical terms in output |

## Ablation studies

The repository contains ablation helpers under `relic/eval/ablation.py`, but ablation is not currently wired into `scripts/eval_run.py`. Use module-specific tests or extend the CLI before treating ablation output as part of the artifact contract.


## Baselines

Baseline helpers exist under `relic/eval/baselines.py`, but `scripts/eval_run.py` does not currently expose `--record-baseline` or `--compare-baseline`. Generate baselines through the Python API or add CLI support before documenting a baseline run as artifact evidence.

## Replication bundles in eval

Replication bundles are built through `relic.eval.replication_bundle` and `relic.replication.bundle`. `scripts/eval_run.py` does not currently expose `--output-bundle`.

See [Artifact Lifecycle](../architecture/artifact-lifecycle.md) for more on replication bundles.

## Debug bundles

For failed cases, a debug bundle can be produced showing the full pipeline trace:

```bash
python -m relic.eval.debug_bundle --case-id <case_id> --output ./debug/
```

Debug bundles are large and should not be committed to the repository.
