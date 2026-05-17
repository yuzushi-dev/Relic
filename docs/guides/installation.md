# Installation

## Requirements

- Python 3.10 or later
- pip
- Ollama (required for local LLM inference during bootstrap and eval)
- Hermes (required for live delivery; optional for offline research use)

## Install Relic

```bash
git clone https://github.com/yuzushi-dev/Relic
cd Relic
pip install -e .
```

For development (includes test dependencies):

```bash
pip install -e ".[dev]"
```

## First-run setup

```bash
relic init
```

`relic init` is an interactive wizard. It checks for Ollama and Hermes, installs them if requested, configures the Hermes model backend, and sets up local directories. Run it once before creating subjects.

If you want to verify your environment without going through the full interactive setup:

```bash
relic setup --check-only
```

## Ollama

Relic uses Ollama for local inference during bootstrap data generation, eval, and profile compilation. If Ollama is not installed, `relic init` will offer to install it via the official installer script.

After installation, `relic init` will offer to pull a starter model. The default is `qwen2.5:32b-instruct-q4_K_M` (configurable). For machines with limited VRAM, a smaller model like `llama3.2:3b` works for basic use, though eval quality will be lower.

## Hermes

Hermes is the agent runtime that Gumi runs inside. It is required for live delivery to subjects but not for offline research workflows (bootstrap, eval, profile inspection).

If Hermes is not installed, `relic init` will offer to install it. After installation, Relic will configure Hermes to use Ollama as the model backend with the settings from `relic/hermes_runtime.py`.

Manual Hermes configuration:

```bash
hermes config set model.provider custom
hermes config set model.base_url http://localhost:11434/v1
hermes config set model.default qwen2.5:32b-instruct-q4_K_M
hermes config set model.context_length 65536
hermes config set agent.tool_use_enforcement true
hermes config set approvals.mode manual
hermes config set privacy.redact_pii true
```

## Environment variables

See [Configuration](../reference/configuration.md) for the full list. The most common ones:

| Variable | Default | Description |
|---|---|---|
| `RELIC_DB_PATH` | `~/.relic/relic.db` | Path to the SQLite database |
| `RELIC_LOG_LEVEL` | `INFO` | Log level |
| `RELIC_LOG_JSON` | `false` | JSON-formatted logs |
| `RELIC_ECHO_SQL` | `false` | Echo SQL queries (debugging) |

## Verifying the installation

```bash
relic --version
relic setup --check-only
```

The `--check-only` flag reports the status of each dependency without making any changes. Expected output on a working installation:

```
[ok] Python: 3.11.x
[ok] Ollama: /usr/local/bin/ollama
[ok] Hermes: /usr/local/bin/hermes
[ok] relic.db: ~/.relic/relic.db
```
