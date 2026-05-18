# Export and Deletion

Subjects can export their data, pause the system, forget specific memories, and delete their data entirely. These operations are first-class in the system, not afterthoughts.

## Export

Export produces a bundle of the subject's data in a portable format. By default, content is redacted — raw session text is replaced with a redaction marker, and safety signals are excluded.

```bash
relic subject export <subject_id> --format json --output ./export/
```

Available formats: `json`, `jsonl`, `markdown`.

The export manifest includes:
- Subject identifier
- Export timestamp
- Redaction status (what was redacted and why)
- Hermes profile hash (not the raw profile)
- Event counts by ontological class
- Confirmed continuity markers

**What is excluded by default:**
- Raw session text (redacted)
- Safety signals (researcher-only, never in subject exports)
- Unconfirmed continuity markers
- Internal system traces

To include raw session text (requires explicit opt-in):

```bash
relic subject export <subject_id> --include-raw-text --format json --output ./export/
```

An audit event is written to `relic.db` on every export.

## Pause

Pause disables proactive behavior without deleting anything:

```bash
relic subject pause <subject_id>
```

When paused, Gumi will not send proactive messages or run cron-scheduled outreach. She can still respond to incoming messages in a reduced mode that does not inject personalization context. To resume:

```bash
relic subject unpause <subject_id>
```

Use pause when a subject is in a sensitive period and you do not want the system acting on its current model.

## Forget

Forget removes specific data from Gumi's recall without deleting it from `relic.db`:

```bash
relic subject forget <subject_id> --session-id <session_id>
```

This is useful in regulatory contexts where audit data must be retained but the subject wants the agent to stop referencing specific content. An audit event is created. Forget is subject-scoped; it cannot affect another subject's data.

## Deletion

!!! danger "Deletion is irreversible"
    Deleted data cannot be recovered. Run a dry-run first to see what will be affected.

```bash
# Dry run: shows what would be deleted
relic subject delete <subject_id> --scope all --dry-run

# Actual deletion
relic subject delete <subject_id> --scope all
```

Deletion scopes:

| Scope | What is removed |
|---|---|
| `prompt` | A specific prompt and its derived artifacts |
| `session` | All data from one session |
| `all` | All data for the subject, including the profile |

Deletion invalidates replication bundles and eval cases derived from the deleted data. They are not silently left intact as if the underlying data still existed.

An audit event is written on every deletion. Subject scope is preserved in the audit record even after the data is gone.

## Consent revocation

To revoke specific consent types without a full deletion:

```python
from relic.control.consent import ConsentManager, ConsentType

mgr = ConsentManager()
mgr.revoke_consent(ConsentType.MEMORY_STORAGE)
```

Consent revocation takes effect immediately. The system will not process new interaction data after revocation of `memory_storage` consent.
