# Security Model

What Relic protects, what it does not protect, and what you must add on top before exposing it.

## Threat model: in scope

- **Accidental leakage** of subject data through workbench exports, chronicle exports, or logs.
- **Researcher mistakes**: running destructive commands without intent (forget, chronicle delete, reset).
- **Cross-subject contamination** at the application layer: data from subject A surfacing in subject B's session.
- **Audit gaps**: an action happening without a corresponding chronicle event.

## Threat model: explicitly OUT of scope

- **Network adversary on localhost.** The workbench and Hermes gateway run on `localhost` by default. No TLS, no auth. Trusted single-machine deployment is assumed.
- **Compromised researcher machine.** If the machine is rooted, Relic cannot help: `relic.db`, `.env` files, and bot tokens are all readable by any process running as the researcher's user.
- **Side-channel inference** about the subject from timing, hardware, or process behaviour.
- **Cloud provider data residency.** If you enable `byterover` or `honcho`, data leaves the machine. That contract is between you and the provider.

If you need any of the out-of-scope properties, wrap Relic in your institution's infrastructure (TLS terminator, IdP, host hardening, encrypted disk).

## At rest

| Asset | Location | Protection |
|---|---|---|
| Subject data, events, decisions | `~/.relic/relic.db` (SQLite) | OS file permissions only. No application-level encryption. |
| Append-only event log | `~/.relic/chronicle.jsonl` (or under chronicle config) | OS file permissions only. |
| Gumi identity files (SOUL.md, MEMORY.md) | `$HERMES_HOME/<profile>/` | OS file permissions only. |
| API keys, bot tokens | `$HERMES_HOME/<profile>/.env`, shell env | Plaintext in `.env`. Never written to `relic.db`. |
| Backups | Wherever you put them | Plaintext. Encrypt at rest if you store off-machine. |

**Recommendation:** put `~/.relic/` and `$HERMES_HOME/` on an encrypted partition (LUKS on Linux, FileVault on macOS). Application-level encryption of `relic.db` is not implemented.

## In transit

| Channel | TLS | Auth | Notes |
|---|---|---|---|
| `localhost` workbench (`relic ui`) | No | None | Loopback only by default. Do not bind to `0.0.0.0` without a reverse proxy. |
| Hermes gateway (`hermes gateway run`) | No | None | Same, local IPC. |
| Ollama (`http://localhost:11434/v1`) | No | None | Loopback. |
| Hindsight cloud backend (if configured) | TLS via provider | API key | Provider-controlled. |
| Byterover / Honcho (if configured) | TLS via provider | API key | Provider-controlled. |
| Telegram delivery | TLS (Telegram Bot API) | Bot token | Telegram-controlled. |
| Gemini media generation | TLS | API key | Google-controlled. |

The exposed Relic surfaces are loopback. Cloud-bound traffic uses the third party's TLS. There is no Relic-side TLS termination.

## Identity and session

- **Researchers:** identified by free-string `researcher_id`. Self-asserted unless you put Relic behind an IdP. See [Multi-Researcher Setup](../guides/multi-researcher.md).
- **Subjects:** identified by `subject_id` (research handle) and the Telegram numeric user ID. No password.
- **Hermes sessions:** identified by a `session_key_hash`. Raw session keys are **never** stored or logged; only hashes appear in the database and in logs (`relic/hermes_client.py:77`). The session key itself lives in process memory and dies with the gateway.
- **Bot tokens:** captured into env vars (`GUMI_<SUBJECT>_BOT_TOKEN`) and into per-subject `.env` files. Rotation is "edit the file, restart the gateway, revoke the old token at BotFather."

## Permissions

A role-based matrix in `relic/ui/permissions.py` gates workbench actions:

| Role | Default permissions |
|---|---|
| `researcher` | read queue, read artefact, read study overview, emit feedback, request recompile, replay trace |
| `subject` | read artefact, emit feedback |
| `viewer` | read queue, read artefact |

`EXPORT_BUNDLE` is **not** granted by default; export is a privileged operation, gate it via your operational layer.

CLI commands trust the operator. There is no per-command authorisation check.

## Audit

Every write operation (correction, forget, chronicle delete, reaper run, replay) emits a chronicle event. Every read on `chronicle query` is itself audited unless `--no-audit` is passed, and `--no-audit` is recorded too (`AccessKind` enum, `relic/chronicle/enums.py:97`).

To answer "what happened on this subject this week":

```bash
chronicle timeline --subject <subject_id> --since 2026-05-11T00:00:00Z
chronicle query --accessor <researcher_id> --limit 200
```

If a write happened without a corresponding event, that is a bug in Relic, file an issue.

## Privacy gates

The runtime enforces:

- **Privacy traces** for every redaction scan and every redaction outcome (`privacy_trace.jsonl`).
- **Consent gates** at memory admission (subject's consent state checked at write time, not just at read).
- **Cross-subject isolation** at the data layer (subject ID required on every query path).
- **Safety signal isolation** from Gumi memory and from subject exports.

Contract tests cover the invariants: `tests/safety/`, `tests/privacy/`, `tests/shared-continuity/`, `tests/ui/`.

## Secrets hygiene

- `.env` files live in `$HERMES_HOME/<profile>/`. Add the directory to your backup encryption.
- Never commit a `.env` file. `.gitignore` covers `~/.relic/` and `~/.hermes/` by default; verify before pushing.
- `check_no_raw_private_data.py` (CI) scans for accidental `*_API_KEY="value"` literals in committed files. Run it locally before any commit.
- Rotate tokens through the source (BotFather `/revoke`, Google Cloud console, provider dashboard) **first**, then update the env var and restart the gateway.

## What to add before exposing Relic

If you plan to run Relic on a shared server or expose the workbench beyond `localhost`:

1. Reverse proxy (nginx, Caddy, Traefik) with **TLS** and **IdP-backed auth**.
2. Encrypted disk for `~/.relic/` and `$HERMES_HOME/`.
3. Firewall blocking all inbound except the proxy.
4. Periodic backup with off-machine encrypted storage.
5. A documented incident response: who is paged, how to rotate, how to revoke.

Do not skip these and call it "production." OSS Relic is researcher-on-a-laptop infrastructure.
