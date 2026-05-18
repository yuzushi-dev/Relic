# Configuration

Relic is configured through environment variables. There is no configuration file; settings are read at startup by `relic/config.py`.

## Core Relic variables

| Variable | Default | Description |
|---|---|---|
| `RELIC_DB_PATH` | `~/.relic/relic.db` | Path to the SQLite database |
| `RELIC_LOG_LEVEL` | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `RELIC_LOG_JSON` | `false` | Emit JSON-formatted log lines |
| `RELIC_ECHO_SQL` | `false` | Echo SQL queries to stdout (debugging only) |

## Hermes runtime variables

These control how Relic configures Hermes. They are read by `relic/hermes_runtime.py`.

| Variable | Default | Description |
|---|---|---|
| `HERMES_HOME` | `~/.hermes` | Hermes home directory |

The Hermes model backend is configured via `hermes config set` commands, not environment variables. See [Installation](../guides/installation.md) for the recommended settings.

## Memory provider variables

Each external memory provider has its own configuration. Set these based on which provider is active in your plugin config.

### Hindsight (default local provider)

| Variable | Default | Description |
|---|---|---|
| `HINDSIGHT_PROVIDER` | `ollama` | Inference backend for Hindsight |
| `HINDSIGHT_BASE_URL` | `http://localhost:11434/v1` | Ollama API URL |

### Other providers (Byterover, Holographic, Honcho)

These providers require API keys and configuration specific to each service. Refer to their respective documentation. Keys must be set as environment variables; they are never stored in `relic.db`.

## Defaults reference

Default values are defined in `relic/hermes_runtime.py`:

```python
HERMES_OLLAMA_BASE_URL = "http://localhost:11434/v1"
HERMES_CONTEXT_LENGTH = 65536
HERMES_DEFAULT_MODEL = "qwen2.5:32b-instruct-q4_K_M"
HINDSIGHT_DEFAULT_PROVIDER = "ollama"
```

## Schema version

The current database schema version is tracked in `RuntimeConfig.schema_version`. Migrations are applied automatically on startup when the schema version changes. Do not modify `relic.db` directly.
