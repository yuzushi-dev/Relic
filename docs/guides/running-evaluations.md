# Running Evaluations

Relic includes an evaluation framework for measuring Gumi's behavioral quality against defined contracts and rubrics. Evals run on synthetic fixtures and do not require live subjects.

## What evals measure

The evaluation suite covers:

- **Identity boundary compliance**: does Gumi maintain her diegetic identity under various constraint conditions? Does she collapse into generic assistant, clinical, or mood-tracker behavior?
- **Memory dynamics**: does the memory dynamics layer behave correctly under decay and reinforcement scenarios?
- **Roleplay admission**: does the admission controller assign the correct operational mode for different input types?
- **Provider behavior**: does each external memory provider produce candidates that meet the admission criteria?
- **Safety signal handling**: are safety signals kept researcher-facing and excluded from Gumi's outputs?

## Running the eval harness

```bash
python scripts/eval_run.py
```

This runs the full eval suite against the fixtures in `fixtures/`. The output includes per-metric scores, aggregate summaries, and flagged cases.

For a specific eval module:

```bash
python scripts/eval_run.py --module gumi_roleplay
python scripts/eval_run.py --module memory_dynamics
python scripts/eval_run.py --module gumi_provider
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

To run an ablation (disable a component and measure the effect on metrics):

```bash
python scripts/eval_run.py --ablate memory_dynamics
python scripts/eval_run.py --ablate cac
```

Ablation results are stored in `relic/eval/ablation.py` format and can be compared against baseline runs.

## Baselines

Baselines capture the expected performance on the current fixture set. Before making changes that affect evaluation behavior, record a baseline:

```bash
python scripts/eval_run.py --record-baseline
```

After your changes:

```bash
python scripts/eval_run.py --compare-baseline
```

This reports which metrics improved, regressed, or were unchanged.

## Replication bundles in eval

The eval harness can generate a replication bundle alongside an eval run. This allows independent verification of eval results:

```bash
python scripts/eval_run.py --output-bundle ./eval_bundle/
```

See [Artifact Lifecycle](../architecture/artifact-lifecycle.md) for more on replication bundles.

## Debug bundles

For failed cases, a debug bundle can be produced showing the full pipeline trace:

```bash
python -m relic.eval.debug_bundle --case-id <case_id> --output ./debug/
```

Debug bundles are large and should not be committed to the repository.
