# CLI Reference

Relic ships three entry points. Most researchers only need `relic`.

| Command | What it does | Reference |
|---|---|---|
| `relic` | Setup, subject lifecycle, runtime, workbench | This page |
| `relic-profile` | Lower-level profile, Hermes, media, cron management | [Profile CLI](relic-profile-cli.md) |
| `chronicle` | Query the event ledger (audit, provenance, stats) | [Chronicle CLI](chronicle-cli.md) |

## `relic`

The primary interface for setup, subject management, and runtime operations.

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

### `relic subject forget`

!!! danger "Irreversible"
    Hard delete (GDPR Art. 17). Permanently erases all subject data on this machine.

```bash
relic subject forget <subject_id> [--yes]
```

| Flag | Description |
|---|---|
| `--yes` | Skip interactive confirmation. For automation only. |

Run `relic subject export` first if you need to keep anything.

## `relic checkin`

Manage subject check-ins (longitudinal facet updates from periodic structured prompts).

### `relic checkin update-facets`

Process pending check-in replies for a subject and update `subject_baseline.json`.

```bash
relic checkin update-facets --subject-id <id> [--dry-run] [--relic-home PATH]
```

| Flag | Description |
|---|---|
| `--subject-id` | Required. Subject identifier. |
| `--dry-run` | Show what would change without writing. |
| `--relic-home` | Override `RELIC_HOME`. |

### `relic checkin status`

Show pending and processed exchange counts for a subject.

```bash
relic checkin status --subject-id <id> [--relic-home PATH]
```

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

## See also

- [`relic-profile`](relic-profile-cli.md) — multi-subject registry, Hermes/Telegram provisioning, Gumi media, cron specs.
- [`chronicle`](chronicle-cli.md) — query the event ledger (audit, provenance, retention).
