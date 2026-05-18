# Testing

## Running tests

```bash
pytest -q
```

!!! warning "Run tests sequentially"
    Do not use pytest-xdist or other parallelization plugins on this project. Tests share database state and parallel execution causes interference and crashes.

For a specific subdirectory:

```bash
pytest tests/ui/ -q
pytest tests/shared-continuity/ -q
pytest tests/safety/ -q
```

For a specific file:

```bash
pytest tests/ui/test_no_direct_artifact_write.py -v
```

## Test organization

Tests are organized by domain, not by module:

| Directory | What it tests |
|---|---|
| `tests/ui/` | Researcher UI contracts: what the workbench can read and write |
| `tests/shared-continuity/` | Shared continuity memory: markers, recall, corrections, clinicalization guard |
| `tests/safety/` | Safety signal handling, escalation notifier |
| `tests/profile/` | Subject profile: bootstrap, inferred fields, corrections, versioning |
| `tests/vault/` | Export, import, deletion |
| `tests/skills/` | Skill metadata validation |
| `tests/profiles/` | Tool boundary and permission tests |

Root-level tests (`tests/test_*.py`) cover smoke tests, CLI setup, DB schema, and Makefile targets.

## CI scripts

Run these before every PR:

```bash
python3 scripts/ci/check_json_jsonl.py       # validates all JSON/JSONL files
python3 scripts/ci/check_no_raw_private_data.py  # scans for sensitive data patterns
```

These run in CI but catching them locally saves time.

## Writing tests

Tests for new features should be added alongside the feature. The most important coverage areas:

- **Boundary enforcement**: does the system correctly block what it should block? (Cross-subject leakage, direct artifact writes, unsafe exports, etc.)
- **Contract compliance**: does new code meet the behavioral contracts in `contracts/`?
- **Correction propagation**: if you add a new artifact type, does it get correctly invalidated when a correction propagates?

Avoid mocking the database in tests. Use a test database with the actual schema instead. See `tests/shared-continuity/conftest.py` and `tests/vault/conftest.py` for the pattern.

## Fixtures in tests

Tests that need subject data should use fixtures from `fixtures/` or create minimal synthetic data inline. Do not create tests that depend on a live `~/.relic/relic.db`.

## What is not covered yet

Some areas have sparse coverage in the current alpha:

- End-to-end integration with a live Hermes instance.
- Full compiler pipeline with real LLM outputs.
- Multi-subject concurrent access patterns.

These are known gaps. If you add coverage in these areas, it is welcome.
