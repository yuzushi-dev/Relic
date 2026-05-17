# Consent and Control

Subjects have the right to know what data is held about them, to correct it, to pause processing, and to delete it. These are not optional features; they are implemented as first-class operations in `relic/control/`.

## Consent types

Relic tracks four consent types:

| Type | Scope | Description |
|---|---|---|
| `memory_storage` | Permanent or session | Whether interaction data may be stored |
| `analytics` | Permanent or session | Whether data may be used in aggregate analysis |
| `roleplay` | Session | Whether the roleplay frame is active |
| `data_sharing` | Permanent | Whether data may be shared with third parties |

Consent is recorded per session or permanently, depending on the scope. Revocation takes effect immediately. The `ConsentManager` in `relic/control/consent.py` handles recording, checking, and revocation.

## Pause

A subject can pause all proactive behavior from Gumi without deleting their profile. The pause command (`relic subject pause <subject_id>`) disables runtime guidance injection and cron-scheduled outreach. Gumi can still respond to incoming messages in a minimal mode.

This is useful when a subject is in a sensitive period and does not want the system to act on its current model of them. The pause state is respected by the CAC and all cron tasks.

## Export

Export produces a redacted bundle of the subject's data: events, confirmed continuity markers, artifacts, and consent records. Raw session text is redacted by default; unredacted export requires explicit opt-in.

Safety signals (researcher-only data from `relic/safety/`) are excluded from subject exports. The export manifest includes a `redaction_status` field confirming what was applied.

```bash
relic subject export <subject_id> --format json --output ./export/
```

See `relic/vault/export.py` for the implementation and `relic/control/export.py` for the control layer.

## Deletion

Delete removes data from the canonical database and creates an audit event. It is irreversible. Before deleting, run a dry-run to see what will be affected:

```bash
relic subject delete <subject_id> --scope all --dry-run
relic subject delete <subject_id> --scope all
```

Deletion scopes:

| Scope | What is removed |
|---|---|
| `prompt` | A specific prompt and its derived artifacts |
| `session` | All data from a session |
| `all` | All data for the subject |

Replication bundles and eval cases derived from deleted sessions are invalidated, not silently left intact. See `relic/control/delete.py`.

## Forget

Forget removes data from Gumi's recall without deleting it from storage. This supports regulatory contexts where audit data must be retained but the subject no longer wants the agent to remember specific information. An audit event is created on forget. The forget operation is subject-scoped; it cannot affect data belonging to another subject.

## Incident reporting

`relic/control/incident.py` supports logging and escalating incidents involving potential boundary violations or unexpected system behavior. Incidents are researcher-facing only.
