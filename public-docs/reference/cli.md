# CLI Reference

The `relic` command is the primary interface for setup, subject management, and runtime operations.

## `relic init`

First-run wizard. Installs and configures Ollama and Hermes. Run once before creating subjects.

```bash
relic init
```

Checks for Ollama and Hermes, offers to install them, configures Hermes to use Ollama as the model backend, and initializes the local `~/.relic/` directory.

## `relic setup`

Install or verify runtime dependencies without creating subjects.

```bash
relic setup [--check-only]
```

| Flag | Description |
|---|---|
| `--check-only` | Report dependency status without making any changes |

## `relic subject`

Manage subjects.

### `relic subject create`

Create a subject profile and Gumi diegetic profile through the bootstrap TUI.

```bash
relic subject create [--subject-id ID] [--experiment-id ID]
```

| Flag | Description |
|---|---|
| `--subject-id` | Subject identifier. Auto-generated if not specified. |
| `--experiment-id` | Experiment identifier for grouping subjects. |

### `relic subject show`

Show a subject's runtime status. Does not display raw session keys.

```bash
relic subject show <subject_id>
```

Output includes: active consent records, compiled artifact count, Hermes profile hash, correction count, pause state.

### `relic subject reprovision`

Re-run provisioning for an active subject with missing or stale artifacts.

```bash
relic subject reprovision <subject_id>
```

Use this when artifacts are missing after a system update, or when a recompile has not run automatically.

## `relic runtime`

Hermes runtime operations.

### `relic runtime status`

Show Hermes runtime status: connectivity, active plugin list, model backend.

```bash
relic runtime status
```

### `relic runtime doctor`

Run a full runtime diagnostic. Checks Hermes connectivity, plugin registration, database access, Ollama model availability, and delivery channel configuration.

```bash
relic runtime doctor
```

### `relic runtime allowlist`

Manage the delivery allowlist for a subject. Subjects must be on the allowlist to receive proactive messages.

#### `relic runtime allowlist add`

```bash
relic runtime allowlist add <subject_id> \
  --platform <platform> \
  --target <target> \
  [--expires <iso_timestamp>]
```

| Flag | Required | Description |
|---|---|---|
| `--platform` | Yes | Delivery platform: `telegram`, `whatsapp` |
| `--target` | Yes | Target identifier, e.g., `telegram:123456789` |
| `--expires` | No | ISO 8601 expiry timestamp |

#### `relic runtime allowlist list`

```bash
relic runtime allowlist list <subject_id> [--platform <platform>]
```

#### `relic runtime allowlist remove`

```bash
relic runtime allowlist remove <subject_id> \
  --platform <platform> \
  --target <target>
```

## `relic ui`

Launch the researcher workbench.

```bash
relic ui [--port PORT]
```

| Flag | Default | Description |
|---|---|---|
| `--port` | 8080 | Port for the web interface |

## `relic-profile`

A separate entry point for profile-level operations. Used internally and in bootstrap scripts.

```bash
relic-profile --help
```
