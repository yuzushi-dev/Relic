# Installation

If you have never installed a Python project from source, work through the **Prerequisites** section first. Otherwise jump straight to [Install Relic](#install-relic).

!!! warning "Supported platforms"
    Relic is developed and tested on **Linux** and **macOS**. The Hermes and Ollama installers used by `relic init` are `curl | bash` scripts that do not run on native Windows. **Windows users must use [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install)** (Ubuntu recommended) and run all commands inside the WSL shell.

## Requirements

- Python 3.10 or later
- pip
- Ollama (required for local LLM inference during bootstrap and eval)
- Hermes (required for live delivery; optional for offline research use)

## Prerequisites

### Python

=== "Linux"

    Most distributions ship Python 3.10+. Check with `python3 --version`. If it is missing or too old:

    ```bash
    # Debian / Ubuntu
    sudo apt update && sudo apt install python3 python3-pip python3-venv

    # Fedora
    sudo dnf install python3 python3-pip
    ```

=== "macOS"

    Use Homebrew (recommended):

    ```bash
    brew install python
    ```

    Or install from [python.org](https://www.python.org/downloads/).

    **Apple Silicon (M1/M2/M3/M4):** Ollama runs natively on ARM and uses the Metal backend. Pull ARM-tagged models when available (most modern Ollama tags include both architectures). Expect noticeably better performance than Intel for the default `qwen2.5:32b` model.

    **Intel Mac:** works, but slower. Consider `qwen2.5:14b` instead of `32b` if interaction feels sluggish.

=== "Windows (WSL2)"

    Open a WSL Ubuntu shell, then follow the Linux instructions. Native Windows is unsupported; do **not** install Python in PowerShell for Relic.

### Ollama

`relic init` can install Ollama for you on Linux and macOS. If you prefer to install it manually or are on Windows:

- Visit [ollama.com/download](https://ollama.com/download) and run the platform installer.
- After install, run `ollama --version` to confirm it is on PATH.

Pull a starter model:

```bash
ollama pull qwen2.5:32b-instruct-q4_K_M    # default, needs ~20 GB disk and ~24 GB RAM
# or, for low-spec machines:
ollama pull llama3.2:3b                    # ~2 GB disk, runs on 8 GB RAM
```

### Hermes (only if you plan to deliver messages to a subject)

`relic init` can install Hermes for you on Linux and macOS. Manual install:

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
```

You can skip Hermes if you only want to bootstrap subjects and use the workbench offline.

### Optional: Node.js for the workbench

The researcher workbench is built from the `ui/` directory. If you want to rebuild it locally, install [Node.js 20+](https://nodejs.org/). For most users the prebuilt assets in the repository are sufficient.

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
