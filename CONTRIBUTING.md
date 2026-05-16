# Contributing

See [docs/contributing/](docs/contributing/index.md) for the full contributing guide.

## Pre-PR checklist

- Run `make lint`.
- Run `pytest -q`.
- Run `python3 scripts/ci/check_json_jsonl.py`.
- Run `python3 scripts/ci/check_no_raw_private_data.py`.
- For UI changes, run `cd ui && npm audit --audit-level=moderate && npm run build:static`.

Keep public fixtures synthetic. Do not commit local subject profiles, Hermes profiles, `.env` files, databases, logs, generated artifacts, or private research notes.

Relic is AGPL-3.0-or-later. By contributing, you agree that your contribution is provided under the same license.
