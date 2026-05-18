# Fixtures

Fixtures are synthetic interaction scenarios used in tests and evaluations. They live in `fixtures/` and are versioned with the repository. All data is synthetic; no fixture contains real personal information.

## Available fixtures

### `fixtures/gumi-identity-attractor/`

Tests that Gumi maintains her diegetic identity under various constraint conditions. Contains:
- `soul_original.md` — baseline Gumi identity for the scenario.
- Interaction sequences designed to trigger each of the six collapse patterns (generic assistant, clinical, mood tracker, backend disclosure, over-attached companion, safety shell abandonment).

Used by: `relic/eval/gumi_roleplay.py`, `tests/profiles/test_tool_boundaries.py`.

### `fixtures/gumi-memory/`

Tests for memory candidate admission and recall under correction and privacy constraints. Contains interaction sequences with explicit memory candidates, some eligible and some blocked.

Used by: `relic/gumi_memory/`, related tests.

### `fixtures/gumi-roleplay/`

Roleplay admission controller test scenarios. Each scenario specifies a task type, sensitivity level, and expected `roleplay_level` and `continuity_mode` output.

Used by: `relic/gumi_roleplay/admission.py`, `tests/profiles/`.

### `fixtures/memory-dynamics/`

Decay and reinforcement scenarios: subjects with simulated interaction histories designed to test whether the memory dynamics layer correctly applies decay rates, reinforcement weights, and consolidation behavior.

Used by: `relic/eval/memory_dynamics.py`.

### `fixtures/memory-positive/`

Edge case scenarios for memory with positive valence: warm relational memories that should not be penalized by conservative decay settings.

Used by: `relic/eval/memory_positive.py`.

### `fixtures/ui-validation/`

Fixture data for workbench panel contract tests. Provides static snapshots of model state that test fixtures can render without a live backend.

Used by: `tests/ui/`.

## Creating fixtures

To add a fixture for a new scenario:

1. Create a directory under `fixtures/` with a descriptive name.
2. Add a `README.md` describing: the scenario, what it tests, and which modules use it.
3. Generate synthetic data using `scripts/generate_demo_data.py` as a starting point, or write it manually.
4. Add a test in the appropriate `tests/` subdirectory that uses the fixture.
5. Keep all content synthetic. Run `python3 scripts/ci/check_no_raw_private_data.py` before committing.

## Fixture format

Most fixtures use JSON or JSONL for structured data. Larger scenario fixtures may include markdown files for narrative context (e.g., SOUL.md variants). There is no single schema; each fixture directory defines its own format, which should be documented in its README.

## Generating demo data

```bash
python scripts/generate_demo_data.py --output fixtures/my-scenario/
```

This generates a synthetic subject profile and interaction sequence. Adjust the parameters in the script for different demographic and behavioral profiles.
