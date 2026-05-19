# Logging and Observability

How Relic emits log lines, how to capture them, and how to ask useful questions of the result. This is the operational counterpart to [Chronicle](../architecture/chronicle.md) — chronicle is structured **events**, logs are unstructured (or JSON) **runtime** lines.

## Variables

| Variable | Default | Purpose |
|---|---|---|
| `RELIC_LOG_LEVEL` | `INFO` | One of `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `RELIC_LOG_JSON` | `false` | Emit JSON log lines instead of text |
| `RELIC_ECHO_SQL` | `false` | Echo SQL queries to stdout (debugging only — chatty) |

Set per shell:

```bash
export RELIC_LOG_LEVEL=DEBUG
export RELIC_LOG_JSON=true
```

Or per command:

```bash
RELIC_LOG_LEVEL=DEBUG RELIC_LOG_JSON=true relic runtime doctor
```

## Where logs go

- **Foreground commands** (`relic ...`): stdout/stderr of the invoking shell.
- **Hermes gateway** (`hermes gateway run`): stdout/stderr of its terminal. Redirect with `... > ~/.relic/gateway.log 2>&1` or use `nohup`.
- **Backgrounded gateways**: capture to a file you control. There is no built-in log directory.

Relic itself does not rotate logs. Use `logrotate` or your service manager (systemd, supervisord) for production.

## Reading JSON logs

```bash
RELIC_LOG_JSON=true relic runtime status 2>&1 | jq '.'
```

Each line is a JSON object with at least `level`, `event`, `timestamp`, `module`. Common extra fields: `subject_id`, `session_id`, `trace_id`, `error`.

### Recipes

```bash
# All lines for a specific subject:
RELIC_LOG_JSON=true relic runtime status 2>&1 \
  | jq 'select(.subject_id == "subj_demo_01")'

# Errors only, last 100:
tail -1000 ~/.relic/gateway.log | jq 'select(.level == "ERROR")' | tail -100

# Latency of model calls (custom field):
tail -1000 ~/.relic/gateway.log \
  | jq 'select(.event == "llm_call_complete") | {ts: .timestamp, ms: .elapsed_ms}'

# Group by error type:
tail -10000 ~/.relic/gateway.log \
  | jq 'select(.level == "ERROR") | .error' | sort | uniq -c | sort -rn
```

## Logs vs Chronicle: which to use

| Question | Use |
|---|---|
| "What did the gateway do at 09:00 today?" | Logs |
| "Why did the CAC block a memory at 09:00 today?" | Chronicle (`chronicle decision --kind cac_decision`) |
| "What stack trace did this error produce?" | Logs |
| "Was a correction applied?" | Chronicle (`chronicle query --type correction_applied`) |
| "How long did the LLM take?" | Logs (timing metric) |
| "What was the model's output budget?" | Chronicle (model event payload) |

Rule of thumb: chronicle answers *what was decided and why*; logs answer *what executed and how it executed*.

## Levels in practice

- **DEBUG**: every gate decision, every plugin hook entry/exit, full payloads. Use when investigating a bug, then turn off.
- **INFO** (default): gateway lifecycle, subject creation, recompile completion, errors. Safe to leave on in production.
- **WARNING**: degraded but non-fatal — plugin fallback, provider unavailable, retention skip.
- **ERROR**: fatal for the affected operation. Almost always paired with a chronicle event (`category=error`).

Setting `DEBUG` in production fills disk fast. Leave it scoped to investigations.

## Privacy in logs

- Raw session text is **not** logged.
- Bot tokens are **not** logged. The token env var name appears; the value does not.
- Session keys are hashed before any log line that references them (`relic/hermes_client.py`).
- API keys are redacted to `$HOME` substitution in CI marker scans (`scripts/ci/check_no_raw_private_data.py`).

If you find raw text or a real token in a log line, that is a bug — file an issue.

## Logs and the chronicle ledger

The two are intentionally not the same store. Chronicle is durable, structured, auditable, and reaper-aware. Logs are convenient, free-form, and ephemeral by default. Do not point your retention policy at logs.

If you need a permanent record, write a chronicle event from your call site (`relic/chronicle/emitter.py`), not a log line.

## Integrating with your stack

Relic does not expose Prometheus metrics, OpenTelemetry traces, or syslog by default. Patterns that work:

- **Promtail / Vector / Fluent Bit** → tail JSON logs, ship to Loki / Elasticsearch / your sink.
- **OpenTelemetry**: add a logging handler in your operational entry point (`relic ui`, `hermes gateway run` wrapper) and instrument from there. The library is not in core dependencies — you pull it in.
- **Sentry**: import `sentry_sdk` in your wrapper; do not push it into core.

Keep instrumentation outside `relic/` so the OSS distribution stays free of operational deps.

## Quick health snapshot

```bash
relic runtime doctor                                     # plugin + gateway + Ollama + DB
RELIC_LOG_LEVEL=DEBUG relic runtime status 2>&1 | head  # first ~20 startup lines
ollama ps                                                # loaded models
sqlite3 ~/.relic/relic.db "PRAGMA integrity_check;"      # DB integrity
```

If any of these report a problem, see [Troubleshooting](../guides/troubleshooting.md).
