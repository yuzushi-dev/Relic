# Contributing

Relic is in alpha. Contributions are welcome, but the codebase moves quickly and the architecture is still being established. Read this section before opening a pull request.

## Before you start

- Read [Release Status](release-status.md) to understand which modules are stable and which are experimental.
- Read the [Ethics](../ethics/index.md) section. Any contribution that weakens an ethical constraint will not be merged.
- Check [open issues](https://github.com/yuzushi-dev/Relic/issues) to avoid duplicate work.

## Pre-PR checklist

```bash
make lint
pytest -q
python3 scripts/ci/check_json_jsonl.py
python3 scripts/ci/check_no_raw_private_data.py
```

For UI changes:

```bash
cd ui && npm audit --audit-level=moderate && npm run build:static
```

## What not to commit

- Local subject profiles, Hermes profiles, or `.env` files.
- `relic.db` or any database files.
- Generated artifacts, logs, or session data.
- Private research notes or internal documents.
- Real personal data of any kind.

All public fixtures must be synthetic. The CI script `check_no_raw_private_data.py` scans for common patterns.

## Detailed guides

- [Development Setup](development-setup.md) — virtual environment, dependencies, local dev workflow.
- [Testing](testing.md) — test organization, how to run tests, important constraints.
- [Contract Tests](contract-tests.md) — what the behavioral contracts are and how they are verified.
- [Release Status](release-status.md) — stability map, what is safe to depend on.

## License

Relic is AGPL-3.0-or-later. By contributing, you agree your contribution is under the same license.

## Code of Conduct

See [CODE_OF_CONDUCT.md](https://github.com/yuzushi-dev/Relic/blob/main/CODE_OF_CONDUCT.md).
