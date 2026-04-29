# Contributing to Relic

---

## Setup

```bash
git clone https://github.com/yuzushi-dev/relic
cd relic
pip install -e .
```

No external dependencies required for development. The webui and provider SDKs are optional:

```bash
pip install -e ".[webui]"          # FastAPI UI
pip install -e ".[anthropic]"      # Anthropic provider
pip install -e ".[openai]"         # OpenAI provider
```

---

## Running tests

```bash
python -m pytest tests/ -v
```

All 15 tests must pass before submitting a PR. The test suite includes:

| Suite | What it checks |
|---|---|
| `test_demo_runner` | Demo pipeline produces expected outputs |
| `test_demo_webui` | Demo console HTML builds correctly |
| `test_docs_sanitization_markers` | Docs contain no private subject markers |
| `test_hook_sanitization_markers` | Hook TypeScript contains no private IDs or paths |
| `test_python_sanitization_markers` | Python sources contain no forbidden private markers |
| `test_python_depersonalization_markers` | Python sources contain no personal names or inline secrets |
| `test_packaging_scaffold` | pyproject.toml metadata and script entrypoints are correct |
| `test_repo_readiness` | LICENSE, README, and required assets exist |

---

## Project structure

```
src/relic/          Core Python modules (relic_*.py) + cron entrypoints
src/lib/                 Runtime shims: config, log, LLM client, Hermes client
hooks/                   Hermes integration hooks (TypeScript)
  relic-capture/    Message capture + delivery tracking
  relic-bootstrap/  PORTRAIT.md injection into agent sessions
  shared/                Shared TS utilities (SMELT retrieval, last-message)
docs/                    Whitepaper, architecture, configuration, adapter docs
demo/                    Synthetic fixtures and expected demo outputs
tests/                   Sanitization, packaging, demo, and repo-readiness tests
install.py               Arasaka-style TUI installation wizard
```

---

## Adding a new cron

Every cron is a thin entrypoint module in `src/relic/` that imports and calls
`main()` from the corresponding `relic_*.py` module:

```python
# src/relic/my_cron.py
"""Cron entrypoint: relic:my-cron

Invoked as: python -m relic.my_cron
Schedule:   0 5 * * *

One-line description of what this cron does.
"""
from relic.relic_my_module import main

if __name__ == "__main__":
    main()
```

Then add it to `install.py`'s `cron_defs` list with its schedule, and to the cron
reference table in `docs/CONFIGURATION.md`.

---

## LLM adapter

All LLM calls go through `src/lib/provider_llm_client.py`. The interface is a single
method:

```python
def complete(self, prompt: str, **kwargs) -> str: ...
```

To add a new provider, add a `_complete_<provider>(model, prompt)` function and a
dispatch branch in `ProviderLLMClient.complete()`. See `docs/ADAPTERS.md`.

---

## Sanitization rules

This repo ships without any private subject data. All PRs must pass the
sanitization test suite. Things that will fail:

- Real names, Telegram IDs, or account credentials in any source file
- Hardcoded file paths pointing to private home directories
- Inline API keys or tokens
- Database records, portraits, or inbox files containing real behavioral data

The tests look for a specific set of marker patterns defined in
`tests/test_python_sanitization_markers.py` and friends. If you need to add a
new pattern to watch for, add it there.

---

## Submitting a PR

1. Fork the repo and create a branch from `main`
2. Make your changes
3. Run `python -m pytest tests/ -v` - all tests must pass
4. Run `python -m relic.demo_runner --output-dir /tmp/sk_demo` - demo must complete
5. Open a PR against `main` with a description of what and why

There is no formal style guide. Match the style of the file you are editing.
Type annotations are welcome but not required.
