# `chronicle` CLI

Query interface for the Relic event ledger. Read-only by default; write operations (export, delete, reaper) are clearly marked. Every read is recorded as an audit event unless `--no-audit` is passed (which itself is audited).

```bash
chronicle --help
```

## Common filters

Most subcommands accept some combination of `--trace`, `--session`, `--subject`, `--since`, `--until`, and `--limit`. `--since` / `--until` take ISO 8601 timestamps, e.g. `2026-05-01T00:00:00Z`.

## `chronicle query`

Query raw events.

```bash
chronicle query [--trace ID] [--session ID] [--subject ID] [--type EVENT_TYPE]
                [--category CATEGORY] [--module PREFIX]
                [--since TS] [--until TS] [--limit N]
                [--format json|jsonl|table]
                [--accessor STR] [--no-audit]
```

| Flag | Description |
|---|---|
| `--trace` | Filter by `trace_id`. |
| `--session` | Filter by `session_id`. |
| `--subject` | Filter by `subject_id`. |
| `--type` | Filter by `event_type`. |
| `--category` | Filter by `event_category`. |
| `--module` | Filter by `source_module` prefix. |
| `--limit` | Default 100. |
| `--format` | `json`, `jsonl`, or `table` (default). |
| `--accessor` | Identity recorded in the audit event. Default `researcher:cli`. |
| `--no-audit` | Skip the audit event (itself audited). |

## `chronicle timeline`

Show an event timeline grouped by trace or by time.

```bash
chronicle timeline [--trace ID] [--session ID] [--subject ID]
                   [--since TS] [--until TS] [--limit N]
                   [--group-by trace|time]
```

Default `--limit` is 200, `--group-by` is `time`.

## `chronicle decision`

Query decision events (cron decisions, admission rulings, etc.).

```bash
chronicle decision [--trace ID] [--session ID] [--subject ID]
                   [--kind DECISION_KIND] [--limit N] [--format json|table]
```

## `chronicle snapshot`

Query state snapshots.

```bash
chronicle snapshot [--subject ID] [--type SNAPSHOT_TYPE] [--scope SCOPE]
                   [--limit N] [--format json|table]
```

## `chronicle provenance`

Show artifact provenance.

```bash
chronicle provenance --artifact ID
                     [--direction ancestors|descendants|verify]
                     [--depth N]
```

| Flag | Description |
|---|---|
| `--artifact` | Required. Artifact identifier. |
| `--direction` | `ancestors` (default), `descendants`, or `verify`. |
| `--depth` | Default 3. |

## `chronicle stats`

Aggregate statistics over events.

```bash
chronicle stats [--subject ID] [--since TS] [--format json|table]
```

## `chronicle export`

Export subject data as `tar.gz`. The exported subject payload is written to the requested file, and the export access itself is recorded in `chronicle_access_log`.

```bash
chronicle export --subject <id> --output PATH [--accessor STR]
```

## `chronicle delete`

!!! danger "Destructive"
    Removes event data for a subject (GDPR scope).

```bash
chronicle delete --subject <id> [--dry-run] [--cascade]
                 [--format json|table] [--accessor STR]
```

| Flag | Description |
|---|---|
| `--dry-run` | Show what would be deleted. |
| `--cascade` | Also delete Chronicle provenance edges connected to the subject's events, decisions, or snapshots. |

Always run with `--dry-run` first.

## `chronicle reaper`

Run the retention reaper. Enforces retention policies; only data past its retention window is removed.

```bash
chronicle reaper [--dry-run] [--policy NAME] [--format json|table]
```

## `chronicle verify`

Verify JSONL append-log visibility. The current command scans journal files and reports entry counts; SQLite repair is not implemented in this artifact.

```bash
chronicle verify
```
