# Development Setup

## Clone and install

```bash
git clone https://github.com/yuzushi-dev/Relic
cd Relic
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

The `[dev]` extra includes pytest, ruff, and other development dependencies defined in `pyproject.toml`.

## Verifying the setup

```bash
relic --version
pytest -q --co -q    # List tests without running them
make lint
```

If `relic` is not found after install, make sure the virtual environment is activated and try `python -m relic --version`.

## Project layout

```
relic/              Core Python package
tests/              Test suite
  ui/               Researcher UI contract tests
  shared-continuity/ Shared continuity memory tests
  safety/           Safety signal tests
  profile/          Subject profile tests
  vault/            Export/import tests
  skills/           Skill metadata tests
fixtures/           Synthetic test data
scripts/
  ci/               CI validation scripts
  dev/              Developer utilities
  hermes/           Hermes-specific scripts
configs/hermes/     Example plugin configurations
contracts/          Behavioral contracts (markdown)
```

## Running the test suite

See [Testing](testing.md) for full instructions. Short version:

```bash
pytest -q
```

## Making changes

Branch from `main`. Keep PRs focused. A PR that fixes a bug should not include unrelated cleanup. The PR template at `.github/pull_request_template.md` lists what to include.

## Linting

```bash
make lint
```

Relic uses ruff for linting. The configuration is in `pyproject.toml`. The lint rules are intentionally not strict in alpha; some warnings will be present. Do not disable rules to pass CI — fix the underlying issue.

## Environment variables for development

For local testing against a separate database:

```bash
export RELIC_DB_PATH=/tmp/relic-dev.db
export RELIC_LOG_LEVEL=DEBUG
export RELIC_ECHO_SQL=true
```

Do not set `RELIC_DB_PATH` to your live database when running tests — the test suite creates and modifies data.
